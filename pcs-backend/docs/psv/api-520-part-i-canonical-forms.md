# API 520 Part I 9th Ed.（2014-07）canonical forms —— 速查

> **从 `.wolf/cerebrum.md` 搬来（2026-11-12 瘦身）**：它是**领域参考**
> （泄压面积 / 临界流动 / 两相流判据），不是「下次还会犯」的规则 ⇒
> 不该占「写代码前查 DNR」的热路径 ⇒ 搬到与它服务的代码同仓。

### API 520 Part I 9th Ed.（2014-07）canonical forms（2026-09-18 验证锁定）

- **§5.6.3.1 Eq (9) SI** C = 0.03948 × √[**k** × (2/(k+1))^((k+1)/(k-1))] — √ 内**只有 k**，**没有 k/(k-1)**。
- **`(k/(k-1))` 因子归属**：§5.6.4 subcritical F_2 Eq 18（`√[(k/(k-1)) × r^(2/k) × ((1-r^((k-1)/k))/(1-r))]`），不用于 critical flow。
- **Eq (5) SI** A = W/(C·Kd·P₁·Kb·Kc) × √(TZ/M)，中 M 在 kg/kmol 下，0.03948 常数已隐含 R 维度。PCS 用 M=kg/mol + R=8.314462618 J/(mol·K) 代数等价。
- **Table 8 SI 列** k=1.10/1.40/1.67 = 0.0248/0.0270/0.0287（4 位有效）。
- **§5.6.3.2 Example 1**（Eq 11 SI）= 3698 mm²（输入：W=24270 kg/h, M=51, k=1.11, T=348K, Z=0.90, P₁=670 kPa）。
- **章节定位**：`§5.6.3.1.1`（不是 §5.6.5 — 9th Ed. 没有 §5.6.5）。
- **bug-089 教训**：不能跨章节搬公式因子；critical 与 subcritical 用的 (k/(k-1)) 形式看似相似但语境完全不同——9th Ed. PDF 原文交叉验证是底线。
- **P5-3-7 ✅**（commit `b83a3a0`，2026-09-18 闭环）：完整 Annex C.2.2 Two-Point Omega Method（Eq C.12/C.13/C.14/C.18/C.19/C.21）— 见上面"Two-Point Omega Method Annex C.2.2" Key Learning。bug-094。
- **P5-3-8 待办**：GB/T 12241 bug-089 修复（R=8314 → 8.314462618，移除 k/(k-1) 因子）—— 与 API 520 同步。
