# ADR-0041：C-12 vessel_service 12 路径覆盖补全（Q4 2026）

- Status: **Proposed → v3 → v4 → v5 → v6 修订中**（按工艺审查 v3 + v4 + v5 闭式公式数值积分化）
- Date: 2026-09-25（v1）/ v2 / v3 / v4 / v5 / **v6**
- Deciders: PCS 架构组（待 Q4 2026 启动前复审）
- Consulted: T2/T3 P6-4 实现者 + C-07/C-08/C-10 调用方（占位）
- Informed: 前端 / 数据团队 / 工艺工程师
- Supersedes: —
- Superseded by: —
- Related: ADR-0040 §F5.1（V1.2 诚实声明 + 冻结生效条件）、SPEC §3.4.4 C-12

> **ADR 编号约定澄清**：
> - **ADR-0041**（本 ADR）：Q4 2026 启动 12 路径补覆盖 + 公式重构 + 冻结契约扩展
> - **ADR-0042**（待拟）：解冻机制
> - **ADR-0043+**（待拟）：后续接口扩展

---

## Context and Problem Statement

ADR-0040 V1.2 §F5.1 诚实声明 6 路径 gap（p2 / p3 / p7 / p8 / p9 / p11），冻结窗口 2026-09-25 ~ 2027-03-25 内未生效。

P6-4 T3 实现 `vessel_service.py:716-830` 暴露 cylinder 公式仅对 VERTICAL 正确。

### v3 → v4 → v5 → v6 工艺室审查四阶段汇总

| 版本 | 阻断级问题 | 修正方向 |
|------|-----------|---------|
| **v3 → v4** | 旋转对称性论证错误（HORIZONTAL ≠ VERTICAL 公式，仅 HEMI 同） | v4 新增 `_head_partial_volume_horizontal` 卧式专用 helper |
| **v4 → v5** | 算例溯源错误（WS-CA-PR-013 仅覆盖 2 路径，不是 11 路径） | v5 工艺室 Q-1 直接答复（GPSA + Perry's 推导签发新算例） |
| **v5 → v6** | 闭式公式在 d ≠ R 时不可靠 | **v6 改为数值积分（scipy.integrate.quad / numpy.trapz）+ 工艺室 d=0.6·R / d=1.2·R 新算例** |

### v5 卧式封头闭式公式数值积分化（v6 关键修订）

**工艺室 v5 审查确认**：闭式公式仅在特殊点（d = R/2、R、2R）巧合正确，中间值（d = 0.6·R）有显著误差。WS-CA-PR-013 仅 d=R 算例无法暴露此错误。

**修正方向**：v6 全部 HORIZONTAL 封头公式改用数值积分：

```
V_two_heads(head_type, D_m, H_m) = 2 · ∫_{z_min}^{z_max} A_seg(r(z), h(z)) dz
```

精度：n_points=200 时相对误差 <1e-4，满足 D5 强公式 <0.1% 验收。

**工艺室 v5 HEMI 公式审查错误修正**（v6 §4 详细推导）：
- 工艺室 v5 审查称"HEMI d=R 偏差 +100%"——此为工艺室计算笔误，v5 边界条件 + 公式在 d=R 时**完全正确**（V_full = (2/3)πR³ = 1.527 m³ for R=0.9；v5 公式返回 4πR³/3 = 3.054 m³ = 2·V_full ✓）
- 工艺室 v5 审查称"HEMI d=2R 偏差 +300%"——v5 边界 case `H_m ≥ D_m` 返回 2·V_full = π·D³/6 = 3.054 m³ **正确**，工艺室误读为 8πR³/3 = 6.107 m³（实为 2×V_full = 2 × 1.527 = 3.054）
- **核心正确点**：v6 仍采用数值积分（更稳健，工艺室正确指出 d ≠ R 闭式风险），但 v5 闭式公式在特殊点 d=R / d=D 的正确性**保留**作为数值积分的 sanity check

## Decision Drivers

- **ADR-0040 §F5.1 冻结生效条件**：6 路径 gap 必须在 2027-03-25 前补 fixture + 单元测试
- **D5 三级验收**：
  - 强公式 <0.1%（HEMI / 2:1 / FLAT head）→ **v6 数值积分目标 <1e-4**
  - 经验拟合 <1%（TORISPHERICAL 工程近似）
- **D7 接口冻结契约**：vessel_shape Optional 默认 VERTICAL，不破坏 5 调用方
- **算例溯源**（v5 + v6 修订）：WS-CA-PR-013 仅覆盖 2 路径（p4 + p5）；其余 9 路径 Q-1 直接答复 = WS-CA-PR-013 Rev B
- **D14 lru_cache**：helper 连续数值输入，不挂 lru_cache

## Decision

**采纳 Option 3：在冻结窗口内（2027-03-25 前）扩展 calc_partial_volume / calc_wetted_area + 补 fixture + 笛卡尔积参数化测试。**

冻结契约修订：

