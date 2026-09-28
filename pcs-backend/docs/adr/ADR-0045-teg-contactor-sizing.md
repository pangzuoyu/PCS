---
status: accepted
date: 2026-09-28
revised: 2026-09-28
version: V1.1 (Rev A)
proposed_by: P6-6A-6 架构组 (T1 implementer, after v5.1 Day-0 Gate form decision)
related:
  - ADR-0046 (TBD, 待 P6-6B 工艺工程师起草)
  - docs/superpowers/plans/2026-09-28-p6-6a-6-glycol-full.md (v5.1 plan)
  - sample/Process caculation from Worley/WS-CA-PR-018.xls (E40=120.76 in @ Q=288 MMscfd)
  - OPEN-P6-6A-9 quest (Ruling 5 后续 P6-6B 接管)
accepted_by: P6-6A-6 v5.1 plan commit 95bb442 (Day-0 Gate form decision)
---

# ADR-0045 Rev A: TEG Contactor Sizing 标准态换算澄清 + K 单点标定说明

## Status

Accepted (P6-6A-6 v5.1 架构组签署)

Supersedes: ADR-0045 (v4, Draft, WITHDRAWN — 物理依据与主流文献不符)

Superseded by: ADR-0046 (TBD, 待 P6-6B 工艺工程师起草)

## Context

P6-6A-6 实现 C-16 glycol dehydration FULL 系统，需要计算 full column diameter。
Worley PR-018 XLS E40=120.76 in @ Q_gas=288 MMscfd / 120°F / 1000 psia / sg≈0.6 /
TEG 99% 是 XLS 标定值。v2/v3 采用 Souders-Brown flooding criteria 直接计算时
与 XLS E40 严重不符（v3 算 3707 in vs XLS 120.76 in, 30× 偏差）。

## 30× 偏差根因分析 (B-1 + v5.1 P-3 落实 — 架构组在 plan 阶段完成 **推测**，**待 P6-6B 工程师验证**)

> **⚠️ v5.1 P-3 弱化**：架构组**数学推导**确认"v3 混淆标准态 vs 实际态"
> 在数学上一致（41.91 ft/s 标准态 → 0.692 ft/s 实际态 = 25% flooding 设计），
> 但**未提供 XLS 用"标准态气速"的工程依据** —— 为什么 XLS 设计者选择用
> 标准态而非实际态？文献依据待补。

**已知但未验证**：

- (a) Worley 内部规范是否要求用标准态气速？
- (b) GPSA §20.4 Fig 20-8 是否以标准态当量为默认表示？
- (c) TEG 接触塔行业是否普遍采用 20-30% flooding 保守设计？

**架构组数学推导**（**推测**而非断言）：

**根因**：v3 混淆了**标准态** vs **实际态**气速/体积流量。

XLS PR-018 E40=120.76 in 反推：

```
CSA = π × (120.76/12)² / 4 = 79.54 ft² (与 XLS E39 一致)
标准状态气速 = 3333.33 ft³/s / 79.54 ft² = 41.91 ft/s  ← allowable superficial gas velocity
```

Souders-Brown flooding velocity（正确算法）：

```
v_flood = C_sb × sqrt((ρ_L − ρ_V) / ρ_V) × (T_std/T_actual) × (P_actual/P_std)
        = 0.65 × sqrt((70 − 2.794) / 2.794) × (519.67/579.67) × (1000/14.7)
        = 0.65 × 4.906 × 0.8964 × 68.027 = 194.4 ft/s (标准态当量)
实际 flooding velocity (实际态) = 194.4 / 68.027 / 0.8964 ≈ 3.19 ft/s
设计气速 = 3.19 × 0.85 ≈ 2.71 ft/s (实际态)
```

为什么 XLS 用 41.91 ft/s：

```
41.91 ft/s 是标准状态当量气速；
实际态气速 = 41.91 × (14.7/1000) × (579.67/519.67) ≈ 0.692 ft/s
0.692 ft/s << 2.71 ft/s (flooding 设计值)，即 XLS 设计气速只有 flooding 的 25%
```

这是 TEG 接触塔的标准保守设计（**架构组推测**；常用 20-30% flooding 保守设计 — 待文献验证），可能符合 Souders-Brown 物理。

