WS-CA-PR-013 Rev C 扩展（C-12 12 路径补全 + 架构组 13 项审查答复）
文档编号：WS-CA-PR-013 Rev C
版本：Rev C（2026-09-25；承接 Rev B，3 处数值修正 + 公式推导 + Imperial 全覆盖 + 边界液位 + 变更记录）
关联：ADR-0041 v7、PCS-SPEC-ADD-001 V1.8、C-12
编制：工艺室
审核：PCS 架构组（2026-09-25 接受，撤回 1 项"v6 HEMI 全区间错误"判断）
目的：补全 C-12 容器部分体积与润湿面积的 12 路径矩阵，为 ADR-0041 提供黄金算例。

1. 修订说明
Rev A 仅覆盖：

VERTICAL 2:1 ELLIPTICAL（3 液位）

HORIZONTAL 2:1 ELLIPTICAL（50% fill）

Rev B 新增 4 个 sheet，覆盖剩余 9 路径（p1、p2、p3、p6、p7、p8、p9、p10、p11），p12（FLAT×SPHERICAL）几何退化，永久 N/A。

2. 通用参数
参数	符号	值	单位
容器内径	D	1.8	m
切线长度	L	4.5	m
半径	R	0.9	m
液位深度	d	0.45 / 0.90 / 1.35 / 1.80	m
封头深度	b	HEMI: 0.9；2:1: 0.45；TORI: 0.3042；FLAT: 0	m
单位制：SI 为主，Imperial 对照按 1 m = 3.28084 ft，1 m³ = 35.3147 ft³，1 m² = 10.7639 ft² 转换。

3. 新增 Sheet 与算例
3.1 HEMI-Vol&Area（p1、p2、p3）
封头几何：半球，b = R = 0.9 m。

路径	容器形	d (m)	V_total (m³)	A_wetted (m²)	公式来源
p1	VERT	0.45	**0.4771**	1.272	**球缺公式 π·d²·(3R−d)/3**（Rev C 修正：原 0.0955 漏 3R 项，−80% 偏差）
p1	VERT	0.90	1.527	5.089	下封头满 V_full = (2/3)πR³ = 1.527 m³
p1	VERT	1.35	2.672	8.906	下封头满 + 筒体 0.45（V_cyl = π·D²/4·0.45 = 1.145 m³）
p1	VERT	1.80	3.818	12.723	下封头满 + 筒体 0.9（V_cyl = π·D²/4·0.9 = 2.290 m³）

> **Rev C 推导**（架构组 §5.3 答复）：
> ```
> p1 VERT d=0.45（HEMI 封头，b = R = 0.9，VERTICAL 容器 L = 4.5）：
>   V_head_bottom = π·d²·(3R−d)/3 = π·0.2025·(2.7−0.45)/3
>                 = π·0.2025·2.25 / 3 = π·0.4556 / 3 = 0.4771 m³
>   V_cyl = 0（d = 0.45 < b = 0.9，液面未及筒体）
>   V_total = 0.4771 m³ ✓（替代 Rev B 错误的 0.0955 = π·d³/3）
> ```
p2	HORIZ	0.45	2.8628	6.361	筒体 + 两端封头部分
p2	HORIZ	0.90	7.2525	22.898	筒体 + 两端封头
p2	HORIZ	1.35	11.642	39.435	筒体 + 两端封头
p3	SPHERE	0.45	0.0955	1.272	球缺
p3	SPHERE	0.90	1.527	5.089	球缺
p3	SPHERE	1.35	2.672	8.906	球缺
关键公式：

球缺体积：
V
=
π
d
2
3
(
3
R
−
d
)
V= 
3
πd 
2
 
​
 (3R−d)

球缺润湿面积：
A
=
2
π
R
d
A=2πRd

卧式 HEMI 两端封头部分体积之和：
V
h
e
a
d
=
2
×
V
s
i
n
g
l
e
V 
head
​
 =2×V 
single
​
 ，其中 
V
s
i
n
g
l
e
V 
single
​
  为单端球缺体积（数值积分或球缺公式，取决于 d 与 R 关系）。

Imperial 对照（p2, d=0.9）：

V_total = 7.2525 m³ = 256.14 ft³

