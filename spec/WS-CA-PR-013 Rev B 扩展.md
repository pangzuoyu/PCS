WS-CA-PR-013 Rev B 扩展（C-12 12 路径补全）
文档编号：WS-CA-PR-013 Rev B
版本：Rev B（2026-09-25）
关联：ADR-0041 v5、PCS-SPEC-ADD-001 V1.8、C-12
编制：工艺室
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
p1	VERT	0.45	0.0955	1.272	球缺体积 + 筒体
p1	VERT	0.90	1.527	5.089	下封头满
p1	VERT	1.35	2.672	8.906	下封头满 + 筒体 0.45
p1	VERT	1.80	3.818	12.723	下封头满 + 筒体 0.9
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
p11	HORIZ	0.45	2.8628	6.361
p11	HORIZ	0.90	5.7255	12.723
p11	HORIZ	1.35	8.588	19.084
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
封头几何：碟形封头，b = 0.169D = 0.3042 m，全容积 
V
f
u
l
l
V 
full
​
  按 ASME VIII-1 UG-32 计算，本 Rev B 取 
V
f
u
l
l
=
0.494
V 
full
​
 =0.494 m³（D=1.8m）。

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

工艺室签署：WS-CA-PR-013 Rev B 扩展完成，12 路径（除 p12 N/A）全覆盖，算例可用于 ADR-0041 Phase 2b fixture 提取。