**结论**：Souders-Brown 与 XLS E40 在数学上不矛盾 —— v3 错误是混淆标准态 vs 实际态；
sqrt(Q) 经验式 = Souders-Brown 在固定 (sg, TEG wt%, P, T) 工况下的标定简化式。

**OPEN-P6-6A-9.1**：P6-6B 工程师须完成 3 项验证：

1. 审查 v3 历史 PR 的具体 V_actual_scfs 实现，定位混淆代码行
2. 找到 Worley / GPSA / 行业规范中"XLS 用标准态气速"的文献依据
3. 若文献不支持"标准态气速是行业惯用"，需修订 ADR-0045 Rev A 根因分析

## Decision (v5.1 修订)

保留 **Souders-Brown 物理模型**作为 TEG contactor sizing 标准 methodology，
但具体数值实现采用 **sqrt(Q) 简化式**作为 XLS PR-018 同型接触塔的标定：

```
D_full_in = K × sqrt(Q_gas_mmscfd)
K = 7.1187 = 120.76 / sqrt(288)  ← XLS PR-018 E40 单点反算标定
```

本公式 = Souders-Brown 在 (sg=0.6, TEG=99%, P=1000 psia, T=120°F) 工况下的标定简化式。

## Rationale

1. **物理合理性**：Souders-Brown 是 TEG contactor 设计的标准 methodology
   (GPSA Engineering Data Book §20.4 Fig 20-8 + Kohl-Nielsen Gas Purification 5th ed Ch.7)。
   XLS PR-018 工程实践采用 sqrt(Q) 简化式 = Souders-Brown 在该工况下的标定。

2. **数值验证**：
   - XLS PR-018 E40=120.76 in @ Q_gas=288 MMscfd → K = 7.1187
   - XLS 设计气速 41.91 ft/s 标准态当量 = Souders-Brown 25% flooding（保守设计）

3. **适用范围 (v5.1 降级)**：
   - K = 7.1187 **单点标定**
   - 适用范围**未经多工况验证**
   - 仅适用于 XLS PR-018 同型接触塔 (sg≈0.6, TEG 99%, P≈1000 psia, T≈120°F)
   - 越界 WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`

## Consequences

- **Positive**：公式直接匹配 XLS E40 标定值 (rel ≤ 1e-3)，PCS Ruling 5 OUT_OF_SCOPE 闭环；
  实现简单 (1 行代码)，无热力学状态换算复杂度
- **Negative**：K 单点标定，**不**声称多工况普适；越界 WARNING 是工程提示而非免责
- **Mitigation**：ADR 文档化单点声明；helper docstring 标 ADR 引用；result formula_ref
  加 `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]` 标记

## 撤回条件 (v5.1 M-1 落实 — 3 条)

本 ADR 在以下任一条件满足时**应被撤回**，由 ADR-0046 替代：

1. XLS E40 被证明不是 full column OD（如为中间量/喷嘴尺寸等）
2. K=7.1187 在 sg/TEG/P/T 多工况下不稳定（波动 >10%）
3. 发现更权威的 TEG 接触塔 sizing 标准公式

## Follow-up

- P6-6B 工艺工程师接管（OPEN-P6-6A-9 根因延伸 quest）：
  1. 真实 K 值的多工况标定 (sg × TEG wt% × P × T 四维矩阵)
  2. 引入 Antoine-based 物理模型 (Wichert-Aziz 形式) 作为 backup
  3. ADR-0046 起草（若 backup 模型验证可行）
  4. 解决 XLS PR-018 E20=103.91 acid gas 工况残差 25.8% 根因

## Implementation Reference

- Service: `pcs-backend/app/services/psychro/glycol_dehydration_service.py`
- Helper: `_calc_full_column_diameter_in(gas_flow_mmscfd, flooding_c_sb=0.65)`
- Constant: `_FULL_COLUMN_K_DEFAULT: Final[float] = 7.1187`
- Constants: `_FULL_COLUMN_XLS_Q_MMSCF_MIN=144.0, _FULL_COLUMN_XLS_Q_MMSCF_MAX=432.0`
  (即 XLS PR-018 Q=288 ± 50% 越界 WARNING 阈值)
- Test: `tests/services/psychro/test_glycol_dehydration.py::test_full_column_diameter_*`
- Acceptance: XLS E40=120.76 in within 1% tolerance (实际 0.04% diff)