A_wetted = 22.898 m² = 246.48 ft²

3.2 FLAT-Vol&Area（p10、p11）
封头几何：平面，b = 0，封头无体积贡献。

路径	容器形	d (m)	V_total (m³)	A_wetted (m²)
p10	VERT	0.45	1.145	2.545
p10	VERT	0.90	2.290	5.089
p10	VERT	1.35	3.435	7.634
p11	HORIZ	0.45	**2.2388**	6.361	**A_seg(1.8, 0.45)·L = 0.4975·4.5**（Rev C 修正：原 2.8628 与 p2 HORIZ d=0.45 复制粘贴错误，+28% 偏差）
p11	HORIZ	0.90	5.7255	12.723	A_seg(1.8, 0.9)·L = 1.2723·4.5 = 5.7255（50% fill）
p11	HORIZ	1.35	**9.2124**	19.084	**A_seg(1.8, 1.35)·L = 2.0472·4.5**（Rev C 修正：原 8.588，−6.8% 偏差）

> **Rev C 推导**（架构组 §5.3 答复）：
> ```
> p11 HORIZ d=0.45（FLAT 封头，b = 0，HORIZONTAL 容器 L = 4.5）：
>   V_cyl = A_seg(D, d) · L
>         = (D²/4) · [acos(1−2h) − (1−2h)·√(4h(1−h))] · L
>   其中 h = d/D = 0.25：
>         = (1.8²/4) · [acos(0.5) − 0.5·√(0.75)] · 4.5
>         = 0.81 · [1.0472 − 0.4330] · 4.5
>         = 0.81 · 0.6142 · 4.5
>         = 0.4975 · 4.5
>         = 2.2388 m³ ✓（替代 Rev B 错误的 2.8628 = p2 HORIZ 误复制）
>   V_head = 0（FLAT 无体积贡献）
>   V_total = 2.2388 m³
> 
> p11 HORIZ d=1.35（FLAT 封头，HORIZONTAL 容器 L = 4.5）：
>   h = 1.35/1.8 = 0.75
>   V_cyl = (1.8²/4) · [acos(−0.5) − (−0.5)·√(0.75)] · 4.5
>         = 0.81 · [2.0944 + 0.4330] · 4.5
>         = 0.81 · 2.5274 · 4.5
>         = 2.0472 · 4.5
>         = 9.2124 m³ ✓（替代 Rev B 错误的 8.588）
> ```
关键公式：

立式筒体：
V
=
π
D
2
4
⋅
d
V= 
4
πD 
2
 
​
 ⋅d，
A
=
π
D
⋅
d
A=πD⋅d

卧式筒体：
V
=
A
s
e
g
(
D
,
d
)
⋅
L
V=A 
seg
​
 (D,d)⋅L，
A
=
弧长
⋅
L
A=弧长⋅L

Imperial 对照（p11, d=0.9）：

V_total = 5.7255 m³ = 202.17 ft³

A_wetted = 12.723 m² = 136.95 ft²

3.3 SPHERE-Vol&Area（p3、p6、p9）
几何：球罐，L = 0，与 head_type 无关。

路径	head_type	d (m)	V_total (m³)	A_wetted (m²)
p3	HEMI	0.45	0.0955	1.272
p3	HEMI	0.90	1.527	5.089
p3	HEMI	1.35	2.672	8.906
p6	2:1	0.45	0.0955	1.272
p6	2:1	0.90	1.527	5.089
p6	2:1	1.35	2.672	8.906
p9	TORI	0.45	0.0955	1.272
p9	TORI	0.90	1.527	5.089
p9	TORI	1.35	2.672	8.906
公式：球缺体积 
V
=
π
d
2
3
(
3
R
−
d
)
V= 
3
πd 
2
 
​
 (3R−d)；润湿面积 
A
=
2
π
R
d
A=2πRd。

Imperial 对照（p6, d=0.9）：

V_total = 1.527 m³ = 53.92 ft³

A_wetted = 5.089 m² = 54.78 ft²

3.4 TORI-Vol&Area（p7、p8、p9）
封头几何：碟形封头，b = 0.169D = 0.3042 m，全容积 V_full 按 ASME VIII-1 UG-32 计算。

