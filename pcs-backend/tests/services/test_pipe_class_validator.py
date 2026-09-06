"""PC-2：管道等级验证引擎 22 条规则测试（V1.4 修正）。

覆盖 PC-V（11）+ PC-E（7）+ PC-C（4）= 22 条规则。
"""
from __future__ import annotations

import inspect

from app.services.pipe_class_validator import (
    PipeClassValidator,
    Severity,
    ValidationContext,
    ValidationResult,
)

# ---------- 测试基线数据 ----------

def _base_data(**overrides) -> dict:
    """合法基线数据，测试通过修改字段触发对应规则。"""
    dn_full = [15, 20, 25, 40, 50, 80, 100, 150, 200, 250, 300, 350, 400,
               450, 500, 600, 700, 800, 900]
    data = {
        "class_id": "U4",
        "class_name": "Cooling Water",
        "material_standard": "ASME B31.3",
        "base_material": "A106 Gr.B",
        "corrosion_allowance": 1.6,
        "design_pressure": 1.0,
        "design_temperature": 110,
        "dn_series_json": {"min": 15, "max": 900, "series": dn_full},
        "sch_series_json": {
            "DN15": [80, 160],
            "DN50": [40, 80, 160],
            "DN200": [40, 80],
            "DN700": [10],
        },
        "flange_class": "150#",
        "fitting_type": "对焊",
        "allowable_stress_json": {"table": "COMMON_ASME_B31_3_TABLE_A1"},
        "branch_table_json": {"table": "COMMON_BRANCH_TABLE_01"},
    }
    data.update(overrides)
    return data


# ---------- PC-V 结构完整性（11 条） ----------

class TestPCV:
    def test_v01_missing_required_fields(self):
        """缺 class_name 触发 PC-V01 ERROR。"""
        data = _base_data()
        del data["class_name"]
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V01" and r.severity == Severity.ERROR for r in results)

    def test_v02_dn_series_min_gt_max(self):
        """dn_series min > max 触发 PC-V02 ERROR。"""
        data = _base_data(dn_series_json={"min": 600, "max": 15, "series": []})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V02" and r.severity == Severity.ERROR for r in results)

    def test_v03_sch_dn_not_in_dn_series(self):
        """sch 中 DN999 不在 dn_series 内 → PC-V03 ERROR。"""
        data = _base_data(sch_series_json={"DN200": [40], "DN999": [80]})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V03" and r.severity == Severity.ERROR for r in results)

    def test_v04_sch_value_zero(self):
        """Sch 值 ≤ 0 触发 PC-V04 ERROR。"""
        data = _base_data(sch_series_json={"DN15": [0]})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V04" and r.severity == Severity.ERROR for r in results)

    def test_v05_pressure_out_of_range(self):
        """design_pressure 超出 (0, 42] → PC-V05 ERROR。"""
        data = _base_data(design_pressure=43.0)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V05" and r.severity == Severity.ERROR for r in results)

    def test_v06_temp_out_of_range_warn(self):
        """design_temperature 超出 [-196, 650] → PC-V06 WARN。"""
        data = _base_data(design_temperature=700)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V06" and r.severity == Severity.WARN for r in results)

    def test_v07_corrosion_allowance_null(self):
        """corrosion_allowance=None → PC-V07 ERROR。"""
        data = _base_data(corrosion_allowance=None)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V07" and r.severity == Severity.ERROR for r in results)

    def test_v08_flange_class_invalid(self):
        """非法法兰等级 '100#' → PC-V08 ERROR。"""
        data = _base_data(flange_class="100#")
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V08" and r.severity == Severity.ERROR for r in results)

    def test_v09_project_class_name_duplicate(self):
        """项目内重名 → PC-V09 ERROR。"""
        data = _base_data(class_name="U4")
        ctx = ValidationContext(existing_class_names=["U4"])
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-V09" and r.severity == Severity.ERROR for r in results)

    def test_v10_source_class_id_invalid(self):
        """公司级数据传入项目级验证无 source_class_id——不触发 PC-V10。

        V1.4 修正：source_class_id 校验移交给 service 层
        （PipeClassValidator.is_valid_source_class_id）。
        """
        data = _base_data()
        ctx = ValidationContext(existing_class_names=[])
        results = PipeClassValidator.validate_project(data, ctx)
        assert not any(r.rule_id == "PC-V10" for r in results)
        # V1.4 补充：validator 暴露 is_valid_source_class_id async classmethod
        assert hasattr(PipeClassValidator, "is_valid_source_class_id")
        assert inspect.iscoroutinefunction(PipeClassValidator.is_valid_source_class_id)

    def test_v11_fitting_type_invalid_component(self):
        """fitting_type 含非法段 '焊接'（正确为'对焊'）→ PC-V11 ERROR。"""
        data = _base_data(fitting_type="焊接/法兰")
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-V11" and r.severity == Severity.ERROR for r in results)


# ---------- PC-E 工程一致性（7 条） ----------

