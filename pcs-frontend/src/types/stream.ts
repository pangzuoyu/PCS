/**
 * Stream 类型定义（P45-3-1 / Task 28）。
 *
 * SPEC §7.7 SIM 物流：
 * - 物流号 / 名称 / 相态 / 温压 / 流量 / 组成 / 状态
 *
 * TODO(api-migration): 此为 V1 极简版前端 mock props shape，与后端
 * StreamResponse 字段命名不一致（前端 temperature_c / pressure_mpa /
 * total_mass_flow_kg_h vs 后端 temp / press / mass_flow）。P5-1 完成
 * 后：
 * 1) 后端 OpenAPI 暴露完整 stream/tag 路径参数 → 跑 npm run api:gen
 * 2) 由 src/types/api.d.ts 的 StreamResponse 替换本页类型
 * 3) 现有 Page-level props shape 升级为 API DTO
 *
 * 见 docs/superpowers/plans/2026-09-16-p45-frontend-sprint-batch3.md
 * §"P5 契约冻结点"
 */

import type { components } from './api';

/**
 * 相态 —— **直接取契约的 `StreamPhase`**，不再手写。
 *
 * 这份手写词表改过两次（`LIQUID|VAPOR|MIXED|AQUEOUS` → 四值），
 * 每次都是因为后端描述变了才知道。**手写副本不会自己变对**，所以现在
 * 它就是契约类型，并配一条双向编译期断言（见 `streamPhaseLabel` 上方）。
 *
 * ⚠️ SPEC P3-SIM 的相态表只列 3 值（漏 SOLID），而
 * `import_service._phase_norm` 真的会产出 SOLID ⇒ SPEC 待修订。
 */

// ⚠️ `tag_number` 已删（2026-10-19，用户裁决）。
// 物流是**流量**不是设备，没有位号 —— `tag_number` 是 `TaggedRecordMixin`
// 给**计算记录**（FlashResult / PipeResult …）的 NOT NULL 唯一字段。
// 全仓 `spec/*.md` 里的 tag_number 也都指设备位号，`streams` 侧零命中；
// 契约 `StreamResponse` 同样没有它。真值是页面此前在显示 `undefined`。
// 首列改用 `stream_name`（用户裁决：不删首列 —— 它是标识，删了行就分不清）。

// ⚠️ `StreamSubphase` 已删（2026-10-19，用户裁决「砍列」）。
// 后端**根本没有子相态这个概念** —— `grep -rn subphase app/` 在
// schemas / ORM / enums 里**零命中**。前端此前细化的是后端没细化的东西，
// 页面读它永远是 `undefined`，于是那一栏恒不显示（静默失效）。

/** SIM 物流条目：流号 + 流名 + 主相态 + 温压 + 双流量 + 组成 + 9 态机签名状态。 */
/**
 * SIM 物流条目 —— **直接就是契约的 `StreamResponse`**，不再手写第二份。
 *
 * ⚠️ 手写副本缺 5 个契约**必填**字段（`case_type` / `data_mode` /
 * `source_type` / `approval_depth` / `created_at`），于是：
 * mock 的 seed 也不带它们 ⇒ 通过 ajv 的 seed 一旦被校验就红
 * （`tests/mocks/handlers.test.ts` 的「响应体 ↔ OpenAPI」）。
 * 与 bug-180/187/188 同一族：**手写副本不会自己变对**。
 */
export type Stream = components['schemas']['StreamResponse'];

/** 契约的 `StreamPhase`（后端 `app/models/enums.py` 是唯一来源）。 */
export type StreamPhase = components['schemas']['StreamPhase'];

/**
 * 编译期守卫：本地词表必须**恰好**等于契约的。
 * 少一个 → 后端真值落进「未知相态: X」；多一个 → 契约里不存在的态被当成合法的。
 * 双向（`extends` 两个方向都查）。
 */
type _AssertPhaseAligned = StreamPhase extends NonNullable<Stream['phase']>
  ? NonNullable<Stream['phase']> extends StreamPhase ? true : never
  : never;
const _phaseAligned: _AssertPhaseAligned = true;
void _phaseAligned;



/**
 * 相态词表 —— 4 值。
 *
 * ⚠️ 契约 `StreamResponse.phase` 目前是 `string | null`（裸串，词表只写在
 * description 里），所以**这份词表在契约侧还没有对应物**。取值依据：
 * 后端 `conflict_resolver._VALID_PHASES` + `import_service._phase_norm`
 * （会产出 SOLID）。已登记 TODOS.md TODO-042：后端改成枚举后，
 * 这里也应改成契约类型。
 */
export const STREAM_PHASE_LABEL: Record<StreamPhase, string> = {
  LIQUID: '液相',
  VAPOR: '气相',
  MIXED: '混合',
  SOLID: '固相',
};

/**
 * 把契约的可空 `phase` 渲染成文案。
 *
 * ## 为什么需要这个函数
 *
 * 契约里 `phase?: string | null`，而 `STREAM_PHASE_LABEL` 是
 * `Record<StreamPhase, string>`。直接 `LABEL[p.phase]` 有两个问题：
 * 1. `null` 是合法值（后端可以不填相态），不是错误；
 * 2. 遇到**词表之外**的未知值，会静默渲染成空标签 —— 不报错、只是没内容。
 *
 * 两种都不是「填个默认值」该解决的：**没填**显示「未标注相态」，
 * **填错了**显示「未知相态: X」。两者都不丢信息（见 STATE_BADGE 那条同源教训）。
 */
export function streamPhaseLabel(phase: Stream['phase']): string {
  if (phase == null) return '未标注相态';
  const label = STREAM_PHASE_LABEL[phase];
  // ⚠️ 类型说这里不可能越界，但**DB 侧的 `streams.phase` 仍无 CHECK 约束**
  // （只有 `ck_streams_case_type`），且 `import_service._phase_norm` 对未知值
  // `return p` 原样放行 ⇒ 历史行/直接 SQL 写入仍可能是词表外的值。
  // 所以兜底保留：明示「未知相态: X」而不是静默空标签。
  return label ?? `未知相态: ${phase}`;
}

/** 同上，附带颜色。未知值给灰色，且**不吞掉原值**（调用方可自行展示）。 */
export function streamPhaseColor(phase: Stream['phase']): string {
  switch (phase) {
    case 'LIQUID': return 'blue';
    case 'VAPOR': return 'orange';
    case 'MIXED': return 'purple';
    case 'SOLID': return 'default';
    case null:
    case undefined: return 'default';
    default: return 'default';
  }
}
