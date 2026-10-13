"""RAG 核心编排：追问改写 → 检索 → 重排 → 生成（带引用出处）。"""
from http import HTTPStatus

import dashscope
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.services.mock_llm import MockChatModel
from app.services.vectorstore import get_vectorstore

# 追问改写提示词：把「它多少钱」这种缺少主语的追问，结合上文还原成完整问题
_CONTEXTUALIZE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是对话改写助手。请结合下面的历史对话，把用户当前的问题改写成一个"
            "不依赖上文、能独立理解的完整问题。只输出改写后的问题，不要输出任何解释。",
        ),
        ("human", "历史对话：\n{history}\n\n当前问题：{question}\n\n改写后的问题："),
    ]
)

# 回答提示词：要求只依据资料回答、并在句尾用 [编号] 标注出处
_ANSWER_SYSTEM = (
    "你是某电商平台的智能客服，负责基于知识库回答用户关于商品的问题。\n"
    "请严格遵守以下规则：\n"
    "1. 只依据下面「知识库参考资料」给出的内容回答，不要使用你自己的知识，也不要编造信息。\n"
    "2. 回答时，若某句话依据了某段资料，请在该句末尾用 [编号] 标注出处，例如 [1]、[2]。\n"
    "3. 如果参考资料中没有足够信息能回答用户的问题，请明确回复"
    "「知识库中未找到相关内容，无法回答」，不要瞎编。\n"
    "4. 回答要条理清晰、通俗易懂，尽量分点说明。\n\n"
    "知识库参考资料：\n{context}"
)
_ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _ANSWER_SYSTEM),
        ("human", "{question}"),
    ]
)


def get_llm(streaming: bool = True):
    """创建大模型实例：压测（MOCK_LLM=1）时用假模型，正常用通义千问（百炼）。"""
    if settings.mock_llm:
        return MockChatModel()
    return ChatTongyi(model=settings.qwen_model, streaming=streaming, temperature=0.3)


def _format_history(history: list[dict]) -> str:
    """把历史消息列表转成便于大模型阅读的纯文本。"""
    lines = []
    for m in history:
        who = "用户" if m["role"] == "user" else "客服"
        lines.append(f"{who}：{m['content']}")
    return "\n".join(lines) or "（无历史对话）"


async def rewrite_question(question: str, history: list[dict]) -> str:
    """多轮追问时，把问题结合上下文改写成完整问题；无历史（或压测假模式）则原样返回。"""
    if settings.mock_llm or not history:
        return question
    llm = get_llm(streaming=False)
    chain = _CONTEXTUALIZE_PROMPT | llm
    result = await chain.ainvoke(
        {"history": _format_history(history), "question": question}
    )
    return result.content.strip()


def retrieve(question: str, k: int | None = None) -> list[tuple[Document, float]]:
    """根据问题在向量库里检索最相关的几段内容。"""
    k = k or settings.top_k
    vectorstore = get_vectorstore()
    return vectorstore.similarity_search_with_score(question, k=k)


def _dedup(docs_with_score: list[tuple[Document, float]]) -> list[tuple[Document, float]]:
    """去掉完全重复的片段（对应「同一份文件传了两次」导致的重复引用）。

    去重键必须带上来源：不同文件里出现一模一样的句子是很常见的情况
    （例如两份文档都写了同一句售后条款），只按内容去重会把来自另一份资料的
    引用误删掉。只有「来源 + 内容」都相同才算重复。
    """
    seen: set[tuple[str, str]] = set()
    out: list[tuple[Document, float]] = []
    for doc, score in docs_with_score:
        content = doc.page_content.strip()
        if not content:
            continue
        key = (doc.metadata.get("source", ""), content)
        if key in seen:
            continue
        seen.add(key)
        out.append((doc, score))
    return out


def _rerank(question: str, docs_with_score: list[tuple[Document, float]]) -> list[tuple[Document, float]]:
    """重排：用百炼重排模型给每段候选逐个「精读打分」，及格（≥rerank_min_score）的按相关度排序返回。

    相当于先海选出一堆候选，再请评委逐个精读，只留真正贴题的那几条。
    重排调用失败时退回原始顺序（仅去重），不阻断主流程。
    """
    if not docs_with_score:
        return []

    texts = [doc.page_content for doc, _ in docs_with_score]
    try:
        resp = dashscope.TextReRank.call(
            model=settings.rerank_model,
            query=question,
            documents=texts,
            top_n=len(texts),  # 让重排给所有候选都打分，后面由我们自己筛
            api_key=settings.dashscope_api_key or None,
        )
        if resp.status_code != HTTPStatus.OK:
            return _dedup(docs_with_score)

        results = getattr(getattr(resp, "output", None), "results", None) or []
        # 先把所有候选按相关度从高到低排好（含不及格的，留作兜底用）
        scored: list[tuple[int, float]] = []
        for r in results:
            idx = r["index"] if isinstance(r, dict) else r.index
            score = r["relevance_score"] if isinstance(r, dict) else r.relevance_score
            scored.append((idx, float(score or 0.0)))
        scored.sort(key=lambda item: item[1], reverse=True)
        if not scored:
            return _dedup(docs_with_score)  # 重排没给出任何分数，退回原始顺序
        # 及格（≥rerank_min_score）的才保留，最多 rerank_top_n 条
        kept = [(idx, s) for idx, s in scored if s >= settings.rerank_min_score]
        if not kept:
            # 兜底：及格线筛空时，也要留下最相关的第一名，避免「有答案却说找不到」
            kept = scored[:1]
        kept = kept[: settings.rerank_top_n]
        return _dedup([(docs_with_score[idx][0], s) for idx, s in kept])
    except Exception:
        return _dedup(docs_with_score)


def retrieve_with_rerank(question: str) -> list[tuple[Document, float]]:
    """检索 + 重排的完整流程：先海选候选 → 去重 → 精读打分筛选，返回最贴题的几段。

    压测假模式（MOCK_LLM=1）下跳过远程重排，直接把词向量检索结果去重后截取前 top_k 段。
    """
    candidates = _dedup(retrieve(question, k=settings.rerank_candidates))
    if settings.mock_llm:
        return candidates[: settings.top_k]
    return _rerank(question, candidates)


def format_context(docs_with_score: list[tuple[Document, float]]) -> str:
    """把检索到的片段按 [1][2]… 编号拼成给大模型的上下文。"""
    parts = []
    for i, (doc, _score) in enumerate(docs_with_score, start=1):
        source = doc.metadata.get("source", "未知来源")
        parts.append(f"[{i}]（来源：{source}）\n{doc.page_content}")
    return "\n\n".join(parts)


def build_sources(docs_with_score: list[tuple[Document, float]]) -> list[dict]:
    """从检索结果提取「引用片段」列表（文件名 + 内容），返回给前端展示。"""
    return [
        {
            "source": doc.metadata.get("source", "未知来源"),
            "content": doc.page_content,
        }
        for doc, _score in docs_with_score
    ]


def build_answer_chain():
    return _ANSWER_PROMPT | get_llm(streaming=True)