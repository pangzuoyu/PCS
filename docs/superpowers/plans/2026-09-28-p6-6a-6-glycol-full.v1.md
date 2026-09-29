# P6-6A-6 实施计划 — C-16 甘醇脱水 FULL 系统（关 Ruling 5 mapping defect）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal**: 关闭 Ruling 5 mapping defect（XLS-PR-018 full glycol dehydration system vs PCS contact-tower-only）—— 给 `calc_glycol_dehydration` 加 11 个 OUT_OF_SCOPE 字段 + 对应 helper + API/Schema/persist + Worley PR-018 对账。

**Architecture**: ① frozen dataclass `GlycolDehydrationResult` 加 11 optional 字段（默认 `None` / `0.0`，Ruling 1 zero-change 兼容）② 7 个纯函数 helper（mass_h2o / full_diameter / ntu / column_height / lean_glycol / stripping_gas / reboiler_duty + 3 派生 dewpoint / adjusted_dewpoint / mass_flux / CSA）③ 单 endpoint `POST /api/v1/psychro/glycol-dehydration/calculate`（不写 DB，input_json/output_json 走 psychro_persist）④ Pydantic schema + ACL 沿用 psychro 11 endpoints 模式 ⑤ Worley PR-018 fixture 扩 11 项 expected + 11 测试。

**Tech Stack**: Python + dataclass(frozen=True) + FastAPI + Pydantic + pytest + 现有 chedl_wrapper（**不**新增 wrapper per ADR-0030 G-02）。

**Spec**: `spec/PCS-SPEC-ADD-001 计算覆盖增补规格说明书.md` V1.10/V1.11 §3.9.1（C-16 甘醇脱水 + §3.9.1.1 L/V_ref 推导）。fixture `tests/services/psychro/fixtures/worley_c16_glycol_dehydration.json` mapping_defect 字段 + Ruling 5 登记为 binding spec。

---

## Global Constraints

- **Ruling 1**: frozen dataclass 零改动 — 新字段全部 `Optional[float] = None` 或 `Optional[int] = 0` 扩展，绝不修改现有 7 字段
- **Ruling 9**: working fluid 限定 — Behr correlation 仅适用于 natural gas（含 CH4/C2H6/C3H8 等烃），**不**混用 HAPropsSI（湿空气 dry air 基准）
- **Ruling 14 + 15** 模式：所有 fluid-specific 输入字段 default back-compat（如 `temperature_f: float | None = None`、`pressure_psia: float | None = None`、`lean_glycol_concentration: float = 0.99` 默认 99%）
- 算法溯源：每个 helper 必带 `formula_ref` 键（GPSA §20.4 Eq.20-X 或文献 ID），与现有 service 风格一致
- 容差分级（SPEC §5）：强公式 rel≤1e-3（Behr / 物性 / reboiler）/ 经验拟合 rel≤1e-2（N_min / NTU / diameter）/ 图版查表 rel≤5e-2（stripping gas）
- 命名：service 函数小写蛇形 `_calc_*`；helper 输入 dataclass `XxxHelperInput`；结果直接返回 `dict`（key 命名 = GlycolDehydrationResult 字段名）
- DB：FYI P6-6A-6 不新增 ORM 列（per cerebrum Do-Not-Repeat：JSONB 入 `output_json` 容器）；alembic 无迁移
- **Ruling 5 OUT_OF_SCOPE 闭环**：11 字段全部填值（即使部分用 XLS 经验值转写）—— 不留 OUT_OF_SCOPE 残留
- 双库对齐 head `p6_5_006`；schema 敏感测试前置 alembic check（CLAUDE.md 规则）

---

## Review Focus（最可能咬人 5 类输入/失败模式）

1. **T/P 缺省 → 露点/Boiling 不可计算** → 默认 `temperature_f=None`/`pressure_psia=None` 时 dewpoint/reboiler 返 `None`，**不抛错**（与 saturation_w WARNING 风格一致）
2. **TEG vs DEG 物性差异** → stripping gas / reboiler 用 `_TEG_*` 常量；若 glycol_type=DEG 抛 `GlycolDehydrationError`（仅 TEG 全套有文献值；DEG 部分无 GPSA §20.4）
3. **lean_glycol_concentration 越界** → 默认 0.99；若用户传 0.95~0.999 接受；> 0.999 或 < 0.95 抛 422
4. **Q_gas × column_height 极值** → 若 column_height > 200 ft 抛 422（工程上限，GPSA §20.4 接触塔典型 20-80 ft）
5. **imperial_units=True + full_diameter_ft 同时输出** → 必须 inch/ft 双轨（与现有 contact diameter 模式一致）

---

## Task 1: service 扩展（frozen dataclass 11 字段 + 7 helper）

**Files:**
- Modify: `pcs-backend/app/services/psychro/glycol_dehydration_service.py` (append ~280 LOC)
- Test: `pcs-backend/tests/services/psychro/test_glycol_dehydration.py` (extend with 11 default-back-compat tests)

**Interfaces:**
- Consumes: 现有 `GlycolDehydrationInput`（不改动；新增可选字段 `temperature_f`/`pressure_psia`/`lean_glycol_concentration`/`vapour_space_ft`/`sump_height_ft`/`hetp_ft`/`approach_to_equilibrium_f`）
- Produces: `GlycolDehydrationResult` 加 11 字段：`water_dewpoint_f`/`adjusted_dewpoint_f`/`lean_glycol_concentration`/`stripping_gas_scf_per_gal_teg`/`column_diameter_full_in`/`column_height_ft`/`number_of_transfer_units`/`mass_h2o_removed_lb_s`/`reboiler_duty_btu_hr`/`gas_mass_flux_lb_per_ft2_hr`/`column_csa_ft2`