class TestPCE:
    def test_e01_carbon_steel_high_temp_warn(self):
        """A106 碳钢 + 450°C → PC-E01 WARN。"""
        data = _base_data(base_material="A106 Gr.B", design_temperature=450)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E01" and r.severity == Severity.WARN for r in results)

    def test_e02_flange_150_over_pressure_warn(self):
        """150# + 2.5 MPa（超 1.96 基准但未到 5.11）→ PC-E02 WARN。"""
        data = _base_data(flange_class="150#", design_pressure=2.5)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E02" and r.severity == Severity.WARN for r in results)

    def test_e03_pressure_exceeds_flange_rating_error(self):
        """150# + 5.0 MPa（超 5.11 类上限 300#） → PC-E03 ERROR。"""
        data = _base_data(flange_class="150#", design_pressure=5.0)
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E03" and r.severity == Severity.ERROR for r in results)

    def test_e04_table_ref_missing_error(self):
        """V1.4 修正：传入 common_tables，NONEXISTENT_TABLE 触发 PC-E04 ERROR。"""
        data = _base_data(allowable_stress_json={"table": "NONEXISTENT_TABLE"})
        results = PipeClassValidator.validate_company(
            data, common_tables={"COMMON_ASME_B31_3_TABLE_A1", "COMMON_BRANCH_TABLE_01"}
        )
        assert any(r.rule_id == "PC-E04" and r.severity == Severity.ERROR for r in results)

    def test_e04_no_common_tables_passes(self):
        """V1.4：未传 common_tables 时不触发 PC-E04（视为通过）。"""
        data = _base_data(allowable_stress_json={"table": "ANY_TABLE"})
        results = PipeClassValidator.validate_company(data, common_tables=None)
        assert not any(r.rule_id == "PC-E04" for r in results)

    def test_e05_dn_over_600_warn(self):
        """dn_series.max > 600 → PC-E05 WARN。"""
        data = _base_data(dn_series_json={"min": 15, "max": 900, "series": [15, 900]})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E05" and r.severity == Severity.WARN for r in results)

    def test_e06_fork_pressure_without_flange_warn(self):
        """V1.4：is_fork=True + override 设计压力但未覆写法兰 → PC-E06 WARN。"""
        data = _base_data(design_pressure=3.0, flange_class="150#")
        ctx = ValidationContext(
            existing_class_names=[],
            is_fork=True,
            override_keys=["design_pressure"],
        )
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-E06" and r.severity == Severity.WARN for r in results)

    def test_e07_sch_empty_but_dn_nonempty_error(self):
        """dn_series 非空但 sch_series 为空 → PC-E07 ERROR。"""
        data = _base_data(sch_series_json={})
        results = PipeClassValidator.validate_company(data)
        assert any(r.rule_id == "PC-E07" and r.severity == Severity.ERROR for r in results)


# ---------- PC-C 项目上下文（4 条） ----------

class TestPCC:
    def test_c01_project_pressure_over_limit_warn(self):
        """项目压力上限 2.0，等级 2.5 → PC-C01 WARN。"""
        data = _base_data(design_pressure=2.5)
        ctx = ValidationContext(project_pressure_limit=2.0)
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-C01" and r.severity == Severity.WARN for r in results)

    def test_c02_material_not_in_project_list_warn(self):
        """材料不在项目允许列表 → PC-C02 WARN。"""
        data = _base_data(base_material="A312 TP304L")
        ctx = ValidationContext(project_allowed_materials=["A106 Gr.B"])
        results = PipeClassValidator.validate_project(data, ctx)
        assert any(r.rule_id == "PC-C02" and r.severity == Severity.WARN for r in results)

    def test_c03_same_name_diff_source_error(self):
        """V1.4：与 PC-V09 语义重合（项目级重名），任一规则触发即通过。

        同项目内同名 → PC-V09 OR PC-C03 ERROR。
        """
        data = _base_data(class_name="U4", source_class_id="A1B")
        ctx = ValidationContext(existing_class_names=["U4"])
        results = PipeClassValidator.validate_project(data, ctx)
        triggered = any(
            r.severity == Severity.ERROR and r.rule_id in {"PC-V09", "PC-C03"}
            for r in results
        )
        assert triggered, f"期望 PC-V09 或 PC-C03 触发 ERROR，实际：{[r.rule_id for r in results]}"

    def test_c04_in_use_block_delete_error(self):
        """V1.4：service 层在删除前调 PipeClassValidator.is_in_use。

        validator 暴露 is_in_use async classmethod，签名 async def(cls, db, class_id) -> bool。
        """
        assert hasattr(PipeClassValidator, "is_in_use")
        sig = inspect.signature(PipeClassValidator.is_in_use)
        # classmethod 通过 inspect.signature 查时不含隐式 cls，故 2 个形参 (db, class_id)
        assert len(sig.parameters) == 2
        assert "db" in sig.parameters
        assert "class_id" in sig.parameters
        assert inspect.iscoroutinefunction(PipeClassValidator.is_in_use)


# ---------- 接口契约附加测试 ----------

class TestInterface:
    def test_has_errors_true_when_error(self):
        """has_errors 命中 ERROR 返回 True。"""
        data = _base_data()
        del data["class_name"]
        results = PipeClassValidator.validate_company(data)
        assert PipeClassValidator.has_errors(results) is True

    def test_has_errors_false_when_clean(self):
        """干净数据 has_errors 返回 False。"""
        results = PipeClassValidator.validate_company(_base_data())
        assert PipeClassValidator.has_errors(results) is False

    def test_validation_result_is_dataclass(self):
        """ValidationResult 是 dataclass 实例，含 rule_id/severity/message/field。"""
        r = ValidationResult("PC-V01", Severity.ERROR, "test", field="x")
        assert r.rule_id == "PC-V01"
        assert r.severity == Severity.ERROR
        assert r.field == "x"

    def test_context_is_fork_default_false(self):
        """ValidationContext.is_fork 默认 False。"""
        ctx = ValidationContext()
        assert ctx.is_fork is False
        assert ctx.override_keys == []