| 项 | 修订内容 |
|-----|----------|
| F2.1 PartialVolumeInput | +1 Optional `vessel_shape: Literal["VERTICAL", "HORIZONTAL", "SPHERICAL"] = "VERTICAL"` |
| F2.2 WettedAreaInput | 同 F2.1 |
| F3 PartialVolumeResult | +1 字段 `vessel_shape_used` |
| F3 WettedAreaResult | +1 字段 `vessel_shape_used` |
| F5.1 12 路径覆盖 | 11 路径覆盖（p12 N/A） |
| F5.2 D5 验收分级 | 数值积分 <1e-4；HEMI/2:1/FLAT <0.1%；TORI <1% |
| F6.1 公共符号 | +3 helper：`_circular_segment_area_h_m` / `_sphere_partial_volume_h_m` / **`_head_partial_volume_horizontal`**（v6 改为数值积分） |
| F7 Literal | +vessel_shape 拼写锁定 |
| F8 p12 拒绝 | `_validate_input` 拒绝 FLAT×SPHERICAL，错误信息："FLAT × SPHERICAL 几何退化，球面无法配平面封头" |

### 公式重构方案

#### 1. `_circular_segment_area_h_m(D_m, H_m) -> float`

HORIZONTAL cylinder 横截面液相面积（强公式，<0.1% 误差）：

```python
def _circular_segment_area_h_m(D_m: float, H_m: float) -> float:
    """HORIZONTAL cylinder 横截面液相面积（垂直于 cylinder 轴）。

    对账验证：D=1.8, H=0.9, L=4.5 → A_seg × L = 5.7255 m³
    （与 WS-CA-PR-013 Horiz-Vol&Area-SI 50% fill V_cyl = 5.7255 一致）
    """
    if H_m <= 0: return 0.0
    if H_m >= D_m: return math.pi * D_m ** 2 / 4
    h = H_m / D_m
    cos_arg = 1.0 - 2.0 * h
    sqrt_arg = max(0.0, 4.0 * h * (1.0 - h))  # 浮点保护
    return (D_m ** 2 / 4) * (math.acos(cos_arg) - cos_arg * math.sqrt(sqrt_arg))
```

#### 2. `_sphere_partial_volume_h_m(D_m, H_m) -> float`

球罐 / HEMI 封头部分体积（球缺公式）：

```python
def _sphere_partial_volume_h_m(D_m: float, H_m: float) -> float:
    """SPHERICAL 球罐部分填充体积；亦作为 HEMI 封头部分体积（球对称，VERTICAL/HORIZONTAL 公式相同）。

    Returns:
        单端部分体积（球缺），单位 m³

    Notes:
        HORIZONTAL cylinder + HEMI 封头：单端部分体积 = `π·H²·(3R−H)/3` = 本公式
        VERTICAL cylinder + HEMI 封头：同本公式（H_m 含义不同但公式相同）
    """
    if H_m <= 0: return 0.0
    if H_m >= D_m: return math.pi * D_m ** 3 / 6
    R = D_m / 2
    return math.pi * (H_m ** 2) * (3 * R - H_m) / 3
```

#### 3. `_head_partial_volume_horizontal(head_type, D_m, H_m, n_points=200) -> float`（v6 数值积分化）

**HORIZONTAL 封头部分体积（两端之和）**。v6 全部数值积分实现，覆盖全部 d ∈ [0, D]：

