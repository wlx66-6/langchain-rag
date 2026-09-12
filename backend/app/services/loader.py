"""文档解析：把上传的 PDF / Word / Excel / TXT / Markdown / CSV 提取成文字。"""
import csv
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_core.documents import Document

_ALLOWED_EXTS = {".pdf", ".docx", ".xlsx", ".xlsm", ".txt", ".md", ".markdown", ".csv"}


def allowed_ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def check_allowed(filename: str) -> str:
    ext = allowed_ext(filename)
    if ext not in _ALLOWED_EXTS:
        raise ValueError(f"不支持的文件格式：{ext}（支持 PDF/Word/Excel/TXT/Markdown/CSV）")
    return ext


def load_file(path: Path, original_filename: str) -> list[Document]:
    """按扩展名分派到对应的解析器，统一返回 LangChain Document 列表。"""
    ext = check_allowed(original_filename)

    if ext == ".pdf":
        return PyPDFLoader(str(path)).load()

    if ext == ".docx":
        return Docx2txtLoader(str(path)).load()

    if ext in {".xlsx", ".xlsm"}:
        return _load_excel(path)

    if ext in {".txt", ".md", ".markdown"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return [Document(page_content=text)]

    if ext == ".csv":
        return _load_csv(path)

    return []


def _load_excel(path: Path) -> list[Document]:
    """Excel：每个工作表读成一篇文字，单元格之间用 ' | ' 分隔。"""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    docs: list[Document] = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            docs.append(Document(page_content=f"工作表「{ws.title}」：\n" + "\n".join(rows)))
    wb.close()
    return docs


def _load_csv(path: Path) -> list[Document]:
    """CSV：尝试多种常见编码，读成一篇文章。"""
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            with open(path, newline="", encoding=enc) as f:
                reader = csv.reader(f)
                rows = [" | ".join(r) for r in reader if any(r)]
            if rows:
                return [Document(page_content="\n".join(rows))]
        except UnicodeDecodeError:
            continue
    return []