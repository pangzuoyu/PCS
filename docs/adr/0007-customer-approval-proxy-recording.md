---
status: accepted
date: 2026-08-28
---

# 客户批准采用凭证代录：客户在系统外批准，内部授权人在系统内代录闭环 CUSTOMER 签署步骤

P0 认证只有公司 AD 的 5 个系统角色，无 CUSTOMER；SUP-005 却要求正式版（Rev 0/1/2）必须含客户签署且 customer_approval_date 必填。客户是业主公司人员，不会有公司 AD 账号，CUSTOMER 步骤物理上无人能在系统内执行。

决定 v1 采用凭证代录（INTERNAL_PROXY）：客户在系统外批准（邮件/正式信函/EDMS/签字文件），项目负责人/文控/审定在系统内"代录客户批准"——上传凭证附件（必填，SHA-256 哈希防篡改）、客户批准人姓名、批准日期、批准方式，代录人二次认证（AD 密码/MFA）。审计日志记录 CUSTOMER_APPROVAL_PROXIED，签署页客户栏显示"客户姓名（代录：X）"与本人签署区分。代录人不得是该交付物的设计人。客户退回同样代录退回，交付物回 DRAFT。v2 演进为外部签署链接（P10 后、需安全评审），v3 远期客户账号。

## Consequences

- CUSTOMER 步骤状态：CUSTOMER_PENDING（系统外交送）→ CUSTOMER_PROXIED（已代录）/ CUSTOMER_REJECTED（代录退回）。
- deliverables 新增客户批准字段组；新增 customer_approval_attachments 表（凭证附件，含 file_hash）。
- 代录权限（项目负责人/文控/审定，审核可配置）在项目模板 customer_approval_config 中配置。
- P1 状态机、P2 项目模板、P9 代录 UI 相应扩展。