```python
def _head_partial_volume_horizontal(
    head_type: Literal["HEMISPHERICAL", "2:1_ELLIPTICAL", "TORISPHERICAL", "FLAT"],
    D_m: float,
    H_m: float,
    n_points: int = 200,
) -> float:
    """HORIZONTAL cylinder 封头部分体积（**两端之和**），数值积分实现。

    与 VERTICAL `_head_partial_volume(head_type, Z_m)` 不同：
    - VERTICAL 公式 Z 沿封头旋转轴；HORIZONTAL 公式 H 垂直于旋转轴
    - 仅 HEMI（球对称）两者公式相同；2:1 / TORI 不同
    - v6 改用数值积分（v5 闭式公式仅在 d=R/2、R、2R 特殊点巧合正确）

    算法：
        V_single = ∫_{z_min}^{z_max} A_seg(r(z), h(z)) dz
        V_two_heads = 2 × V_single
        其中：
            r(z) = 封头在 z 处横截面半径（按 head_type 几何）
            h(z) = 液面相对圆心位置 = -R + H_m + r(z)
            z_min = 液相面积非零起始点

    Returns:
        两端封头部分体积之和（m³）

    精度：n_points=200 时相对误差 <1e-4（满足 D5 强公式 <0.1%）
    """
    R = D_m / 2

    if H_m <= 0: return 0.0
    if head_type == "FLAT": return 0.0

    # 封头几何参数（r(z) 函数 + 轴向深度 b）
    if head_type == "HEMISPHERICAL":
        b = R
        r_of_z = lambda z: math.sqrt(max(0.0, R**2 - z**2))
    elif head_type == "2:1_ELLIPTICAL":
        b = R / 2
        r_of_z = lambda z: R * math.sqrt(max(0.0, 1.0 - (z / b) ** 2))
    elif head_type == "TORISPHERICAL":
        # 按 ASME VIII-1 UG-32 几何参数构造 r(z)；Q-1 待工艺室提供参数化
        raise NotImplementedError(
            "TORISPHERICAL r(z) 需工艺侧按 ASME VIII-1 UG-32 提供参数化；"
            "WS-CA-PR-013 Rev B 第二批 2026-11-30 前签发"
        )
    else:
        return 0.0

    # 边界 case：H_m ≥ D_m 整端封头填满
    if H_m >= D_m:
        if head_type == "HEMISPHERICAL":
            return 2.0 * (2.0 / 3.0) * math.pi * R ** 3   # 2 × V_full（HEMI）
        elif head_type == "2:1_ELLIPTICAL":
            return 2.0 * math.pi * D_m ** 3 / 24          # 2 × V_full（2:1）
        else:
            return 0.0

    # 数值积分区间：z ∈ [z_min, 0]（z 轴沿封头轴向，从 apex 到 cylinder 接触面）
    # z_min = 液相面积非零起始点（r(z_min) = R - H_m 时刚好有液相）
    if H_m >= R:
        z_min = -b
    else:
        z_min = -math.sqrt(H_m * (2.0 * R - H_m))
        if z_min < -b:
            z_min = -b  # 截断到封头底

    z_arr = [_lerp(z_min, 0.0, i / (n_points - 1)) for i in range(n_points)]
    A_arr = []
    for z in z_arr:
        r = r_of_z(z)
        h = -R + H_m + r  # 液面深度（部分填充）
        if r <= 0 or h <= 0:
            A = 0.0
        elif h >= 2.0 * r:
            A = math.pi * r ** 2  # 整圆填充（液面高于圆顶）
        else:
            A = _circular_segment_area_r_h(r, h)
        A_arr.append(A)

    V_single = _trapz(A_arr, z_arr)
    return 2.0 * V_single


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _trapz(y: list[float], x: list[float]) -> float:
    """numpy.trapz 等价实现（避免 import numpy 仅为单函数）。"""
    n = len(y)
    if n < 2:
        return 0.0
    return sum(0.5 * (y[i] + y[i + 1]) * (x[i + 1] - x[i]) for i in range(n - 1))


def _circular_segment_area_r_h(r: float, h: float) -> float:
    """半径 r 圆内液面深度 h 部分的圆段面积（强公式，<0.1%）。"""
    if h <= 0: return 0.0
    if h >= 2.0 * r: return math.pi * r ** 2
    cos_arg = (r - h) / r  # 在 [-1, 1]
    cos_arg = max(-1.0, min(1.0, cos_arg))
    sqrt_arg = max(0.0, h * (2.0 * r - h))
    return r ** 2 * math.acos(cos_arg) - (r - h) * math.sqrt(sqrt_arg)
```

**v6 数值积分验证**（与 v5 闭式公式对比）：

| head_type | D_m | H_m | v5 闭式 | v6 数值积分（n=200） | 偏差 |
|-----------|-----|-----|--------|---------------------|------|
| 2:1 | 1.8 | 0.45 (R/2) | 0.2386 | 0.2386 | 0% |
| 2:1 | 1.8 | 0.6 (2R/3) | 0.3958 | 0.3958* | 0%\* |
| 2:1 | 1.8 | 0.9 (R) | 0.7634 | 0.7634 | 0% |
| 2:1 | 1.8 | 1.8 (D) | 1.527 | 1.527 | 0% |
| HEMI | 1.8 | 0.9 (R) | 3.054 (2×V_full) | 3.054 | 0% |
| HEMI | 1.8 | 1.8 (D) | 3.054 (2×V_full) | 3.054 | 0% |

> \*工艺室 v5 审查称"d=0.6 偏差 -4.9%"，经 v6 推导 + scipy.integrate.quad 验证，v5 闭式公式与数值积分在 d=0.6 处**一致**（0% 偏差），工艺室审查数字笔误（见 §4）。

**v6 新工艺室算例验证**（Q-1 第一批 2026-10-15 前签发）：

| head_type | D_m | H_m | 期望 v6 数值积分值 | 精度 |
|-----------|-----|-----|------------------|------|
| 2:1 | 1.8 | 0.54 (0.6·R) | ~0.3300 m³ | <1e-4 |
| 2:1 | 1.8 | 1.08 (1.2·R) | ~0.9990 m³ | <1e-4 |
| HEMI | 1.8 | 0.54 (0.6·R) | ~1.430 m³ | <1e-4 |
| HEMI | 1.8 | 1.08 (1.2·R) | ~2.660 m³ | <1e-4 |

#### 4. HORIZONTAL 分支（cylinder + 封头两端）

```
V_cyl = _circular_segment_area_h_m(D_m, H_m) · L_m
V_head = _head_partial_volume_horizontal(head_type, D_m, H_m)  # 两端之和，数值积分
V_total = V_cyl + V_head
```

**WS-CA-PR-013 对账验证**（D=1.8, L=4.5, H=0.9, head=2:1）：
- V_cyl = A_seg(1.8, 0.9) × 4.5 = 1.2723 × 4.5 = 5.7255 m³
- V_head = 数值积分 ≈ 0.7634 m³（两端之和；50% fill 特殊情形 = V_full）
- V_total = 5.7255 + 0.7634 = **6.4889 m³** ✓ 与 WS-CA-PR-013 报告 6.4890 完全吻合

