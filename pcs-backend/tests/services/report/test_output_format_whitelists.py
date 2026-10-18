"""四份输出格式白名单必须是同一份（评审 #19）。

## 这条测试为什么存在

评审 #19 的原话是「两份输出格式白名单不一致：generate 拒 csv，execute 收
csv」。修的时候数出来的是**四份**：

| # | 位置 | 内容 |
|---|---|---|
| 1 | `schemas/report.py` `SUPPORTED_OUTPUT_FORMATS` | 无 csv |
| 2 | `services/report/report_service.py` `SUPPORTED_FORMATS` | 有 csv，但**是硬编码字面量** |
| 3 | `services/report/watermark.py` `EXPORT_FORMATS` | 有 csv |
| 4 | `api/v1/report_builder.py` `_RENDERABLE_FORMATS` | 有 csv（`frozenset(watermark.EXPORT_FORMATS)`，正确派生） |

第 2 份的注释写着「取自 `watermark.EXPORT_FORMATS`」—— 那是**愿望不是事实**，
它是字面量。注释比代码乐观这件事在本仓出现过不止一次
（`.wolf/cerebrum.md`「读评审结论」节）。

所以本测试不是断言「csv 在不在」，而是断言**四份指向同一个集合**：
再加一种格式时，改一处就会红，而不是像 #19 那样改漏一处、
缺陷要等用户点「导出 CSV」才暴露。

## 观测点选在哪 —— 这里踩了两个坑，都记在下面

**坑一：内容相等证明不了派生。**
`frozenset({...同样四个...})` 与 `frozenset(EXPORT_FORMATS)` 今天相等，
但加第 5 种格式时前者不动。#19 的缺陷正是这个形状。
⇒ 断言必须是**结构**的。

**坑二：字符串匹配证明不了派生，因为它会被注释骗。**
第一版用 `inspect.getsource(...)` 里找 `'EXPORT_FORMATS'` 子串 ——
结果**绿的**，可代码是硬编码字面量。因为 `report_service.py` 里那句
**说谎的注释**正好写着「取自 `watermark.EXPORT_FORMATS`」。
⇒ 必须走 AST，注释进不了 AST。
"""

import ast
import inspect

from app.api.v1 import report as report_api
from app.api.v1 import report_builder as report_builder_api
from app.schemas import report as report_schemas
from app.services.report import report_service, watermark


def test_watermark_is_the_single_source_of_truth():
    """权威副本在 watermark（渲染器所在层）—— 它列什么就真的渲染得出什么。"""
    assert set(watermark.EXPORT_FORMATS) == {"pdf", "xlsx", "docx", "csv"}


def _references_export_formats(module) -> bool:
    """模块 AST 里是否真的**引用**了 `EXPORT_FORMATS`。

    走 AST 而非 `getsource` 找子串 —— 后者会被注释骗（见文件头坑二）。
    还要排除 `from ... import EXPORT_FORMATS` 那种「引进来但没用」。
    """
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        # 形如 `watermark.EXPORT_FORMATS` 的 Attribute 读取
        if isinstance(node, ast.Attribute) and node.attr == "EXPORT_FORMATS":
            return True
        # 形如 `EXPORT_FORMATS` 的裸 Name 读取（排除 import 语句里的）
        if isinstance(node, ast.Name) and node.id == "EXPORT_FORMATS":
            return True
    return False


def test_service_whitelist_is_derived_not_copied():
    assert _references_export_formats(report_service), (
        "report_service.SUPPORTED_FORMATS 是硬编码字面量 —— 内容相等证明不了"
        "派生，加新格式时它不会跟着动（#19 的形状）"
    )


def test_schema_whitelist_is_derived_not_copied():
    assert _references_export_formats(report_schemas), (
        "schemas.report.SUPPORTED_OUTPUT_FORMATS 是硬编码字面量（#19 的形状）"
    )
    assert tuple(report_schemas.SUPPORTED_OUTPUT_FORMATS) == tuple(
        watermark.EXPORT_FORMATS
    )


def test_api_whitelist_is_derived_not_copied():
    assert report_builder_api._RENDERABLE_FORMATS == frozenset(
        watermark.EXPORT_FORMATS
    )


def test_every_declared_format_has_a_media_type():
    """下载端点的 Content-Type 映射也必须覆盖全部格式。

    漏一个不会报错 —— `report.py` 的 `_MEDIA.get(fmt, octet-stream)` 会静默
    兜底，于是浏览器把 CSV 当二进制下载而不是表格。
    """
    missing = set(watermark.EXPORT_FORMATS) - set(report_api._MEDIA)
    assert not missing, f"这些格式没有 media type：{sorted(missing)}"


def test_generate_and_execute_accept_the_same_formats():
    """#19 的正面：直接 generate 与走定义的 execute 白名单一致。

    两端点各自校验、各自报错码（REPORT_FORMAT_UNSUPPORTED vs
    REPORT_OUTPUT_FORMAT_UNSUPPORTED）—— 报错码分开是有意的，
    **可接受集合**必须一致。
    """
    assert set(report_schemas.SUPPORTED_OUTPUT_FORMATS) == set(
        report_builder_api._RENDERABLE_FORMATS
    )
