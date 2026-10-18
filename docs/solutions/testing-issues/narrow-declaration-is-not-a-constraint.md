---
module: 前端契约层 + StateBadge 组件
date: 2026-10-19
problem_type: testing_issue
component: testing_framework
severity: high
symptoms:
  - "看到 `MODULE_ACTIVATED.SIM` 只有 4 态，就断言「物流记录只有 4 态」，并据此建议把 `Stream['sign_status']` 收窄成 4 态"
  - "看到样式 UI 没有写入端点，就断言「这个需求不存在」—— 实际需求在 SPEC，缺的是地基"
  - "`STATUS_META[status] ?? STATUS_META.DRAFT`：一个 ACTIVE 的管子等级在页面上显示「草稿」，用户不会报错，会基于错误信息做决策"
  - "PipeClassListPage 在生产上整页空白，而 6 条组件测试全绿"
root_cause: inferring_contract_semantics_from_local_code_shape
resolution_type: types_and_tests
framework_version: TypeScript 5.x / vitest 2.1.9 / React 18 / jq
related_components:
  - frontend
  - testing_framework
  - contract
tags:
  - inference-error
  - constraint-vs-emphasis
  - compile-time-guard
  - silent-fallback
  - false-green
  - single-developer
---

# 「窄的类型声明」是有意的约束，还是无意的遗漏？

## 元问题

本会话（以及更早的样式 UI 那次）两次犯同一个错：**用代码的局部形态
推断契约的整体语义**。

| 看到的局部 | 推断出的结论 | 实际 |
|---|---|---|
| 样式 UI 没有写入端点 | 「需求不存在」 | 需求在 SPEC，缺的是地基 |
| `MODULE_ACTIVATED.SIM` 只有 4 态 | 「物流只有 4 态」 | 它是**强调表**（只管 opacity），物流有 9 态 |

两次都发生在**单人开发**里 —— 没有第二个人问「你确定吗」。
危险之处在于推断出的结论**读起来完全合理**，而且能被后续的改动「印证」：
一旦按 4 态收窄了类型，类型检查就会反过来确认这个错误结论。

## 判别方法：看那份「窄」的数据有没有运行时消费者在依赖它做校验

| | 有校验逻辑 | 只是外观/强调 | 结论 |
|---|---|---|---|
| `MODULE_ACTIVATED` | 无 —— 只喂 `opacity: isActive ? 1 : 0.4` | ✓ | **强调表**，不是词表 |
| `STATE_META` 的兜底分支 | 有 —— `?? STATUS_META.DRAFT` 会**替换**未知值 | | **约束**，而且是**错的**约束 |

即：**一个窄的声明，要么在做校验（约束），要么只是在做展示（强调）。
看它被消费的地方，不要看它的形状。**

`MODULE_ACTIVATED` 若被提升成编译期词表，会把一个「渲染强调」误升成
「合法性约束」—— 于��合法的 `STALE`（后端 `StreamSignStatus` 九态之一，
`stream_service.py:258` 的锁定检查逐个点名了它）被 `tsc` 拒绝。
**那是比现状更糟的回归**：把一个假绿换成��个假红。

## 推论：窄的东西要问「谁在依赖它」

发现「类型声明比实际值窄」时，先问：这个窄是**有意的约束**，还是**无意的遗漏**。
区分方法如上表。

`types/stream.ts` 的 `sign_status` 只声明 5 态而后端有 9 态，
是**遗漏**（少声明 CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE），
不是「多声明了 STALE」—— 后者才是我最初的误判。

## 真正的约束该长什么样

`StateBadge` 现在的做法：props 用**判别联合**而不是「module + 一个宽 status」。

```ts
export type StateBadgeProps = StateBadgeBase & (
  | { module: 'PIPE_CLASS'; status: PipeClassStatus }
  | { module?: SignModule;      status: RecordSignStatus }
);
```

于是 `module="PIPE_CLASS" status="CHECKED"` 与 `module="PIPE" status="ACTIVE"`
**编译期就报错**（已用探针实测）。宽 status 的话两种都能过 `tsc`，
类型系统对「module/status 组合」零保护。

⚠️ 判别联合**拦不住后端返回的裸 string**（契约 `PipeClassResponse.status`
没写 Literal），运行时那一层要单独兜：

```ts
const meta = STATUS_META[status];
if (!meta) return unknownBadge(status, size);   // dev 抛错 / prod「未知状态: X」
```

**绝不回落到 `STATUS_META.DRAFT`。** 那不是兜底，是语义改写：
一个**已生效**的管子等级显示「草稿」，用户不会报错（他不知道本该显示什么），
他会基于错误信息做决策（「这个等级还没生效，不能用于设计」）。

与 `definitionBody.ts` 给缺 `source` 的条件伪造 `'EQUIP_LIST'`、
`report_service` 静默吞掉审计写失败同族：
**缺失的值被填成某个默认值，而不是显式失败。**

## 同一族：fixture 与被测对象共用一份错误类型

`PipeClassListPage` 的 6 条测试全绿，而页面在生产上整页空白。
原因不是断言写错，是 **fixture 用手写类型构造，页面读同一份手写类型** ——
「页面读什么」与「fixture 有什么」同源，于是永远对得上，互不设防。

```ts
// 掩盖 bug-180 的写法（手写副本）
const classes: PipeClass[] = [{ pipe_class_id: 'pc-1', code: 'ASME B31.3', ... }];

// 修法：类型本身就是契约，缺字段在编译期就红
const classes: PipeClass[] = [{ class_id: 'pc-1', class_name: 'ASME B31.3', ... }];
```

`src/mocks/seed/pipe-classes.ts` 是同一个病的另一个实例 ——
mock 返手写形状，于是**替页面遮着**，让缺陷在 dev 里不可见。

⇒ **mock 与契约一致是正确性的一部分**，不是开发体验问题。
mock 越宽松，它替页面/后端扛的越多，而那些差异平时不可见。

## 给单人开发的两条自查

1. **要收窄/放宽一个类型前**，先打开那个声明的**每一处消费点**，
   确认它在做校验还是在做外观。
2. **断言新代码时，fixture 只能用契约类型构造**。如果 fixture 与被测对象
   共用一份错误类型，测试数量再多也是零信号。