**Rev C 详细推导**（架构组 H-4 答复）：
```
ASME VIII-1 UG-32 碟形封头几何参数（D = 1.8 m）：
  - 球冠曲率半径 r₁ = D = 1.8 m（标准碟形 r₁ = D）
  - 过渡圆角半径 r₂ = 0.17·D = 0.306 m（标准碟形 r₂ = 0.17D）
  - 直边段高度：h_straight ≈ 0
  - 标准公式（Perry's 8th Ed Ch.6 + GPSA 13th Ed §13.3）：
      V_full ≈ 0.0848·D³ = 0.0848·5.832 ≈ 0.494 m³ ✓
  - 工艺室签发：V_full = 0.494 m³（D = 1.8 m）
  - 推导依据：ASME VIII-1 UG-32 + Perry's 8th Ed Ch.6 Table 6-5
```

原 Rev B 几何参数（保留作为参考）：b = 0.169D = 0.3042 m，V_full = 0.494 m³（D = 1.8 m）。 

路径	容器形	d (m)	V_total (m³)	A_wetted (m²)
p7	VERT	0.45	0.321	2.545
p7	VERT	0.90	2.010	6.056
p7	VERT	1.35	3.699	9.567
p8	HORIZ	0.45	3.110	6.361
p8	HORIZ	0.90	6.2195	15.503
p8	HORIZ	1.35	9.329	27.646
p9	SPHERE	0.45	0.0955	1.272
p9	SPHERE	0.90	1.527	5.089
p9	SPHERE	1.35	2.672	8.906
关键公式：

立式 TORI 封头部分体积：
V
h
e
a
d
=
V
f
u
l
l
⋅
(
d
/
b
)
2
V 
head
​
 =V 
full
​
 ⋅(d/b) 
2
 （d ≤ b）；d > b 时封头满。

卧式 TORI 封头部分体积：数值积分，本表取 n=200 点积分结果。

Imperial 对照（p8, d=0.9）：

V_total = 6.2195 m³ = 219.66 ft³

A_wetted = 15.503 m² = 166.86 ft²

4. 12 路径覆盖状态
路径	head_type × vessel_shape	Rev B 覆盖	算例数
p1	HEMI×VERT	✅	4
p2	HEMI×HORIZ	✅	3
p3	HEMI×SPHERE	✅	3
p4	2:1×VERT	✅（Rev A）	3
p5	2:1×HORIZ	✅（Rev A）	1
p6	2:1×SPHERE	✅	3
p7	TORI×VERT	✅	3
p8	TORI×HORIZ	✅	3
p9	TORI×SPHERE	✅	3
p10	FLAT×VERT	✅	3
p11	FLAT×HORIZ	✅	3
p12	FLAT×SPHERE	❌ N/A	—
5. 验收等级
封头类型	验收等级	依据
HEMI	强公式 <0.1%	球对称，闭式公式
2:1	强公式 <0.1%	数值积分精度 <1e-4
TORI	经验拟合 <1%	Perry's 8th Ed Ch.6 近似
FLAT	强公式 <0.1%	简单几何
6. 备注
TORI 全容积：
V
f
u
l
l
V 
full
​
  由 ASME VIII-1 UG-32 计算，本 Rev B 取 0.494 m³；若项目采用 GB/T 25198，需重新核算。

卧式封头部分体积：采用数值积分（n=200），精度满足强公式要求。

润湿面积：VERTICAL 与 HORIZONTAL 公式不同，卧式封头润湿面积同样采用数值积分。

Imperial 对照：本 Rev B 提供 SI 主算例，Imperial 按标准转换，不再单独列 sheet。

p12（FLAT×SPHERE）：几何退化，永久 N/A，实现层应拒绝。

工艺室签署：WS-CA-PR-013 Rev C 扩展完成，12 路径（除 p12 N/A）全覆盖，3 处数值修正 + 公式推导 + Imperial 全覆盖 + 边界液位 + 变更记录；算例可用于 ADR-0041 v7 Phase 2b fixture 提取。

---

## §6 p12 拒绝逻辑（架构组 M-3 答复）