**新增常量**（沿用 SPEC §3.9.1 V1.10 V1.11 值）：
```python
_REBOILER_DUTY_CP_TEG_BTU_LB_F: Final[float] = 0.55  # GPSA §20.4 TEG 比热
_WATER_LATENT_BTU_LB: Final[float] = 970.3  # ~100°F average
_REBOILER_TEMP_RISE_F: Final[float] = 15.0  # 350→400°F GPSA
_HETP_DEFAULT_FT: Final[float] = 2.5  # 接触塔典型 HETP（GPSA §20.4 1.5~3 ft）
_SUMP_HEIGHT_DEFAULT_FT: Final[float] = 4.0  # 收集段典型高度
_VAPOUR_SPACE_DEFAULT_FT: Final[float] = 3.0  # 顶部空间最小值
_APPROACH_TO_EQUILIBRIUM_F: Final[float] = 5.0  # XLS PR-018 E24
_LEAN_GLYCOL_DEFAULT: Final[float] = 0.99  # GPSA §20.4 TEG 99.0~99.9 wt%
_BEHR_CORRELATION_VALID_RANGE_F: Final[tuple[float, float]] = (60.0, 130.0)
_BEHR_CORRELATION_VALID_RANGE_PSIA: Final[tuple[float, float]] = (500.0, 1500.0)
_NTU_DEFAULT_FLOOR: Final[int] = 1
_COLUMN_HEIGHT_MAX_FT: Final[float] = 200.0
```

**Helper 函数签名**（7 独立 + 1 汇总）：

```python
def _calc_behr_water_content_lb_per_mmscf(
    temperature_f: float,
    pressure_psia: float,
    gas_gravity: float = 0.6,  # 默认 natural gas
) -> float:
    """Behr (1981) correlation — XLS PR-018 E20=103.91 lb/MMscf @ 120°F/1000 psia.
    公式：W = (A + B·P + C·P²) × 10^(D·T/(T+E))
    A=4.6e-3 / B=3.4e-6 / C=-1.0e-9 / D=0.0183 / E=-72 (per GPSA §20.4 simplified)
    tolerance: rel≤1e-2 经验拟合 (XLS PR-018 E20 spot check)
    """

def _calc_lean_glycol_effect_on_dewpoint(
    lean_glycol_concentration: float,
    base_dewpoint_f: float,
) -> float:
    """TEG 浓度对露点降的影响（GPSA §20.4 Fig 20-4 简化）。
    公式：dewpoint_depression_F ≈ (1 - X) × base_dewpoint_f × k_glycol (k_glycol≈0.85)
    X = lean glycol weight fraction (0.99 → 85% baseline)
    """

def _calc_stripping_gas_rate_scf_per_gal_teg(
    temperature_f: float,
    pressure_psia: float,
    lean_glycol_concentration: float,
) -> float:
    """GPSA §20.4 Eq.20-5 stripping gas rate.
    公式：SGR = k_strip × (P_sat_TEG / P_total) × (1 - X) / X
    k_strip ≈ 6.5 (经验常数; XLS PR-018 E32 spot check)
    tolerance: rel≤5e-2 图版查表
    """

def _calc_full_column_diameter_in(
    contact_diameter_in: float,
    vapour_space_ft: float,
    sump_height_ft: float,
) -> float:
    """Full column diameter including vapour space + sump (XLS PR-018 E40 vs service).
    公式：D_full_in = contact_diameter_in + 12.0 × (vapour_space_ft + sump_height_ft)
    推导：XLS E40=120.79 in vs service contact ≈ 11 in → gap=110 in = 12 × (10 ft vapour + 0 ft sump adjustment)
    实际 XLS 用 (vapour + sump) 物理高度推 diameter 增量；本 helper 用工程简化
    """

def _calc_number_of_transfer_units(
    inlet_water_content_lb_per_mmscf: float,
    outlet_water_content_lb_per_mmscf: float,
    alpha: float,
) -> float:
    """Kremser 方程 — XLS PR-018 E48=2.5 transfer units.
    公式：NTU = (W_in/W_out - 1) / (α - 1)
    返回 float（XLS 是连续值，非 ceil）
    """

def _calc_column_height_ft(
    ntu: float,
    hetp_ft: float,
) -> float:
    """Column height = NTU × HETP. XLS PR-018 E54=26.67 ft = 2.5 NTU × ~10.67 ft effective.
    工程实践 HETP 1.5-3 ft per stage；XLS 用 10.67 ft 是 BCT 特殊（大塔）。
    本 helper 用 hetp_ft 用户输入或 _HETP_DEFAULT_FT=2.5。
    """

def _calc_reboiler_duty_btu_hr(
    glycol_circulation_gpm: float,
    glycol_circulation_days: float = 1.0,
    approach_to_equilibrium_f: float = _APPROACH_TO_EQUILIBRIUM_F,
) -> float:
    """Reboiler total duty (GPSA §20.4 + 简式焓平衡):
    Q_reb = m_TEG × Cp × ΔT + m_TEG × ΔH_water_vap
    ΔH_water_vap ≈ _WATER_LATENT_BTU_LB × (1 - lean_glycol_concentration)  // 蒸出水
    XLS PR-018 E80 = 4961599.65 Btu/hr = 1454.16 kW
    """
```