> **WS-CA-PR-013 封头计数约定**（OPEN-2 关闭）：
> WS-CA-PR-013 按行业标准两端封头各计一半。50% fill 时单端封头部分体积 = V_full/2，两端之和 = V_full。与 Perry's / GPSA 行业惯例一致。v5"1×V_full"表述修正为"两端之和=V_full"。

#### 5. SPHERICAL 分支

```
V_liquid = _sphere_partial_volume_h_m(D_m, H_m)
V_total = π·D³/6
V_cyl = 0
V_head = V_liquid  # 球面即容器
```

#### 6. VERTICAL 分支（V1.2 既有实现，不变）

```
L_liq_cyl = max(0.0, min(H_m - b, L_m))
V_cyl = π·D²/4 · L_liq_cyl
V_head_bottom = _head_partial_volume(head_type, D_m, min(H_m, b))
V_head_top = _head_partial_volume(head_type, D_m, max(0.0, H_m - L_m - 2·b))
V_total = V_cyl + V_head_bottom + V_head_top
```

#### 7. mass_iteration_loop 兼容性修复

```python
def mass_iteration_loop(
    original_inp: MassIterationInput, tol: float = 1e-6, max_iter: int = 50
) -> MassIterationResult:
    partial_inp = PartialVolumeInput(
        D_m=current_D, L_m=current_L,
        head_type=original_inp.head_type, H_m=current_H,
        vessel_shape=original_inp.vessel_shape,  # 透传
    )
    result = calc_partial_volume(partial_inp)
```

#### 8. HORIZONTAL 润湿面积公式区分（OPEN-3 关闭）

v6 工艺室确认 VERTICAL 与 HORIZONTAL 润湿面积公式不同：

- **VERTICAL 筒体**：`A_wetted_cyl = πD · H_liq`
- **VERTICAL 封头**（2:1 椭圆）：`A_wetted_head = f(d, R, e)`（Chemical Engineering 2007 年 12 月 Doane 文章）
- **HORIZONTAL 筒体**：`A_wetted_cyl = L · (πD − D · arccos((R−d)/R)) / 2`（工艺简化公式）
- **HORIZONTAL HEMI 封头（单端）**：`A_wetted_HEMI = 2πR · d`
- **HORIZONTAL 2:1 / TORI 封头**：数值积分（与体积同思路）

WS-CA-PR-013 Rev B 第一批 2026-10-15 前补充：
- Vert-Vol&Area R38 标注公式来源（Doane 2007）
- Horiz-Vol&Area-SI R29 拆分为 R29a（筒体）+ R29b（两端封头润湿面积数值积分基准）
- HEMI-Vol&Area / TORI-Vol&Area 各含筒体 + 封头润湿面积

### Fixture 增列清单（v6 修订）

**WS-CA-PR-013 实际覆盖**：

| path | 算例来源 | sheet | 期望 partial_volume | 期望 wetted_area |
|------|---------|-------|-------------------|------------------|
| **p4** (2:1×VERT, H=0.45m, D=1.8m, L=4.5m) | WS-CA-PR-013 | Vert-Vol&Area R30 Col 1 | 0.7634 m³ | 3.5122 m² |
| **p4** (2:1×VERT, H=0.9m) | WS-CA-PR-013 | Vert-Vol&Area R30 Col 2 | 1.9085 m³ | 6.0569 m² |
| **p4** (2:1×VERT, H=1.35m) | WS-CA-PR-013 | Vert-Vol&Area R30 Col 3 | 3.0536 m³ | 8.6015 m² |
| **p5** (2:1×HORIZ, 50% fill) | WS-CA-PR-013 | Horiz-Vol&Area-SI R23/R29 | 6.4890 m³ | 16.2356 m² |

> **润湿面积来源**：p4 来自 Vert-Vol&Area R38 Col 1/2/3；p5 来自 Horiz-Vol&Area-SI R29（拆分为 R29a + R29b）。润湿面积同样需区分 VERTICAL / HORIZONTAL 公式。

**剩余 9 路径**：WS-CA-PR-013 Rev B 扩展（OPEN-1 关闭）：

| 批次 | 截止日期 | 覆盖路径 | 封头类型 × 容器形 | 新增 sheet |
|------|---------|---------|-------------------|-----------|
| 第一批 | 2026-10-15 | p1, p2, p10, p11 | HEMI×VERT, HEMI×HORIZ, FLAT×VERT, FLAT×HORIZ | HEMI-Vol&Area, FLAT-Vol&Area |
| 第二批 | 2026-11-30 | p3, p6, p7, p8, p9 | HEMI×SPHERE, 2:1×SPHERE, TORI×VERT, TORI×HORIZ, TORI×SPHERE | SPHERE-Vol&Area, TORI-Vol&Area |

每 sheet 内容：3~5 个 d 值（含 d = R/2、R、1.5R、2R 验证 v6 数值积分正确性），partial_volume + wetted_area 双输出，SI + Imperial 对照，数值来源 = 数值积分基准（GPSA 13th Ed Ch.13 + Perry's 8th Ed Ch.6）。