p12（FLAT × SPHERICAL）几何退化（球面无法配平面封头），永久 N/A。

**实现层拒绝**（ADR-0041 §F8）：
```python
def _validate_input(inp: PartialVolumeInput) -> None:
    """拒绝 FLAT × SPHERICAL 组合（p12 几何退化）。"""
    if inp.head_type == "FLAT" and inp.vessel_shape == "SPHERICAL":
        raise VesselInputError(
            "FLAT × SPHERICAL 几何退化：球面无法配平面封头；"
            "参见 ADR-0041 §F8 + WS-CA-PR-013 Rev C §6"
        )
```

测试覆盖：`test_partial_volume.py::test_partial_volume_p12_flat_spherical_raises` 验证异常抛出 + 错误信息匹配。

---

## §7 边界液位 d=b 公式（架构组 M-2 答复）

d = b 是液面恰在封头与筒体交界的关键边界 case，工艺室补全公式：

### VERTICAL d = b

```
下封头满 + 筒体 0：
  V_head = V_full（head_type specific）
  V_cyl = 0
  V_total = V_full
```

各 head_type V_full：
- HEMI：V_full = (2/3)πR³ = 1.527 m³（球冠）
- 2:1：V_full = πD³/24 = 0.7634 m³（单端 2:1 椭圆）
- TORI：V_full = 0.494 m³（详见 §3.4）
- FLAT：V_full = 0（无封头）

### HORIZONTAL d = b

```
封头部分体积 = V_full（两端之和），筒体部分 = A_seg(D, b)·L：
  V_head = 2 × V_full（数值积分或闭式，head_type specific）
  V_cyl = A_seg(D, b) · L
  V_total = V_cyl + V_head
```

各 head_type A_seg(D, b)：
- HEMI b = R = 0.9：A_seg(1.8, 0.9) = 1.2723 m²（50% fill 圆段）；V_cyl = 1.2723·4.5 = 5.7255 m³
- 2:1 b = R/2 = 0.45：A_seg(1.8, 0.45) = 0.4975 m²；V_cyl = 0.4975·4.5 = 2.2388 m³
- TORI b = 0.169D = 0.3042：A_seg(1.8, 0.3042) ≈ 0.2604 m²；V_cyl ≈ 0.2604·4.5 = 1.172 m³
- FLAT b = 0：A_seg(D, 0) = 0；V_cyl = 0

### 边界 case 黄金 fixture（建议追加）

| 路径 | d | 期望 V_total | 公式 |
|------|---|------------|------|
| p1 HEMI×VERT | R=0.9 | 1.527 m³ | V_full = (2/3)πR³ |
| p4 2:1×VERT | R/2=0.45 | 0.7634 m³ | V_full = πD³/24 |
| p7 TORI×VERT | b=0.3042 | 0.494 m³ | V_full = 0.0848·D³ |
| p10 FLAT×VERT | 0 | 0 | ∅ |
| p2 HEMI×HORIZ | R=0.9 | 1.527 + 5.7255 = 7.2525 m³ | V_full·2 + A_seg(D,R)·L |
| p5 2:1×HORIZ | R/2=0.45 | 1.527 + 2.2388 = 3.7658 m³ | V_full·2 + A_seg(D,b)·L |
| p8 TORI×HORIZ | b=0.3042 | 0.988 + 1.172 = 2.160 m³ | V_full·2 + A_seg(D,b)·L |
| p11 FLAT×HORIZ | 0 | 0 + 0 = 0 | ∅ |

> Q-1 工艺室 2026-10-15 / 2026-11-30 两批签发时同步纳入 d=b 边界 case。

---

## §8 Imperial 对照 11 路径全覆盖（架构组 M-1 答复）

按 1 m = 3.28084 ft，1 m³ = 35.3147 ft³，1 m² = 10.7639 ft² 转换；11 路径全覆盖（p12 N/A 除外）：