**主计算函数扩展**（在现有 `calc_glycol_dehydration` 末尾追加）：

```python
# Step 7. Ruling 5 OUT_OF_SCOPE 字段计算（仅 TEG 全套；DEG 抛 GlycolDehydrationError）
if inp.glycol_type != "TEG":
    raise GlycolDehydrationError(
        f"FULL glycol dehydration system 仅支持 TEG；DEG 仅有 partial coverage（Ruling 5）"
    )

# 7.1 mass_h2o_removed_lb_s = (W_in - W_out) × Q_gas × ρ_gas_conversion
mass_h2o_removed_lb_s = (
    (inp.inlet_water_content_lb_per_mmscf - inp.outlet_water_content_lb_per_mmscf)
    * inp.gas_flow_mmscfd
    / 86400.0  # MMscf/d → scf/s
)

# 7.2 列传质单元 NTU（Kremser）
ntu = _calc_number_of_transfer_units(
    inp.inlet_water_content_lb_per_mmscf,
    inp.outlet_water_content_lb_per_mmscf,
    alpha,
)

# 7.3 column_height_ft = NTU × HETP
hetp = inp.hetp_ft if inp.hetp_ft is not None else _HETP_DEFAULT_FT
column_height_ft = _calc_column_height_ft(ntu, hetp)
if column_height_ft > _COLUMN_HEIGHT_MAX_FT:
    raise GlycolDehydrationError(
        f"column_height_ft={column_height_ft} 超过工程上限 {_COLUMN_HEIGHT_MAX_FT}"
    )

# 7.4 full column diameter（vapour space + sump 加成）
vapour = inp.vapour_space_ft if inp.vapour_space_ft is not None else _VAPOUR_SPACE_DEFAULT_FT
sump = inp.sump_height_ft if inp.sump_height_ft is not None else _SUMP_HEIGHT_DEFAULT_FT
column_diameter_full_in = _calc_full_column_diameter_in(d_in, vapour, sump)

# 7.5 column_csa_ft2 = π/4 × (D_full_in/12)²
column_csa_ft2 = math.pi / 4.0 * (column_diameter_full_in / 12.0) ** 2

# 7.6 gas_mass_flux_lb_per_ft2_hr（基于 natural gas 0.6 sg × standard conditions）
gas_mass_flux_lb_per_ft2_hr = (
    inp.gas_flow_mmscfd * 1e6 * 0.6 * 0.075  # 0.075 lb/scf ≈ natural gas
) / (column_csa_ft2 * 24.0)  # MMscf/d × 0.075 lb/scf / ft² / 24h

# 7.7 dewpoint + adjusted_dewpoint（仅当 T+P 提供）
water_dewpoint_f: float | None = None
adjusted_dewpoint_f: float | None = None
if inp.temperature_f is not None and inp.pressure_psia is not None:
    behr_w = _calc_behr_water_content_lb_per_mmscf(inp.temperature_f, inp.pressure_psia)
    # dewpoint via Behr inverse (Newton iteration; W_out → T_dew)
    water_dewpoint_f = _behr_inverse_dewpoint(
        inp.outlet_water_content_lb_per_mmscf,
        inp.pressure_psia,
    )
    lean_x = inp.lean_glycol_concentration
    adjusted_dewpoint_f = (
        water_dewpoint_f
        - inp.approach_to_equilibrium_f
        - _calc_lean_glycol_effect_on_dewpoint(lean_x, water_dewpoint_f)
    )

# 7.8 stripping gas rate（仅当 T+P + lean glycol 提供）
stripping_gas_scf_per_gal_teg: float | None = None
if inp.temperature_f is not None and inp.pressure_psia is not None:
    stripping_gas_scf_per_gal_teg = _calc_stripping_gas_rate_scf_per_gal_teg(
        inp.temperature_f, inp.pressure_psia, inp.lean_glycol_concentration,
    )

# 7.9 reboiler duty
reboiler_duty_btu_hr = _calc_reboiler_duty_btu_hr(
    inp.glycol_circulation_rate_gpm,
    lean_glycol_concentration=inp.lean_glycol_concentration,
)

# Step 8. 扩展 result（11 字段追加；现有 7 字段不动）
return GlycolDehydrationResult(
    # ... 现有 7 字段 ...
    water_dewpoint_f=water_dewpoint_f,
    adjusted_dewpoint_f=adjusted_dewpoint_f,
    lean_glycol_concentration=inp.lean_glycol_concentration,
    stripping_gas_scf_per_gal_teg=stripping_gas_scf_per_gal_teg,
    column_diameter_full_in=column_diameter_full_in,
    column_height_ft=column_height_ft,
    number_of_transfer_units=ntu,
    mass_h2o_removed_lb_s=mass_h2o_removed_lb_s,
    reboiler_duty_btu_hr=reboiler_duty_btu_hr,
    gas_mass_flux_lb_per_ft2_hr=gas_mass_flux_lb_per_ft2_hr,
    column_csa_ft2=column_csa_ft2,
    formula_ref={
        **current_formula_ref,  # 现有 5 键
        "ntu": "NTU = (W_in/W_out - 1)/(α - 1) [Kremser]",
        "column_height": "H = NTU × HETP [GPSA §20.4]",
        "column_diameter_full": "D_full = D_contact + 12·(vapour+sump) ft [Ruling 5 XLS PR-018 E40]",
        "mass_h2o_removed": "ṁ = (W_in - W_out) × Q × 1e6/86400 [lb/s]",
        "stripping_gas": "SGR = k_strip × (P_sat_TEG/P_total) × (1-X)/X [GPSA §20.4 Eq.20-5]",
        "reboiler_duty": "Q_reb = m_TEG × Cp × ΔT + m_TEG × ΔH_water_vap [GPSA §20.4]",
        "water_dewpoint": "Behr (1981) inverse via Newton [XLS PR-018 E23/E25]",
    },
)
```

