# P45 BATCH3 前端类型手动迁移登记

> P5 frontend 收口阶段，前端模块类型由 OpenAPI regen (`openapi-typescript`) 自动生成尚未纳入 CI 流水线（V1.4 阶段统一处理）。本批次 P5-3 PSV / P5-4 HEAT 等模块需要前端先行落地，因此类型由前端工程师手写并在 `types/<module>.ts` 顶部以 `@migrate-when` 标注约定替换时机。

## 迁移约定

- `@migrate-when`：触发替换的条件（例如 "P5 全栈收口 + openapi-typescript regen 后"）。
- `@target`：替换目标（默认 `src/types/api.d.ts` 的对应 schema）。
- `@reason`：为何手写（regen 阻塞 / 后端契约先行 / P5 frontend 闭环阻塞）。

V1.4 阶段 `openapi-typescript` 接入 CI 后，扫描本文件 + `types/*.ts` 顶部注释，批量删除手写类型并切换至 regen 生成的 `api.d.ts` 路径。

## 登记条目

| 模块 | 文件 | 后端 OpenAPI commit | `@migrate-when` | 备注 |
|------|------|---------------------|------------------|------|
| PSV  | `src/types/psv.ts`         | 93627a7 | P5-3 全栈收口 + openapi-typescript regen 后 | P5-3 frontend（Task 1）首登 |
| HEAT | `src/types/heat.ts`        | 96165e1 | P5-4 全栈收口 + openapi-typescript regen 后 | P5-4 frontend（Task 1）本批次登 |

## 校验

```bash
grep -l "@migrate-when" pcs-frontend/src/types/*.ts
```

期望：`psv.ts` + `heat.ts` 命中（V1.4 阶段未引入新模块前不变）。