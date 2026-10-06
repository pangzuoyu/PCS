# PCS-NOTE — SPEC §3.2.4(3) 结论档数修订（3 档 → 4 档，新增「不可判」）

> **日期**: 2026-10-06
> **触发**: P7 Sprint 4 Task S4-2/S4-3（偏差报告与核算流程）落地，OpenAPI 比对发现
> **影响范围**: 偏差报告「结论」枚举；`can_confirm` 确认门禁；前端比对结果表渲染
> **状态**: 已落代码并测试（`tests/services/supplier/`，`deviation_report.py`）

按 PCS 项目规则「枚举/字段与 SPEC 冲突时以 OpenAPI 为准**并登记 SPEC 修订**」——
本文即该登记。**不修改 `spec/` 下的 V1.0 冻结原件**；同批的
`docs/PCS-NOTE-SPEC-3.2.4-电机功率规则修订-2026-10-06.md` 是同型先例。

---

## 1. SPEC 原文与冲突

`spec/工艺专用综合计算软件需求规格说明书 Web版 P7.md` §3.2.4(3) 定 **3 档**：

| 档位 | 语义 |
|------|------|
| 合格 | 实际值在 SPEC §3.2.4(2) 允许偏差内 |
| 警告 | 允许差异，但需重新校核 |
| 不合格 | 超出允许偏差 |

代码注释自己承认了这一点（`deviation_service.py`）：

> 第 4 档 `UNVERDICTABLE`（不可判）是本引擎在 SPEC 三档之外的补充

而 `pcs-frontend/src/types/api.d.ts` 已同步为 4 值 union：

```ts
Verdict = "QUALIFIED" | "WARNING" | "UNQUALIFIED" | "UNVERDICTABLE"
```

**冲突后果**：前端开发者按冻结的 `docs/PCS-UI-SPEC.md:1597`（`结论 合格/警告/不合格`）
实现比对结果表，只会渲染 3 色，第 4 档落到 else 分支。

## 2. 为什么必须加第 4 档（而不是把「不可判」并入合格）

两条独立理由，任一条都足以否决「并入合格」：

1. **SPEC 表内本就有 2 条无数值阈值的规则**：材质「不得低于设计要求」是**序数比较**，
   机器判不了；转速/叶轮直径「允许差异需重新校核」没有百分比带。表头又明写
   「**以泵为例**」，非泵设备参数必然落不到规则。
2. **设计值可能缺失**：`design_parameters_json` 只覆盖 `PUMP_DESIGN` 的 17 个
   蜡油加氢泵位号，tag 集之外的设备全部「缺设计值」。

把「判不了」并入「合格」会让 SPEC §3.2.4(4) 的确认门禁形同虚设——**一个从未被
测量的值能拿到「已确认」**。故独立成档，且**不可确认**（fail-closed）。

## 3. 修订内容

| 项 | 修订前 | 修订后 |
|---|---|---|
| 结论枚举 | 3 档 | 4 档，追加 `UNVERDICTABLE`（不可判，灰） |
| `can_confirm` | 阻断不合格 | 阻断不合格 **与** 不可判 |
| 前端渲染 | 3 色 | 4 色，第 4 档需明确视觉（建议灰色 + 「需人工核对」文案） |

## 4. 覆盖面范围限定（与 #8 裁决同源）

「应检参数集须全部有实测值」这条 fail-closed **本轮仅对泵生效**：

- 泵的应检集可从 `PUMP_DESIGN` 的设计键推导（SPEC §3.2.4(2) 六条允许偏差）；
- 非泵设备无设计值 → 报告行集为空 → `can_confirm` 恒 False，**已是事实上的
  fail-closed**，不会误确认；
- 非泵设备的应检参数表机制留到其数据模型落地时再建 —— 那时才谈得上
  「哪些参数应检」，在此之前凭空造表反而会拒掉合法录入。

## 5. 附带登记：`EVENT_ID_CONFLICT` 需要 per-instance 信息

客户端按 `code -> ui_behavior` 建映射（`ui_behavior` 是 **per-code**）。但
`EVENT_ID_CONFLICT` 同码下有两种情形：

| 情形 | `detail.retryable` | 语义 |
|---|---|---|
| 同一 event_id 携带**不同** payload | `false` | **上游 bug**，重试无用 |
| 撞主键但对方事务尚未对本读可见 | `true` | 并发竞态，重试有意义 |

「重试」是 per-instance 的，压不进 per-code 的 `ui_behavior`。**显式承认这是范式
特例**：`EVENT_ID_CONFLICT` 的 `ui_behavior` 标 `RETRY_IF_DETAIL_SAYS_SO`，客户端
按 `detail.retryable` 分流。（未选另两条路：扩展 `ui_behavior` 支持 per-instance
条件是大改；拆成两个复合 code 会把 instance 差异错放进 code 空间。）

## 6. 落地位置

| 项 | 位置 |
|---|---|
| 枚举定义 | `pcs-backend/app/schemas/supplier.py::Verdict` |
| fail-closed 门禁 | `deviation_report.py::can_confirm` |
| 引擎 | `deviation_service.py`（`UNVERDICTABLE` 及各 kind 的产出条件） |
| 前端类型 | `pcs-frontend/src/types/api.d.ts`（随 OpenAPI 契约重生成） |
| UI-SPEC | §7.14 结论枚举补第 4 档 + §12.4 修订记录追加一行 |

## 7. 关联

- 同批修订：`docs/PCS-NOTE-SPEC-3.2.4-电机功率规则修订-2026-10-06.md`
- ce-code-review 报告：`docs/ce-code-review/20261006-sprint4/report.md`（#25；#4 错误码注册；#8 覆盖面裁决）