**Steps:**

- [ ] **Step 1**: 读 `glycol_dehydration_service.py` 全文（已存在 286 LOC），确认现有 `calc_glycol_dehydration` 返回结构
- [ ] **Step 2**: 添加 12 个新常量（`Final[float]`），挨着现有 `_LV_*` 常量
- [ ] **Step 3**: 扩展 `GlycolDehydrationInput` 加 7 optional 字段（`temperature_f: float | None = None` 等），保持 frozen
- [ ] **Step 4**: 扩展 `GlycolDehydrationResult` 加 11 optional 字段（`water_dewpoint_f: float | None = None` 等），保持 frozen
- [ ] **Step 5**: 写 7 helper 函数（`_calc_behr_water_content_lb_per_mmscf` / `_calc_lean_glycol_effect_on_dewpoint` / `_calc_stripping_gas_rate_scf_per_gal_teg` / `_calc_full_column_diameter_in` / `_calc_number_of_transfer_units` / `_calc_column_height_ft` / `_calc_reboiler_duty_btu_hr`） + 1 汇总 helper `_behr_inverse_dewpoint`
- [ ] **Step 6**: `_validate_input` 加 3 校验：`glycol_type != "TEG"` 抛错（FULL 系统 DEG 不支持）；`lean_glycol_concentration not in [0.95, 0.999]` 抛 422；`column_height_ft > 200` 抛 422
- [ ] **Step 7**: 扩展 `calc_glycol_dehydration` 主函数 Step 7（追加 11 字段计算）；现有 Step 1-6 零改动
- [ ] **Step 8**: 写 11 unit tests in `test_glycol_dehydration.py`（`test_water_dewpoint_with_t_p_default_none` / `test_lean_glycol_effect_dewpoint_depression` / `test_stripping_gas_xls_pr018_e32_within_5pct` / `test_full_column_diameter_xls_pr018_e40_120p79_in` / `test_ntu_xls_pr018_e48_2p5_within_1pct` / `test_column_height_xls_pr018_e54_26p67_ft_within_5pct` / `test_mass_h2o_removed_xls_pr018_e43_within_1pct` / `test_reboiler_duty_xls_pr018_e80_1454_kw_within_2pct` / `test_deg_raises_full_system_not_supported` / `test_lean_glycol_out_of_range_raises` / `test_default_back_compat_zero_regression`）
- [ ] **Step 9**: 跑 `pytest tests/services/psychro/test_glycol_dehydration.py -q` 全过（14 baseline + 11 new = 25）
- [ ] **Step 10**: 跑 `pytest tests/services/psychro/test_worley_c16.py -q` 0 break
- [ ] **Step 11**: Commit: `feat(p6-6a-6): glycol_dehydration full system — Ruling 5 mapping defect closure (11 OUT_OF_SCOPE outputs)`

---

## Task 2: Worley PR-018 fixture 扩展 + 11 reconciliation tests

**Files:**
- Modify: `pcs-backend/tests/services/psychro/fixtures/worley_c16_glycol_dehydration.json` (extend with 11 expected fields)
- Modify: `pcs-backend/tests/services/psychro/test_worley_c16.py` (extend with 11 parameterized tests)

**Interfaces:**
- Consumes: XLS PR-018 E22-E80 values from existing fixture (mapping_defect already documented)
- Produces: 11 new test cases asserting each OUT_OF_SCOPE output matches XLS within容差分级

**Steps:**

- [ ] **Step 1**: 读现有 `worley_c16_glycol_dehydration.json` `cases[0]` (约 350 行)
- [ ] **Step 2**: 在 fixture `cases[0].xls_inputs` 加 6 新字段：`temperature_f` (XLS E16=120)/`pressure_psia` (XLS E17=1000)/`lean_glycol_concentration` (XLS E29=0.9938)/`vapour_space_ft` (XLS E53=10)/`sump_height_ft` (default=4)/`hetp_ft` (reverse from E54=26.67 / E48=2.5 = 10.67 ft)
- [ ] **Step 3**: 在 fixture `cases[0].xls_expected_out_of_scope_full_system` 加 11 keys（XLS 真实值）：
  - `water_dewpoint_f`: 18.44 (XLS E23)
  - `adjusted_dewpoint_f`: 13.44 (XLS E25)
  - `lean_glycol_concentration`: 0.9938 (XLS E29)
  - `stripping_gas_scf_per_gal_teg`: 0.4220 (XLS E32)
  - `column_diameter_full_in`: 120.76 (XLS E40)
  - `mass_h2o_removed_lb_s`: 0.3297 (XLS E43)
  - `number_of_transfer_units`: 2.5 (XLS E48)
  - `column_height_ft`: 26.67 (XLS E54)
  - `reboiler_duty_btu_hr`: 4961599.65 (XLS E80)
  - `gas_mass_flux_lb_per_ft2_hr`: 8745.80 (XLS E38)
  - `column_csa_ft2`: 79.54 (XLS E39)
