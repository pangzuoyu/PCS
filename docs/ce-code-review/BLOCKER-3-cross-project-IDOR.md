# BLOCKER-3: 跨项目 IDOR (Insecure Direct Object Reference)

- **编号**: BLOCKER-3
- **登记**: 2026-10-01 (P7 Sprint 1 retrospective review)
- **影响范围**: PCS 全 API 端点（pre-existing across PCS）
- **根因**: 每个 endpoint 信任 client 传入的 `project_id`，未与 `current_actor.user_id` 的 UserProject 关联做 ACL 校验

## 发现来源

F-P0-004 (P7 Sprint 1 retrospective review, P0 BLOCKING):
- `pcs-backend/app/api/v1/equip_list.py:1` 起所有 endpoint
- 端点接受 `project_id: UUID` 路径/query/header 参数，直接用做 ORM 查询条件
- 当前 actor (`current_actor.user_id`) 未参与查询过滤 → 用户 A 可读用户 B 的项目数据

F-P1-005 (P7 Sprint 2 review, P1 → 升级为同源 BLOCKER-3):
- 同一根因（per process_engineering_rulings `F-P1-005_sprint1_F-P0-004_same_root`）

## 关联根因分析

per `synthesized-findings.json` §F-P1-005_sprint1_F-P0-004_same_root:
> F-P0-003 (audit bypass) 是 F-P0-004 (IDOR) 的放大器. 修复顺序:
> 先 F-P0-003 恢复 audit trail; F-P0-004 可延后 (登记 BLOCKER-3).
> 因为有了 audit trail, 即使 IDOR 存在, 也能被审计发现.

**F-P0-003 已修复** (本次 hotfix 批) → audit trail 恢复 → IDOR 利用痕迹可被 audit 捕获

## 修复范围（不在 P7 hotfix 批内）

**P7-7+ UserProject model**: PCS 需新增 `user_projects` 关联表
- `(user_id, project_id, role_in_project)` 三键主键
- 每个 API endpoint 加 `_check_user_project_access(db, current_actor, project_id)` 守卫
- 覆盖范围：Sprint 1+2 已落的所有 endpoint（约 30+ routes）

**预估工时**: 2-3 人周（覆盖全 endpoint + 测试 + review）

## 修复前置条件

- [ ] F-P0-003 audit trail 修复落地 (P7-S1-HOTFIX-A 本批) ✅
- [ ] P7-7 sprint 立项（与 P7 sprint 主线对齐）
- [ ] UserProject model 评审（架构组 Q1 决议）

## 临时缓解措施（hotfix 后）

1. Audit trail 现在会记录 actor + project_id + endpoint（F-P0-003 修复）
2. 运营监控：audit_logs 跨用户访问异常检测（人工 review）
3. 网络层 ACL：单用户单项目场景下，project_id 应等于 current_actor 的 primary project

## 相关 Rulings / Findings

- F-P0-004 (P7 Sprint 1 retrospective)
- F-P1-005 (P7 Sprint 2 review)
- process_engineering_ruling `F-P1-005_sprint1_F-P0-004_same_root`
- process_engineering_ruling `F-P0-004_BLOCKER_3_registration`

## 状态

- **登记**: 2026-10-01 (Sprint 1 retrospective review)
- **修复优先级**: P7-7+ (不在 P7 sprint 内)
- **审计追溯**: F-P0-003 修复后，所有跨项目访问会留 audit trace