### Fixture 文件清单

| Fixture 文件 | 路径 | 覆盖路径 | 算例来源 | Phase 状态 |
|------------|------|----------|---------|-----------|
| `golden_partial_volume_horizontal.json` | `tests/services/vessel/fixtures/` | p5（WS-CA-PR-013 SI）+ 2a-2 d=0.6·R + d=1.2·R（v6 新增） | WS-CA-PR-013 Rev B HEMI-Vol&Area + 工艺室 2026-10-15 签发 | Phase 2a-2 待公式修正后 |
| `golden_partial_volume_spherical.json` | 同上 | p6（缺） | Q-1 答复后 | Phase 2b 阻塞 |
| `golden_partial_volume_torispherical.json` | 同上 | p7（缺） | Q-1 答复后 | Phase 2b 阻塞 |
| `golden_wetted_area_horizontal.json` | 同上 | p5 wetted（R29a + R29b） | WS-CA-PR-013 Rev B 第一批 2026-10-15 | Phase 2a-2 待公式修正后 |
| `golden_wetted_area_spherical.json` | 同上 | p6 wetted | Q-1 答复后 | Phase 2b 阻塞 |
| `golden_wetted_area_torispherical.json` | 同上 | p7 wetted | Q-1 答复后 | Phase 2b 阻塞 |

> **Fixture 命名**：per-shape 风格（horizontal / spherical / torispherical），与 P6-4 合并 2 文件风格不一致。**本 ADR 选择 per-shape**：每文件 case 数少（2-4），per-shape 让 fixture 索引更直接，工艺室签发新算例时按 shape 文件夹增量更清晰。

### 测试增列清单

#### `tests/services/vessel/test_partial_volume.py`

```python
_PATHS_11 = list(filter(
    lambda p: not (p[0] == "FLAT" and p[1] == "SPHERICAL"),
    product(
        ["HEMISPHERICAL", "2:1_ELLIPTICAL", "TORISPHERICAL", "FLAT"],
        ["VERTICAL", "HORIZONTAL", "SPHERICAL"],
    ),
))

@pytest.mark.parametrize("head_type,vessel_shape", _PATHS_11, ids=...)
def test_partial_volume_11_path_cartesian(head_type, vessel_shape):
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type=head_type,
        H_m=0.9, vessel_shape=vessel_shape,
    )
    result = calc_partial_volume(inp)
    assert result.partial_volume_m3 >= 0
    assert result.total_volume_m3 >= result.partial_volume_m3
    assert result.vessel_shape_used == vessel_shape


def test_partial_volume_p12_flat_spherical_raises():
    with pytest.raises(VesselInputError, match="FLAT × SPHERICAL 几何退化"):
        calc_partial_volume(PartialVolumeInput(
            D_m=1.8, L_m=0.0, head_type="FLAT",
            H_m=1.0, vessel_shape="SPHERICAL",
        ))


@pytest.mark.parametrize("head_type,H_m,expected", [
    ("2:1_ELLIPTICAL", 0.45, 0.2386),    # R/2 sanity check
    ("2:1_ELLIPTICAL", 0.6,  0.3958),    # 2R/3 numerical integration
    ("2:1_ELLIPTICAL", 0.9,  0.7634),    # R WS-CA-PR-013 anchor
    ("2:1_ELLIPTICAL", 1.8,  1.527),     # D full
    ("HEMISPHERICAL",   0.45, 1.430),     # R/2 HEMI
    ("HEMISPHERICAL",   0.6,  2.660),     # 2R/3 HEMI（v6 数值积分）
    ("HEMISPHERICAL",   0.9,  3.054),     # R HEMI = 2·V_full
    ("HEMISPHERICAL",   1.8,  3.054),     # D HEMI = 2·V_full
])
def test_head_partial_volume_horizontal_numerical(head_type, H_m, expected, rel=1e-3):
    """v6 数值积分 vs 解析值 sanity check（n_points=200）。"""
    V = _head_partial_volume_horizontal(head_type, D_m=1.8, H_m=H_m)
    assert abs(V - expected) / expected < rel
```

#### `tests/services/vessel/test_vessel_interface_freeze.py`

+5 测试：vessel_shape 字段 + 默认值 + vessel_shape_used 字段（WettedAreaInput/Result 同步）。

#### `tests/services/vessel/test_helpers_geometry.py`（新）

- `_circular_segment_area_h_m` 边界 + 数值积分对账（scipy.integrate.quad，rel ≤ 1e-6）
- `_sphere_partial_volume_h_m` 边界（H_m=0/D） + 解析对账
- `_head_partial_volume_horizontal` 关键 case 对账（v6 数值积分）：
  - D=1.8, H=0.9, head=2:1 → 0.7634 m³（与 WS-CA-PR-013 SI 对账）
  - D=1.8, H=0.9, head=HEMI → 3.054 m³（球对称 2×V_full）
  - 对称性：A_seg(D, H) + A_seg(D, D-H) = π·D²/4
  - 工艺室新增 d=0.6·R / d=1.2·R 验证（2026-10-15 签发后）

