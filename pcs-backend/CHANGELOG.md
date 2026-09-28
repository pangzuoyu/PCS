# PCS Backend Changelog

记录 pcs-backend 服务层的破坏性变更与 API 演进。本文件是 backend 级变更账本，git-ignored 的 SDD ledger（`.superpowers/sdd/...`）记录实施细节。

---

## [Unreleased]

### Breaking Changes

- **hydrate_inhibition_service**: 字段名 `hydrate_depression_c` → `hydrate_depression_f`（语义 Bug：原字段值实际是 °F，符合 Hammerschmidt 1934 论文 K °F scale convention）。新增派生字段 `hydrate_depression_c = _f × 5/9`。原字段值保留为 `hydrate_depression_c_legacy` deprecated 标记。OPEN-P6-6A-3 真正关闭。

  - 主输出：`hydrate_depression_f: float`（°F；Hammerschmidt 1934 Eq 直接输出）
  - 派生 °C：`hydrate_depression_c: float`（= `_f × 5/9`）
  - DEPRECATED：`hydrate_depression_c_legacy: float`（== `_f`，向后兼容旧调用方）
  - 受影响调用方：`HydrateInhibitionResult`（frozen dataclass）；迁移方式：把 `result.hydrate_depression_c` 改成 `result.hydrate_depression_f`（若需要 °C，改为 `result.hydrate_depression_c`）。

---