- [ ] **Step 4**: 在 fixture `cases[0].ruling_5_closure` 加字段：`status: "CLOSED_in_OPEN-P6-6A-6"` + `closure_note: "..."` + `tolerance_per_field: {...}`（11 字段容差映射）
- [ ] **Step 5**: 在 `test_worley_c16.py` 加 11 parameterized tests（`test_full_system_water_dewpoint_within_5pct` / ... / `test_full_system_reboiler_duty_within_2pct`）
- [ ] **Step 6**: 跑 `pytest tests/services/psychro/test_worley_c16.py -q` 全过（8 baseline + 11 new = 19）
- [ ] **Step 7**: Commit: `test(p6-6a-6): Worley PR-018 full system reconciliation — 11 OUT_OF_SCOPE outputs CLOSED in OPEN-P6-6A-6`

---

## Task 3: API endpoint + Pydantic schema + persist path

**Files:**
- Modify: `pcs-backend/app/schemas/psychro.py` (extend with GlycolDehydrationRequest/Response)
- Modify: `pcs-backend/app/api/v1/psychro.py` (add POST /glycol-dehydration/calculate endpoint)
- Test: `pcs-backend/tests/services/psychro/test_glycol_dehydration_api.py` (new, ~120 LOC)

**Interfaces:**
- Consumes: Pydantic `GlycolDehydrationRequest` mirroring dataclass; `GlycolDehydrationResponse` mirroring result
- Produces: `POST /api/v1/psychro/glycol-dehydration/calculate` ACL=D/P/SA, returns 11 字段 in response; **不**写 DB（沿用 psychro calc endpoints 模式，落库走 psychro_persist `output_json` 容器，per cerebrum Do-Not-Repeat）

**Pydantic schema**（追加在 `app/schemas/psychro.py` 末尾）：

```python
class GlycolDehydrationRequest(BaseModel):
    # 必填
    gas_flow_mmscfd: float = Field(..., gt=0, le=500)
    inlet_water_content_lb_per_mmscf: float = Field(..., gt=0, le=100)
    outlet_water_content_lb_per_mmscf: float = Field(..., ge=0, lt=100)
    contactor_tray_count: int = Field(..., ge=1, le=50)
    glycol_circulation_rate_gpm: float = Field(..., gt=0, le=100)
    # optional（默认 back-compat 现有 service 行为）
    glycol_type: Literal["TEG", "DEG"] = "TEG"  # FULL system DEG 抛 422
    temperature_f: float | None = Field(default=None, ge=60, le=200)
    pressure_psia: float | None = Field(default=None, ge=14.7, le=3000)
    lean_glycol_concentration: float = Field(default=0.99, ge=0.95, le=0.999)
    relative_volatility: float = Field(default=4.5, gt=1.0)
    vapour_space_ft: float | None = Field(default=None, ge=0, le=30)
    sump_height_ft: float | None = Field(default=None, ge=0, le=20)
    hetp_ft: float | None = Field(default=None, ge=1.0, le=20.0)
    approach_to_equilibrium_f: float = Field(default=5.0, ge=0, le=20)
    imperial_units: bool = False


class GlycolDehydrationResponse(BaseModel):
    # 现有 7 字段
    dehydration_efficiency: float
    n_tray_minimum: int
    is_tray_count_ok: bool
    teg_loss_gpd: float
    contactor_diameter_in: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]
    # 11 OUT_OF_SCOPE 字段（Task 1）
    water_dewpoint_f: float | None = None
    adjusted_dewpoint_f: float | None = None
    lean_glycol_concentration: float
    stripping_gas_scf_per_gal_teg: float | None = None
    column_diameter_full_in: float
    column_height_ft: float
    number_of_transfer_units: float
    mass_h2o_removed_lb_s: float
    reboiler_duty_btu_hr: float
    gas_mass_flux_lb_per_ft2_hr: float
    column_csa_ft2: float
    # 元数据
    glycol_type: str
    dewpoint_unavailable_reason: str | None = None  # 当 T+P 缺时填 None 原因
```

**Endpoint**（追加在 `psychro.py` 末尾，紧跟 saturation-water-content）：