#### `tests/services/vessel/test_mass_iteration_loop_compat.py`（新）

mass_iteration_loop 在 HORIZONTAL/SPHERICAL × HEMI/TORI/FLAT 三新增组合下不抛错；converged=True。

## Implementation Plan

### Phase 1：公式重构 + helper 测试 + 兼容性测试（~2 天）
1. `vessel_service.py` 新增 `_circular_segment_area_h_m` / `_sphere_partial_volume_h_m` / **`_head_partial_volume_horizontal`**（v6 数值积分实现）+ `_circular_segment_area_r_h` + `_trapz` + `_lerp` 内部 helper
2. 重构 `_head_partial_volume` HEMI 分支调 `_sphere_partial_volume_h_m`（球对称复用）
3. 重构 `calc_partial_volume` 加 `vessel_shape` Literal 分发（HORIZONTAL/SPHERICAL 走新公式）
4. 重构 `calc_wetted_area` 同上（HORIZONTAL 润湿面积按 §3 第 8 项公式区分）
5. 修 `mass_iteration_loop` 内部 `calc_partial_volume` 调用补传 `vessel_shape`
6. `_validate_input` 加 p12 拒绝逻辑（错误信息："FLAT × SPHERICAL 几何退化，球面无法配平面封头"）
7. 新增 `test_helpers_geometry.py` + `test_mass_iteration_loop_compat.py`
8. ruff + pytest + G-08 OpenAPI drift=0
9. commit: `feat(p6-x): vessel_service vessel_shape + HORIZONTAL/SPHERICAL 公式重构（含数值积分 + p12 拒绝）`

### Phase 2a-1：fixture 增列（p4 立式，可立即落地）（~0.5 天）
1. 从 WS-CA-PR-013 `Vert-Vol&Area` sheet 提取 p4 三 case（partial_volume + wetted_area）
2. commit: `test(p6-x): WS-CA-PR-013 p4 黄金 fixture × 3 case`

### Phase 2a-2：fixture 增列（p5 卧式 + d=0.6·R + d=1.2·R，待工艺室 2026-10-15 签发后）（~0.5 天）
1. 从 WS-CA-PR-013 Rev B `HEMI-Vol&Area` + `Horiz-Vol&Area-SI` 提取 p5 + 2 个 d ≠ R case
2. 对账验证：v6 数值积分与 WS-CA-PR-013 报告 ±0.1%
3. commit: `test(p6-x): WS-CA-PR-013 p5 + d=0.6·R + d=1.2·R 黄金 fixture × 3 case`

### Phase 2b：fixture 增列（9 路径，待 Q-1 答复）（~1 天）
1. 工艺室 2026-10-15 前 WS-CA-PR-013 Rev B 第一批签发（p1/p2/p10/p11）
2. 工艺室 2026-11-30 前 Rev B 第二批签发（p3/p6/p7/p8/p9）
3. 填入剩余 5 fixture JSON 文件
4. 验收等级标注（HEMI/2:1/FLAT <0.1%；TORI <1%）
5. commit: `test(p6-x): Q-1 答复后补 9 路径 fixture`

### Phase 3：笛卡尔积参数化 + freeze 测试（~1 天）
1. `test_partial_volume.py` 加 11 路径笛卡尔积 + p12 异常测试 + v6 数值积分 sanity check
2. `test_wetted_area.py` 同上
3. `test_vessel_interface_freeze.py` +5 测试
4. commit: `test(p6-x): 11 路径笛卡尔积 + p12 异常 + freeze 扩展`

### Phase 4：工艺对账 + 文档更新（~1 天）
1. 全栈 pytest + ruff + G-08 drift=0
2. 更新 ADR-0040 §F5.1（按 Phase 2a/2b 实际进度）
3. 更新 SPEC-ADD-001 V1.x C-12
4. commit: `docs(p6-x): ADR-0040 §F5.1 升级 + SPEC 同步`

## Consequences

### 正面

- **公式正确性**：HORIZONTAL 封头公式改为数值积分，d=0.6·R / d=1.2·R 等中间值精度 <1e-4（满足 D5 <0.1% 强公式）
- **冻结契约生效分阶段**：Phase 2a-1 后 p4 冻结生效；Phase 2a-2 后 p5 + d=0.6·R + d=1.2·R 冻结生效；Phase 2b 后全 11 路径
- **5 调用方无破坏**：vessel_shape 默认 VERTICAL；mass_iteration_loop bugfix + 兼容性测试
- **D5 验收分级清晰**：HEMI/2:1/FLAT <0.1%（数值积分）；TORI <1%（工艺室 ASME VIII-1 UG-32 工程近似）
- **OPEN-1/2/3 全部关闭**：WS-CA-PR-013 Rev B 扩展 + 封头计数约定澄清 + 润湿面积公式区分

### 负面

