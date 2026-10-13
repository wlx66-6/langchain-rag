"""实测 SSE 首字延迟（单请求，串行）。

测三个数，故意分开——它们回答的是不同问题：

  - **检索链路耗时**：到首个 SSE 事件 `start` 的时间。服务端在开始流式输出之前，必须先完成
    「追问改写 → 向量检索 → 重排」，`start` 事件才携带引用片段发出，所以它衡量的是检索链路。
  - **首字延迟**：到首个 `token` 事件的时间 = 检索链路 + 大模型吐出第一个字。
  - **总时长**：到 `done` 事件。

「首轮提问」与「同会话追问」会给出明显不同的数字：首轮没有历史，追问改写这一步被短路；
追问有历史，会多出一次真实的大模型调用，检索链路随之变长。两者都测，避免只报有利的那个。

用法（后端需已启动，且 bge-m3 已就位）：

    # 在仓库根目录执行
    venv\\Scripts\\python.exe loadtest\\measure_latency.py --doc loadtest\\sample_doc.md

    # 已有文档在知识库里时，可跳过上传
    venv\\Scripts\\python.exe loadtest\\measure_latency.py --no-upload \\
        --username admin --password 你的管理员密码

注意：本脚本会向知识库**上传**文档，并在结束时**删除**它及本次产生的会话，
不给环境留垃圾数据。请在个人开发环境运行。
"""

import argparse
import json
import os
import sys
import time

import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"


def sse_marks(
    client: httpx.Client, base: str, token: str, question: str, conv_id: int | None
) -> dict:
    """发一次流式提问，返回各阶段耗时（秒）与新建会话 ID。"""
    t0 = time.perf_counter()
    marks: dict = {}
    with client.stream(
        "POST",
        f"{base}/api/chat",
        headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
        json={"content": question, "conversation_id": conv_id},
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            now = time.perf_counter() - t0
            try:
                evt = json.loads(line[6:])
            except json.JSONDecodeError:
                continue  # 心跳或非 JSON 行，忽略
            etype = evt.get("type")
            if etype == "start" and "ttfb" not in marks:
                marks["ttfb"] = now
                marks["conv_id"] = evt["data"]["conversation_id"]
                marks["sources"] = len(evt["data"].get("sources") or [])
            elif etype == "token" and "first_token" not in marks:
                marks["first_token"] = now
            elif etype == "done":
                marks["total"] = now
            elif etype == "error":
                marks["error"] = evt
    return marks


def show(label: str, marks: dict) -> None:
    if "error" in marks:
        print(f"  {label:<22} !! 出错: {marks['error']}")
        return
    print(
        f"  {label:<22} 检索链路={marks['ttfb']:5.2f}s  "
        f"首字={marks['first_token']:5.2f}s  总时长={marks['total']:5.2f}s  "
        f"引用={marks.get('sources', 0)} 条"
    )


def summarize(name: str, rows: list[dict]) -> None:
    print(f"\n[汇总] {name}  n={len(rows)}")
    for key, label in (
        ("ttfb", "检索链路(TTFB)"),
        ("first_token", "首字延迟"),
        ("total", "总时长"),
    ):
        vals = sorted(r[key] for r in rows if key in r)
        if vals:
            print(
                f"  {label:<16} 平均 {sum(vals) / len(vals):5.2f}s   最小 {vals[0]:5.2f}s   最大 {vals[-1]:5.2f}s"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="实测 SSE 首字延迟")
    ap.add_argument("--doc", help="上传入库的示例文档路径（用于让检索有内容）")
    ap.add_argument("--no-upload", action="store_true", help="跳过上传，直接用知识库现有内容")
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"后端地址（默认 {DEFAULT_BASE}）")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="123456")
    ap.add_argument("--rounds", type=int, default=3, help="每种场景的请求次数（默认 3）")
    args = ap.parse_args()

    base = args.base
    client = httpx.Client(timeout=180)

    try:
        r = client.post(
            f"{base}/api/auth/login",
            json={"username": args.username, "password": args.password},
        )
    except httpx.ConnectError:
        print(f"连不上后端 {base}，请先启动服务（见 loadtest/README.md）")
        return 1
    if r.status_code != 200:
        print(f"登录失败 {r.status_code}：{r.text[:200]}")
        return 1
    token = r.json()["access_token"]
    if not r.json().get("is_admin"):
        print("该账号不是管理员，无法上传示例文档；请用管理员账号或加 --no-upload")
        return 1
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[登录] {args.username} 成功")

    doc_id = None
    if args.doc and not args.no_upload:
        with open(args.doc, "rb") as fh:
            r = client.post(
                f"{base}/api/knowledge/upload",
                headers=headers,
                files={"file": (os.path.basename(args.doc), fh, "text/markdown")},
            )
        if r.status_code != 201:
            print(f"上传失败 {r.status_code}：{r.text[:200]}")
            return 1
        doc_id = r.json()["id"]
        print(f"[上传] id={doc_id} 已入库（{r.json().get('chunk_count')} 个文本块）")

    try:
        print(
            "\n[首次问答] 不计入统计：可能含加载 bge-m3（用 --no-upload 时）"
            "与首次流式建连的开销，作为「最坏情况」参考 ..."
        )
        show("首次问答", sse_marks(client, base, token, "这个商品有哪些规格？", None))

        print(f"\n[实测] 首轮提问（新会话，无历史 → 追问改写被短路），{args.rounds} 次：")
        first_rows = []
        conv_id = None
        for i in range(args.rounds):
            m = sse_marks(client, base, token, "云澜 X3 有哪些颜色可选？", None)
            first_rows.append(m)
            show(f"第 {i + 1} 次", m)
            conv_id = m.get("conv_id")
        summarize("首轮提问", first_rows)

        print(f"\n[实测] 同会话追问（有历史 → 追问改写真实调用大模型），{args.rounds} 次：")
        follow_rows = []
        for q in ["它的售后政策是什么？", "那保修期多久？", "哪些情况不保修？"][: args.rounds]:
            m = sse_marks(client, base, token, q, conv_id)
            follow_rows.append(m)
            show(q[:14], m)
        summarize("同会话追问", follow_rows)

        print(
            "\n提示：本机串行单请求的数字会明显好于并发场景。"
            "并发下的延迟与吞吐见 loadtest/report.md。"
        )
    finally:
        # 清理：删掉本次上传的文档与产生的会话，不给环境留垃圾
        removed = 0
        if doc_id is not None:
            client.delete(f"{base}/api/knowledge/documents/{doc_id}", headers=headers)
            removed += 1
        listed = client.get(f"{base}/api/conversations?limit=200", headers=headers).json()
        for conv in listed.get("items", listed) if isinstance(listed, dict) else listed:
            if (
                client.delete(f"{base}/api/conversations/{conv['id']}", headers=headers).status_code
                == 200
            ):
                removed += 1
        print(f"\n[清理] 已删除本次上传的文档与测试会话（共 {removed} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