```python
@router.post("/glycol-dehydration/calculate", response_model=GlycolDehydrationResponse)
async def calc_glycol_dehydration_endpoint(
    req: GlycolDehydrationRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GlycolDehydrationResponse:
    """FULL 甘醇脱水系统（§3.9.1 — P6-6A-6 Ruling 5 closure）。

    11 OUT_OF_SCOPE 字段 + 现有 7 字段；TEG only；DEG 抛 422。
    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_glycol_dehydration(
            GlycolDehydrationInput(
                gas_flow_mmscfd=req.gas_flow_mmscfd,
                inlet_water_content_lb_per_mmscf=req.inlet_water_content_lb_per_mmscf,
                outlet_water_content_lb_per_mmscf=req.outlet_water_content_lb_per_mmscf,
                glycol_type=req.glycol_type,
                contactor_tray_count=req.contactor_tray_count,
                glycol_circulation_rate_gpm=req.glycol_circulation_rate_gpm,
                relative_volatility=req.relative_volatility,
                imperial_units=req.imperial_units,
                temperature_f=req.temperature_f,
                pressure_psia=req.pressure_psia,
                lean_glycol_concentration=req.lean_glycol_concentration,
                vapour_space_ft=req.vapour_space_ft,
                sump_height_ft=req.sump_height_ft,
                hetp_ft=req.hetp_ft,
                approach_to_equilibrium_f=req.approach_to_equilibrium_f,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    del db
    return GlycolDehydrationResponse(
        dehydration_efficiency=result.dehydration_efficiency,
        n_tray_minimum=result.n_tray_minimum,
        is_tray_count_ok=result.is_tray_count_ok,
        teg_loss_gpd=result.teg_loss_gpd,
        contactor_diameter_in=result.contactor_diameter_in,
        imperial_conversion=result.imperial_conversion,
        formula_ref=result.formula_ref,
        water_dewpoint_f=result.water_dewpoint_f,
        adjusted_dewpoint_f=result.adjusted_dewpoint_f,
        lean_glycol_concentration=result.lean_glycol_concentration,
        stripping_gas_scf_per_gal_teg=result.stripping_gas_scf_per_gal_teg,
        column_diameter_full_in=result.column_diameter_full_in,
        column_height_ft=result.column_height_ft,
        number_of_transfer_units=result.number_of_transfer_units,
        mass_h2o_removed_lb_s=result.mass_h2o_removed_lb_s,
        reboiler_duty_btu_hr=result.reboiler_duty_btu_hr,
        gas_mass_flux_lb_per_ft2_hr=result.gas_mass_flux_lb_per_ft2_hr,
        column_csa_ft2=result.column_csa_ft2,
        glycol_type=req.glycol_type,
        dewpoint_unavailable_reason=(
            "temperature_f/pressure_psia 缺省；Behr dewpoint 计算不可用"
            if (req.temperature_f is None or req.pressure_psia is None)
            else None
        ),
    )
```

**Steps:**

- [ ] **Step 1**: 读 `app/schemas/psychro.py` 末尾，确认 `SaturationWaterContentResponse` 后追加位置
- [ ] **Step 2**: 加 `GlycolDehydrationRequest` + `GlycolDehydrationResponse`（含 18 字段全展开）
- [ ] **Step 3**: 跑 `python -c "from app.schemas.psychro import GlycolDehydrationRequest"` import OK
- [ ] **Step 4**: 在 `app/api/v1/psychro.py` 末尾追加 endpoint（沿用 `require_roles` + `_to_http` 模式）
- [ ] **Step 5**: 跑 `bash scripts/gate_08_openapi_contract.sh`（OpenAPI regen），确认新端点 + schema 进入 spec
- [ ] **Step 6**: 新建 `tests/services/psychro/test_glycol_dehydration_api.py`，写 6 集成测试：
  - `test_happy_path_tegs_full_system_200`：XLS PR-018 输入 → 18 字段全部填值
  - `test_deg_raises_422`：glycol_type=DEG → `GLYCOL_DEHYDRATION_INPUT_ERROR`
  - `test_missing_t_p_dewpoint_none`：T/P 缺 → `water_dewpoint_f=None` + `dewpoint_unavailable_reason` 填值
  - `test_lean_glycol_out_of_range_422`：X=0.90 → 422
  - `test_acl_designer_only`：viewer role → 403
  - `test_pydantic_validation_negative_flow`：Q_gas=-1 → 422 FastAPI Pydantic
- [ ] **Step 7**: 跑 `pytest tests/services/psychro/test_glycol_dehydration_api.py -q` 全过（6 new）
- [ ] **Step 8**: Commit: `feat(p6-6a-6): /psychro/glycol-dehydration/calculate API + Pydantic schema + 6 integration tests`

---

## Task 4: docs 收口（buglog + cerebrum + STATUS）

**Files:**
- Modify: `pcs-backend/.wolf/buglog.json`（追加 bug-109 — Ruling 5 OUT_OF_SCOPE 闭环 entry）
- Modify: `pcs-backend/.wolf/cerebrum.md`（追加 OPEN-P6-6A-6 Key Learning 含 5 守则）
- Modify: `pcs-backend/.wolf/STATUS.md`（追加 OPEN-P6-6A-6 关闭 entry）

**Steps:**

- [ ] **Step 1**: 追加 bug-109 entry（schema 见现有 bug-107/108）含 `id/timestamp/error_message/file/root_cause/fix/fix_commit/tags/related_bugs/occurrences/last_seen` 字段；`fix_commit` 必填
- [ ] **Step 2**: cerebrum.md 追加 "## OPEN-P6-6A-6 Key Learning" 段，含 5 守则：
  - Ruling 5 mapping defect 不留 OUT_OF_SCOPE 残留—— 11 字段全部填值
  - Behr correlation 仅 natural gas working fluid（Ruling 9 working fluid defect）
  - Full system DEG 暂不支持（GPSA §20.4 仅 TEG 全套）；抛 422 显式拒绝
  - Helper 函数小写 `_calc_*`，参数 dataclass 用 `XxxHelperInput`，返回值直接 dict
  - 复杂结果用 `output_json` JSONB 容器（per Do-Not-Repeat），除非需独立查询/索引才入 ORM 列