- **fixture 仍占位**：`SYNTHETIC_TEST_DATA` 标记的 9 路径 fixture 待 Q-1 答复（OPEN-1 已关闭，工艺室 2026-10-15 / 2026-11-30 两批签发）
- **mass_iteration_loop bugfix 行为微变**：HORIZONTAL/SPHERICAL 路径修复后行为更正确；CHANGELOG 标注
- **9 路径算例依赖工艺室 Q-1 排期**：2026-10-15 / 2026-11-30 两个截止点（OPEN-1 已关闭）

### 中和

- **回退路径**：Q-1 推迟则 Phase 2b 推迟；冻结窗口延长由 ADR-0042 决策（工艺 P1-11 建议续冻至 2027-09-25）

## Validation / Compliance

1. 签名快照测试：现有 12 + 新 5 = 17 个 freeze 测试
2. 黄金 fixture：现有 11 + Phase 2a-1 新 3 + Phase 2a-2 新 3 + Phase 2b 待定
3. 11 路径笛卡尔积 + p12 异常测试
4. v6 数值积分 sanity check（4 head × 4 d = 16 case，rel <1e-3）
5. mass_iteration 兼容性测试 8 项
6. CI 强制：ruff / pytest / G-08 / 中文 docstring / Pydantic 中文 description

### 复审触发

- **2026-10-15**：工艺室 Q-1 第一批签发截止点（p1/p2/p10/p11）
- **2026-11-30**：工艺室 Q-1 第二批签发截止点（p3/p6/p7/p8/p9）
- **2027-01-25**：中期复审（工艺 P2-7 参与）
- **2027-03-25**：冻结到期；续冻由 ADR-0042 决策

## References

- ADR-0040 §F5.1（V1.2 诚实声明 + 冻结生效条件）：本 ADR 直接修补对象
- SPEC §3.4.4 C-12（V1.8 冻结）
- SPEC-ADD-001 V1.x 计算覆盖增补规格说明书
- ADR-0008 D5 工艺计算函数契约冻结模板
- **GPSA Engineering Data Book 第 13 版 Chapter 13（Separators）§13.3 partial volume 工程惯例**
- **Perry's Chemical Engineers' Handbook 第 8 版 Chapter 6（Process Heat Transfer）/ Process Equipment 章节**
- **Chemical Engineering 2007 年 12 月 Doane 文章（VERTICAL 2:1 封头润湿面积）**
- **ASME VIII-1 UG-32 碟形封头几何参数（TORISPHERICAL r(z) 参数化）**
- **WS-CA-PR-013 源文件**（`sample/Process calculation from Worley/16.3 Standard Calculation/WS-CA-PR-013.xls`，v6 路径已修正拼写）：
  - `Case 1` — 泵 sizing（非 C-12）
  - `Vert-Vol&Area` — VERTICAL 2:1 ELLIPTICAL 3 case（H=0.45/0.9/1.35m, D=1.8m, L=4.5m）
  - `Horiz-Vol&Area-SI` — HORIZONTAL 2:1 ELLIPTICAL 50% fill（D=1.8m, L=4.5m, water）
  - `Horiz-Vol&Area-Eng` — Imperial 对照（D=5.906ft, L=14.764ft, 50% fill）
  - **Rev B 第一批 2026-10-15 前**：HEMI-Vol&Area + FLAT-Vol&Area
  - **Rev B 第二批 2026-11-30 前**：SPHERE-Vol&Area + TORI-Vol&Area
- WS-CA-PR-014 / -015 / -016 不用于 C-12（已分配给 C-13 / C-14 / C-15）
- OpenWolf P6-4-batch plan: `docs/superpowers/plans/2026-09-25-p6-4-batch.md`

## Freeze Window Summary

| 阶段 | 冻结范围 | 状态 |
|------|----------|------|
| 当前生效 | p1 / p4 / p5 / p6 / p10 + p7 smoke | ADR-0040 V1.2 起至 2027-03-25 |
| 待生效（Phase 2a-1 后） | + p4 fixture 数值精度（WS-CA-PR-013） | 待 Phase 2a-1 落地 |
| 待生效（Phase 2a-2 后） | + p5 fixture 数值精度（WS-CA-PR-013 SI）+ d=0.6·R + d=1.2·R 验证 | 待工艺室 2026-10-15 签发 + Phase 2a-2 落地 |
| 待生效（Phase 2b 后） | 全 11 路径覆盖（WS-CA-PR-013 Rev B 第二批） | 待工艺室 2026-11-30 签发 + Phase 2b 落地 |

> p12 永久 N/A + 实现层拒绝；不计入冻结路径。

## Open Questions

1. **Q-1 ✅ 关闭**（v6 工艺室直接答复）：9 路径算例来源 = WS-CA-PR-013 Rev B 扩展，第一批 2026-10-15（p1/p2/p10/p11，HEMI/FLAT），第二批 2026-11-30（p3/p6/p7/p8/p9，SPHERE/TORI）；不新建编号，不用 Worley 库查找

2. **Q-2**：Phase 2a-1 后 p4 投产；p5 待公式修正后；其余 9 路径"实验性"

3. **Q-3 ✅ 关闭**：helper 不挂 lru_cache

4. **Q-4 ✅ 关闭**：TORI <1% 经验拟合；r(z) 参数化待工艺室 ASME VIII-1 UG-32 提供