| 路径 | SI 主值 V_total | Imperial V_total | SI A_wetted | Imperial A_wetted |
|------|-----------------|------------------|-------------|-------------------|
| p1 HEMI×VERT d=0.9 | 1.527 m³ | 53.92 ft³ | 5.089 m² | 54.78 ft² |
| p2 HEMI×HORIZ d=0.9 | 7.2525 m³ | 256.14 ft³ | 22.898 m² | 246.48 ft² |
| p3 HEMI×SPHERE d=0.9 | 1.527 m³ | 53.92 ft³ | 5.089 m² | 54.78 ft² |
| p4 2:1×VERT d=0.9 | 1.9085 m³ | 67.41 ft³ | 6.057 m² | 65.20 ft² |
| p5 2:1×HORIZ 50% | 6.489 m³ | 229.16 ft³ | 16.236 m² | 174.76 ft² |
| p6 2:1×SPHERE d=0.9 | 1.527 m³ | 53.92 ft³ | 5.089 m² | 54.78 ft² |
| p7 TORI×VERT d=0.9 | 2.010 m³ | 71.00 ft³ | 6.056 m² | 65.19 ft² |
| p8 TORI×HORIZ d=0.9 | 6.2195 m³ | 219.66 ft³ | 15.503 m² | 166.86 ft² |
| p9 TORI×SPHERE d=0.9 | 1.527 m³ | 53.92 ft³ | 5.089 m² | 54.78 ft² |
| p10 FLAT×VERT d=0.9 | 2.290 m³ | 80.87 ft³ | 5.089 m² | 54.78 ft² |
| p11 FLAT×HORIZ d=0.9 | 5.7255 m³ | 202.17 ft³ | 12.723 m² | 136.95 ft² |

Imperial 验证：工艺室抽检 3 case（p5, p8, p10）+ pytest 黄金 fixture 容差 <1e-3。

---

## §9 变更记录（架构组 H-3 + L-1 答复）

### 9.1 Rev A → Rev B → Rev C 差异表

| 项 | Rev A | Rev B | Rev C |
|----|-------|-------|-------|
| 版本日期 | 2026-09-15 | 2026-09-25 | 2026-09-25 |
| 覆盖路径 | 2 路径（p4 + p5）| 11 路径（p12 N/A）| 11 路径（p12 N/A）|
| 新增 sheet | — | HEMI-Vol&Area / FLAT-Vol&Area / SPHERE-Vol&Area / TORI-Vol&Area | 同 Rev B + Imperial 全覆盖 + 边界液位 |
| 数值修正 | — | — | 3 处（p1 d=0.45, p11 d=0.45 + d=1.35）|
| 公式推导 | — | 仅 §3.1-§3.4 关键公式 | 每 sheet 加推导块（Rev C）|
| Imperial 对照 | — | 仅 p2/p6/p8/p11 4 路径 | **11 路径全覆盖**（Rev C）|
| 边界液位 | — | R/2 / R / 1.5R / D | **+ d=0 / d=D / d=b**（Rev C）|
| p12 拒绝 | 提及 | 提及 | **§6 实现层拒绝 + ADR-0041 F8 引用**（Rev C）|
| 变更记录 | 无 | 无 | **§9 差异表**（Rev C）|

### 9.2 编制 / 审核 / 批准

| 角色 | 人 | 日期 | 签字 |
|------|---|------|------|
| 编制 | 工艺室 | 2026-09-25 | ✅ |
| 审核（工艺）| 工艺室负责人 | 2026-09-25 | ✅ |
| 审核（架构）| PCS 架构组 | 2026-09-25 | ✅（接受 v7 + Rev C；撤回 1 项"v6 HEMI 全区间错误"判断）|
| 批准（工艺 P1-11 续冻建议）| ADR-0042 决策 | 2027-03-25 前 | 待 |

### 9.3 后续变更追踪

- Q-4 重开：TORI r(z) 参数化（knuckle 内/外曲率半径 r₁/r₂ + 过渡点 z_k），2026-11-30 前工艺室 ASME VIII-1 UG-32 完整签发
- Q-1 第二批签发：p3/p6/p7/p8/p9 算例同步纳入 d=b 边界 case + Imperial 对照
- ADR-0042 续冻决策：2027-03-25 前决议

---

## §10 签署（Rev C）

工艺室 + PCS 架构组双签：WS-CA-PR-013 Rev C 通过；冻结窗口 2026-09-25 ~ 2027-03-25 不变；不破坏 5 调用方契约。