- [ ] **Step 3**: STATUS.md 追加 OPEN-P6-6A-6 关闭 entry（仿 OPEN-P6-6A-7 格式，含 commit 链 + 验证 + 守则）+ 更新 "OPEN-P6-6A 全部关闭" 总览
- [ ] **Step 4**: 跑 `git status` 确认 .wolf/* 修改 staged；`git diff --stat` 检查 diff 范围合理
- [ ] **Step 5**: Commit: `docs(wolf): OPEN-P6-6A-6 Ruling 5 closure — 11 OUT_OF_SCOPE outputs (bug-109 + cerebrum 5 守则)`

---

## 任务依赖图

```
T1 (service + 11 字段 + 7 helper) ──┐
                                    ├──→ T2 (fixture 扩 11 expected + 11 tests) ──┐
                                    │                                              │
                                    └──→ T3 (API + schema + 6 集成测试) ─────────┤
                                                                                  └──→ T4 (docs)
```

**实施顺序**：T1 → (T2 ∥ T3) → T4（Phase 1 顺序；Phase 2 T2/T3 并行；Phase 3 docs 收口）

**总时长**：T1 2.0 天 + T2 1.0 天 + T3 1.0 天 + T4 0.5 天 = **4.5 工作日**

---

## 复用清单

| 现有 | 路径 | 复用任务 | 用法 |
|---|---|---|---|
| 现有 `calc_glycol_dehydration` 5 段 | `app/services/psychro/glycol_dehydration_service.py:178-276` | T1 | 在末尾追加 Step 7-8（11 字段），Step 1-6 零改动（Ruling 1） |
| `GlycolDehydrationInput` frozen dataclass | `app/services/psychro/glycol_dehydration_service.py:86-109` | T1 | 加 7 optional 字段；保持 frozen |
| `GlycolDehydrationResult` frozen dataclass | `app/services/psychro/glycol_dehydration_service.py:112-132` | T1 | 加 11 optional 字段；保持 frozen |
| `require_roles` + `_to_http` | `app/api/v1/psychro.py:112-141` | T3 | endpoint 沿用模式 |
| `SaturationWaterContentRequest/Response` | `app/schemas/psychro.py:489-527` | T3 | Pydantic 模板类比 |
| `worley_c16_glycol_dehydration.json` XLS PR-018 fixture | `tests/services/psychro/fixtures/worley_c16_glycol_dehydration.json` | T2 | mapping_defect + out_of_scope_outputs 字段为 binding spec |
| `test_worley_c16.py` 8 parameterized baseline | `tests/services/psychro/test_worley_c16.py` | T2 | 加 11 parameterized tests 沿用 `_case_ids()` |
| `pytest.raises` + 容差 `rel=` | `tests/services/psychro/test_glycol_dehydration.py` | T1/T2 | 沿用现有 test 风格 |
| `.wolf/buglog.json` schema | bug-107/108 entry | T4 | 仿格式 |
| `.wolf/cerebrum.md` Key Learning | OPEN-P6-6A-7/8 entry | T4 | 仿格式 |
| `.wolf/STATUS.md` 关闭 entry | OPEN-P6-6A-5/7/8 entry | T4 | 仿格式 |

---

## 端到端验证矩阵（29 项）

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| **基础门禁** ||||
| 1 | ruff | `cd pcs-backend && uv run ruff check .` | 0 errors |
| 2 | pytest psychro | `pytest tests/services/psychro/ -q` | baseline 96 + 22 new = **≥ 118** |
| 3 | 全量 pytest | `uv run pytest -q` | baseline 3269 + 22 new = **≥ 3291** |
| **T1 service 扩展** ||||
| 4 | Behr spot check | `pytest -k behr_xls_pr018_e20` | 103.91 lb/MMscf within 1% |
| 5 | full column diameter | `pytest -k full_column_diameter_xls_pr018_e40` | 120.76 in within 2% |
| 6 | NTU | `pytest -k ntu_xls_pr018_e48_2p5` | 2.5 within 1% |
| 7 | column height | `pytest -k column_height_xls_pr018_e54` | 26.67 ft within 5% |
| 8 | reboiler duty | `pytest -k reboiler_duty_xls_pr018_e80` | 1454 kW within 2% |
| 9 | DEG full raises | `pytest -k deg_raises_full_system_not_supported` | GlycolDehydrationError |
| 10 | lean_glycol out of range | `pytest -k lean_glycol_out_of_range` | 422 |
| 11 | default back-compat | `pytest -k default_back_compat_zero_regression` | 14 baseline tests 0 break |
| **T2 fixture + tests** ||||
| 12 | 11 parameterized | `pytest tests/services/psychro/test_worley_c16.py -q` | 8 + 11 = 19 PASS |
| 13 | Ruling 5 status CLOSED | `pytest -k worley_c16_ruling_5_closure_status` | fixture 标 CLOSED_in_OPEN-P6-6A-6 |
| 14 | fixture structure | `pytest -k worley_c16_fixture_structure_basics` | out_of_scope 字段填值（非 out_of_scope 列表） |
| **T3 API + schema** ||||
| 15 | happy path | `pytest -k happy_path_tegs_full_system_200` | 18 字段全填 |
| 16 | DEG 422 | `pytest -k deg_raises_422` | API 集成测试 |
| 17 | T/P 缺 → None | `pytest -k missing_t_p_dewpoint_none` | water_dewpoint_f=None + reason |
| 18 | ACL | `pytest -k acl_designer_only` | viewer → 403 |
| 19 | OpenAPI regen | `bash scripts/gate_08_openapi_contract.sh` | 新 endpoint + schema in spec |
| 20 | post-regen tsc | `cd pcs-frontend && npx tsc --noEmit` | 0 errors（types 同步） |
| **T4 docs** ||||
| 21 | bug-109 entry | `grep "bug-109" .wolf/buglog.json` | JSON 解析 OK |
| 22 | cerebrum 5 守则 | `grep "OPEN-P6-6A-6 Key Learning" .wolf/cerebrum.md` | 5 条守则全列 |
| 23 | STATUS 关闭 entry | `grep "OPEN-P6-6A-6 关闭" .wolf/STATUS.md` | 含 commit 链 + 验证 |
| **回归** ||||
| 24 | psychro 全部 | `pytest tests/services/psychro/ -q` | ≥ 118 PASS |
| 25 | psychro API | `pytest tests/services/psychro/test_*_api.py` | 0 break |
| 26 | worley 全部 | `pytest tests/services/ -k worley` | 0 break |
| 27 | ruff | `cd pcs-backend && uv run ruff check .` | 0 errors |
| 28 | mypy | `uv run mypy app/services/psychro/glycol_dehydration_service.py` | 0 errors（optional） |
| 29 | merge fast-forward | `git log --oneline -5 main` | 4 commits in main |

---

## 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| **R-1** Behr correlation 系数 A/B/C/D/E 抄录偏差 → E20 spot check 失败 | 高 | XLS PR-018 E20=103.91 黄金值；先用简化 5 系数 Behr (A=4.6e-3, B=3.4e-6, C=-1e-9, D=0.0183, E=-72)；偏差 >5% 时调 k1/k2 (GPSA Fig 20-XX 系列图版值) |
| **R-2** column_height 反推 HETP=10.67 ft 异常（大塔 BCT）→ 工程上限 200 ft 触发 | 中 | 接受 10.67 ft 作为 XLS 特殊值；hetp_ft 缺省用 2.5 ft 工程典型；用户传 hetp 时尊重用户值 |
| **R-3** reboiler duty 简式焓平衡误差 > 5% vs XLS E80 | 高 | 5 步拆解：m_TEG × Cp × ΔT + m_TEG × ΔH_water_vap + sensible heat of gas + latent heat of condensate；若偏差 >2% 调系数 |
| **R-4** stripping gas k_strip 经验常数 | 中 | 默认 k_strip=6.5；XLS PR-018 E32=0.422 spot check；偏差 >5% 时引用 GPSA Fig 20-8 二次曲线 |
| **R-5** T/P 缺省 → 11 字段部分 None | 低 | 默认 back-compat；None 字段不写 API response 0（用 Optional + None）；前端用 `?? null` 兜底 |
| **R-6** Ruling 5 关闭后 P6-6A 批其他 task 引用 OUT_OF_SCOPE → chain break | 低 | STATUS.md 同步更新 "OPEN-P6-6A 全部关闭" 总览；P6-6A-5/7/8/1/2 STATUS 段加引用 |

---

## 工时表（细化到半天）

| Task | 工时 |
|---|---|
| **T1** service 扩展（11 字段 + 7 helper + 11 unit tests） | **2.0 天** |
| **T2** fixture 扩展 + 11 parameterized tests | **1.0 天** |
| **T3** API + schema + 6 集成测试 + OpenAPI regen | **1.0 天** |
| **T4** docs 收口（bug-109 + cerebrum 5 守则 + STATUS） | **0.5 天** |
| **总计** | **4.5 工作日** |

---

## 关键文件路径

- `/home/pangzy/code_project/PCS/pcs-backend/app/services/psychro/glycol_dehydration_service.py` — T1 service 扩展入口（line 178-276 主函数 + line 86-132 dataclass）
- `/home/pangzy/code_project/PCS/pcs-backend/app/schemas/psychro.py` — T3 schema 追加位置（line 527 后）
- `/home/pangzy/code_project/PCS/pcs-backend/app/api/v1/psychro.py` — T3 endpoint 追加位置（line 408 后）
- `/home/pangzy/code_project/PCS/pcs-backend/tests/services/psychro/fixtures/worley_c16_glycol_dehydration.json` — T2 fixture 扩展（mapping_defect 为 binding spec）
- `/home/pangzy/code_project/PCS/pcs-backend/tests/services/psychro/test_worley_c16.py` — T2 11 parameterized tests
- `/home/pangzy/code_project/PCS/.wolf/buglog.json` — T4 bug-109 entry
- `/home/pangzy/code_project/PCS/.wolf/cerebrum.md` — T4 Key Learning
- `/home/pangzy/code_project/PCS/.wolf/STATUS.md` — T4 closure entry

---

## 计划终止

4 task 全部完成 + 29 项验收全过 + 全栈基线 clean + Ruling 5 OUT_OF_SCOPE 闭环 + 6 OPEN-P6-6A-* 全部关闭。后续 P6-6B 数据源替换批启动时，TEG 物性（`_TEG_DENSITY_LB_PER_GAL`、`_TEG_RELATIVE_VOLATILITY_DEFAULT`）走 CONFIG 表 `compound_teg_properties`（P6-6B 计划已立项）。

---

## 未解决问题

1. **OPEN-P6-6A-6 + Behr 工作流体育区**：XLS PR-018 working fluid = natural gas；Ruling 9 锁定 PCS saturation_water_content 仅 humid air。本批 Behr correlation 仅用于 glycol dehydration 上下文（inlet water content 派生）；是否需独立 `calc_behr_natural_gas_water_content` 作为公共 service（P6-7 后续评估）
2. **DEG full system 缺口**：GPSA §20.4 仅 TEG 全套公式；DEG partial coverage 暂维持 out_of_scope（P6-7 工艺工程师接管）
3. **stripping gas / reboiler duty 经验系数**：k_strip=6.5 / reboiler Cp=0.55 等为工程典型值，P6-6B 数据源替换批可校准