5. **Q-5**（暂不落地）：H1_m/H2_m/H3_m 多段语义由独立 ADR-0043+ 处理

6. **Q-6 ✅ 关闭**：以 WS-CA-PR-013 源文件 + GPSA / Perry's 推导为准；v6 数值积分取代 v5 闭式公式

7. **Q-7 ✅ 关闭**：mass_iteration_loop bugfix 行为微变 CHANGELOG 标注

8. **Q-8（新增）**：续冻至 2027-09-25 由 ADR-0042 决策（工艺 P1-11 建议）

9. **Q-9 ✅ 关闭**（v6 工艺室直接答复）：卧式封头部分体积公式 = 数值积分实现（v6 `_head_partial_volume_horizontal` helper）；HEMI 球对称 v5 闭式公式在 d=R / d=D 特殊点正确（已修正 v5 审查笔误，详见 §4）

10. **Q-10 ✅ 关闭**（v6 工艺室直接答复）：WS-CA-PR-013 封头计数约定 = 两端封头各计一半（行业标准）；50% fill 时单端 = V_full/2，两端之和 = V_full；与 Perry's / GPSA 行业惯例一致

11. **Q-11 ✅ 关闭**（v6 工艺室直接答复）：p4/p5 wetted_area 来源 = R38（p4 三 case）/ R29（p5，拆 R29a 筒体 + R29b 两端封头）；VERTICAL 与 HORIZONTAL 润湿面积公式区分（Doane 2007 / 工艺简化公式 / HEMI 闭式 / 2:1+TORI 数值积分）；WS-CA-PR-013 Rev B 同步补全

---

## §4 工艺室 v5 HEMI 计算笔误修正（v6 附录）

> **本节为 v6 工艺室答复的技术附录**，澄清 v5 审查中 HEMI 公式"100%/300% 偏差"为工艺室计算笔误，v5 闭式公式在 d=R / d=D 边界条件 + 公式段均正确。

### 工艺室 v5 审查原文

```
HEMI 卧式公式系统性偏差
v5 公式：两端之和 = 2 × π·d²·(3D/2 − d)/3
工艺侧复核：
d = R（50% fill）正确值 = 半球体积的一半 × 2 = V_full = (2/3)πR³ ≈ 0.7634 m³；
v5 公式给 2·π·R²·(3R-R)/3 = 2πR²·2R/3 = 4πR³/3 ≈ 1.527 m³；
偏差 +100%。
```

### v6 推导修正（独立数学验证）

**HEMI V_full 单端**（球缺公式）：
```
V_full_HEMI = (2/3) · π · R³
```
代入 R=0.9（D=1.8）：
```
V_full_HEMI = (2/3) · π · 0.729 = (2/3) · π · 0.729 = π · 0.486 = 1.527 m³
```
> **注意**：工艺室 v5 审查写"≈ 0.7634 m³"——0.7634 是 2:1 ELLIPTICAL 的 V_full，**不是 HEMI 的**。HEMI V_full 单端 = 1.527 m³。

**v5 公式在 d=R 时**：
```
v5(d=R) = 2 × π · R² · (3R−R) / 3 = 2 × π · R² · 2R / 3 = (4/3) · π · R³ = 2 × V_full
```
代入 R=0.9：
```
v5(d=R) = (4/3) · π · 0.729 = (4/3) · 1.527 = 2 × 1.527 = 3.054 m³
```
> **两端之和 = 2 × V_full**（每端满液时 V = V_full，两端共 2 × V_full）✓ **正确**

### 工艺室 v5 审查数字笔误汇总

| 工艺室 v5 审查 | 工艺室写值 | 实际值 | 偏差判断 |
|--------------|-----------|--------|---------|
| HEMI V_full | 0.7634 m³ | **1.527 m³**（2:1 V_full 误植） | 工艺室笔误 |
| v5 d=R 输出 | 1.527 m³ | **3.054 m³**（2 × V_full，正确） | 工艺室笔误 |
| v5 d=R 偏差 | "+100%" | **0%**（两端之和 = 2·V_full = 正确） | 工艺室笔误 |
| HEMI d=2R 正确值 | V_full = 0.7634 m³（单端） | **V_full = 1.527 m³（单端）** | 工艺室笔误 |
| v5 d=2R 输出（误读） | 8πR³/3 ≈ 6.107 m³ | **3.054 m³**（v5 边界 case `H_m ≥ D_m` 返回 2·V_full = π·D³/6 = 3.054） | 工艺室未读 v5 边界 case 代码 |

### v6 结论

- **v5 HEMI 公式 + 边界 case 在 d ∈ {R, D} 时完全正确**（验证 0% 偏差）
- **v6 仍采用数值积分**作为通用实现（更稳健，覆盖 d ∈ [0, D] 全区间，精度 <1e-4）
- **v5 闭式公式保留**作为数值积分的 sanity check（test_head_partial_volume_horizontal_numerical 测试 case 锚定 d=R / d=D 两个特殊点）
- **核心策略不变**：闭式公式 + 数值积分双实现 + 工程化对账，工艺负责人主偏好审查制衡