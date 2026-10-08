"""ReportStyle 四级优先级合并的契约测试。

顺序 **默认 → 报表类型 → 项目 → 运行时** 是用户 2026-10-08 裁决的，
ADR-P8-001 原文的「默认 → 项目 → 报表类型 → 运行时」作废：报表类型级是公司
标准（默认值），项目级是更具体的上下文，应当覆盖它。反过来会让「项目级样式」
这一层失去存在意义。
"""
from app.services.report.style import ReportStyle, resolve


def test_precedence_is_defaults_type_project_runtime():
    d = ReportStyle(font_size_body=10)
    t = ReportStyle(font_size_body=12)
    pj = ReportStyle(font_size_body=11)
    r = ReportStyle(font_size_body=13)
    assert resolve(defaults=d, by_type=t, project=pj, runtime=r).font_size_body == 13
    assert resolve(defaults=d, by_type=t, project=pj, runtime=None).font_size_body == 11
    assert resolve(defaults=d, by_type=t, project=None, runtime=None).font_size_body == 12
    assert resolve(defaults=d, by_type=None, project=None, runtime=None).font_size_body == 10


def test_locked_fields_ignore_every_layer():
    """公司强制标准字段任何层都改不了。

    P8 先只锁 page_size / orientation（改了版式 A4/A3 就不再是标准计算书了）。
    页脚必含 doc_no 之类的业务强制项待工艺确认后再加。
    """
    d = ReportStyle(page_size="A4")
    assert resolve(defaults=d, by_type=ReportStyle(page_size="A3"),
                   project=ReportStyle(page_size="Letter"),
                   runtime=ReportStyle(page_size="A3")).page_size == "A4"
    # 未锁定的字段仍然正常覆盖
    assert resolve(defaults=d, by_type=ReportStyle(font_size_body=12),
                   project=ReportStyle(font_size_body=11),
                   runtime=None).font_size_body == 11


def test_none_layers_do_not_erase_lower_precedence_values():
    d = ReportStyle(font_size_body=10, font_family_cn="Noto Sans CJK SC")
    out = resolve(defaults=d, by_type=ReportStyle(), runtime=None)
    assert out.font_family_cn == "Noto Sans CJK SC", "空层不得把下层值清掉"


def test_unset_field_falls_through_to_lower_layer():
    """只覆盖一个字段时，其余字段必须保留低层值 —— 靠 exclude_unset。

    model_validate({...}) 只把出现的键算作「已设置」，
    而 ReportStyle(font_size_body=12) 的其余字段全部是「已设置」。
    """
    layer = ReportStyle.model_validate({"font_size_body": 12})
    out = resolve(defaults=ReportStyle.model_validate(
                      {"font_size_body": 10, "font_family_cn": "A"}),
                  project=layer, runtime=None)
    assert out.font_size_body == 12
    assert out.font_family_cn == "A"


def test_locked_fields_themselves_cannot_be_overridden():
    """上层不能通过改 locked_fields 来解锁自己。

    循环里 `k not in defaults.locked_fields` 检查的是**值**不是**键名**，
    拦不住对 locked_fields 键自身的覆盖。合并后必须显式还原。
    """
    d = ReportStyle()
    sneaky = ReportStyle.model_validate(
        {"locked_fields": frozenset({"font_size_body"})})
    out = resolve(defaults=d, by_type=sneaky, project=None, runtime=None)
    assert out.locked_fields == frozenset({"page_size", "orientation"})
    assert out.font_size_body == d.font_size_body, "被 sneaky 解锁的字段不应被改动"


def test_footer_has_no_pages_placeholder():
    """`{{pages}}` 已于 2026-10-08 从 SPEC §4.1 移除。

    ReportLab 需两遍渲染才能知道总页数，代价是生成时间 ×2，而总页数在 PDF
    阅读器里本就可见。样式默认值里若还留着它，`_fill_placeholders` 会原样保留
    一个永远替换不掉的占位符印在页脚上。
    """
    assert "{{pages}}" not in ReportStyle().footer.right
    assert "{{page}}" in ReportStyle().footer.right
