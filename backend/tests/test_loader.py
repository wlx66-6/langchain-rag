"""loader.py 的单元测试：文件格式白名单校验 + 纯文本解析。"""
import pytest

from app.services.loader import allowed_ext, check_allowed, load_file


class TestAllowedExt:
    def test_lowercases_extension(self):
        assert allowed_ext("report.PDF") == ".pdf"
        assert allowed_ext("数据.XLSX") == ".xlsx"

    def test_no_extension_returns_empty(self):
        assert allowed_ext("README") == ""


class TestCheckAllowed:
    @pytest.mark.parametrize(
        "name", ["a.pdf", "b.docx", "c.xlsx", "d.txt", "e.md", "f.csv"]
    )
    def test_allowed_extensions_pass(self, name):
        assert check_allowed(name) == allowed_ext(name)

    def test_disallowed_extension_raises(self):
        with pytest.raises(ValueError):
            check_allowed("virus.exe")


class TestLoadFile:
    def test_load_txt(self, tmp_path):
        p = tmp_path / "说明.txt"
        p.write_text("示例耳机，续航 40 小时。", encoding="utf-8")
        docs = load_file(p, "说明.txt")
        assert len(docs) == 1
        assert docs[0].page_content == "示例耳机，续航 40 小时。"

    def test_load_markdown(self, tmp_path):
        p = tmp_path / "商品.md"
        p.write_text("# 标题\n内容正文", encoding="utf-8")
        docs = load_file(p, "商品.md")
        assert len(docs) == 1
        assert "# 标题" in docs[0].page_content

    def test_load_disallowed_ext_raises(self, tmp_path):
        p = tmp_path / "x.exe"
        p.write_text("x")
        with pytest.raises(ValueError):
            load_file(p, "x.exe")


class TestLoadExcel:
    def test_loads_sheet_as_one_document(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "尺码表"
        ws.append(["尺码", "身高"])
        ws.append(["M", 170])
        path = tmp_path / "尺码.xlsx"
        wb.save(path)

        docs = load_file(path, "尺码.xlsx")
        assert len(docs) == 1
        assert "尺码表" in docs[0].page_content
        assert "M | 170" in docs[0].page_content

    def test_blank_sheet_yields_no_document(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()  # 默认空表，没有任何单元格
        path = tmp_path / "空表.xlsx"
        wb.save(path)

        assert load_file(path, "空表.xlsx") == []


class TestLoadCsv:
    def test_loads_utf8_csv(self, tmp_path):
        p = tmp_path / "颜色.csv"
        p.write_text("颜色,库存\n黑色,10\n", encoding="utf-8")
        docs = load_file(p, "颜色.csv")
        assert len(docs) == 1
        assert "黑色 | 10" in docs[0].page_content

    def test_loads_gbk_csv(self, tmp_path):
        # 中文 Windows 上导出的 CSV 常见 GBK 编码，应能自动识别
        p = tmp_path / "gbk.csv"
        p.write_bytes("尺码,身高\nL,175\n".encode("gbk"))
        docs = load_file(p, "gbk.csv")
        assert len(docs) == 1
        assert "L | 175" in docs[0].page_content