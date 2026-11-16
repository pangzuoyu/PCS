"""WF-PATH-02/03 + E2E-011/012：交付物 Rev 与代录客户批准（P10-B · T5）。

## WF-PATH-02：Rev 递增

`issue` 一次 ⇒ rev **+1** ⇒ 且**旧 rev 的 snapshot 仍可读**（历史不能被抹掉）。

## WF-PATH-03：代录客户批准（★ Review Focus #2）

代录**必须落「谁代录的」** ⇒ `customer_approval_proxy_by` **非空**
⇒ 否则事后无法追责 ⇒ 客户投诉时查不到人。

## ⚠️ 二次认证要桩掉 LDAP（**只桩认证那一步**）

`verify_secondary_auth` ⇒ `ldap_client.authenticate(username, password)`
⇒ 车道**没有 LDAP** ⇒ ⇒ 只桩**认证那一步**（返回成功）
⇒ ⚠️ **不**桩「代录」本身的逻辑 ⇒ 「谁代录的」这条**照常被验**。
"""
from __future__ import annotations

import pytest

from tests.e2e_flows.helpers import make_record  # noqa: F401  （T5 共用 helper）


@pytest.mark.e2e
async def test_wf_path_02_issuing_a_new_rev_bumps_the_version(
    e2e_client, role_headers, e2e_seed
):
    """`issue` ⇒ rev +1 ⇒ 旧 rev 的 snapshot 仍可读。"""
    headers = role_headers("DESIGNER")
    deliverable_id = str(e2e_seed["deliverable_id"])

    before = await e2e_client.get(
        f"/api/v1/deliverables/{deliverable_id}/versions", headers=headers
    )
    assert before.status_code == 200, (
        f"读版本列表失败：{before.status_code} {before.text[:300]}"
    )
    before_body = before.json()
    before_versions = before_body["versions"] if isinstance(before_body, dict) else before_body
    before_revs = {v.get("rev") for v in before_versions}

    issued = await e2e_client.post(
        f"/api/v1/deliverables/{deliverable_id}/issue",
        json={"version_purpose": "ISSUED_FOR_DESIGN", "description": "E2E 场景签发"},
        headers=headers,
    )
    assert issued.status_code in (200, 201), (
        f"签发失败：{issued.status_code} {issued.text[:300]}"
    )
    issued_body = issued.json()
    new_rev = issued_body.get("rev") or issued_body.get("version", {}).get("rev")

    after = await e2e_client.get(
        f"/api/v1/deliverables/{deliverable_id}/versions", headers=headers
    )
    after_body = after.json()
    after_versions = after_body["versions"] if isinstance(after_body, dict) else after_body
    after_revs = {v.get("rev") for v in after_versions}

    assert after_revs > before_revs, f"版本没增加：{before_revs} → {after_revs}"
    assert new_rev in after_revs, f"签发返回的 rev {new_rev!r} 不在版本列表里：{after_revs}"

    # 旧 rev 的 snapshot **仍可读**（历史不能被抹掉）
    for old_rev in before_revs:
        snapshot = await e2e_client.get(
            f"/api/v1/deliverables/{deliverable_id}/versions/{old_rev}/snapshot",
            headers=headers,
        )
        assert snapshot.status_code == 200, (
            f"旧 rev {old_rev!r} 的 snapshot 读不到了：{snapshot.status_code}"
        )


@pytest.mark.e2e
async def test_wf_path_03_proxy_customer_approval_records_who_recorded_it(
    e2e_client, role_headers, e2e_seed, monkeypatch
):
    """代录客户批准 ⇒ `customer_approval_proxy_by` = 代录人 id（**非空**）。

    ⚠️ **二次认证要桩 LDAP**（车道没有 LDAP）⇒ 只桩**认证那一步**
    ⇒ 「谁代录的」这条逻辑**照常被验**。
    """
    from app.services import ldap_client

    monkeypatch.setattr(
        ldap_client, "authenticate", lambda username, password: True, raising=True
    )

    # ⚠️ 签发要 DESIGNER / SYSTEM_ADMIN（`_ISSUE_ROLES`）⇒ 用 **e2e-designer** 签发
    issuer = role_headers("DESIGNER")
    # ⚠️ **代录人不得是该交付物的设计人**（ADR-0007 ⇒ 403
    # `PROXY_RECORDER_IS_DESIGNER`）⇒ ⇒ 代录人（e2e-admin）≠ 设计人（e2e-designer）
    # ⇒ ⚠️ 且代录端点本身要 DESIGNER / SYSTEM_ADMIN（`_ISSUE_ROLES`）
    # ⇒ ⇒ APPROVER **不行**（403）⇒ ⇒ 组合只能是「DESIGNER 签发 + SYSTEM_ADMIN 代录」
    headers = role_headers("SYSTEM_ADMIN")
    deliverable_id = str(e2e_seed["deliverable_id"])

    # ① 先签发一个版本（代录是针对某个版本的）
    # ⚠️ **换一个 version_purpose** —— 同一目的已有版本 ⇒
    # **409 `DELIVERABLE_ALREADY_ISSUED`**（每种目的只能有一个版本）
    issued = await e2e_client.post(
        f"/api/v1/deliverables/{deliverable_id}/issue",
        json={"version_purpose": "CUSTOMER_REVIEW", "description": "E2E 代录场景"},
        headers=issuer,
    )
    assert issued.status_code in (200, 201), (
        f"签发失败：{issued.status_code} {issued.text[:300]}"
    )
    issued_body = issued.json()
    version_id = issued_body.get("version_id") or issued_body.get("version", {}).get(
        "version_id"
    )
    assert version_id, f"签发没返回 version_id：{issued_body}"

    # ② 代录客户批准
    # ⚠️ **`file_path` 必须在存储根之内**（`var/reports`）⇒ 逃逸出去 ⇒
    # **400 `REPORT_PATH_ESCAPE`** ⇒ ⇒ 附件文件也要真的建出来
    from pathlib import Path as _Path

    storage_root = _Path(__file__).resolve().parents[2] / "var" / "reports"
    storage_root.mkdir(parents=True, exist_ok=True)
    attachment = storage_root / "e2e-customer-approval.pdf"
    attachment.write_bytes(b"%PDF-1.4\n% e2e customer approval\n")

    proxied = await e2e_client.post(
        f"/api/v1/deliverables/{deliverable_id}/customer-approval/proxy",
        json={
            "version_id": str(version_id),
            "file_path": str(attachment),
            "file_name": "customer-approval.pdf",
            "file_type": "PDF",
            "approver_name": "客户方代表",
            "approval_date": "2026-11-16",
            "approval_method": "EMAIL",
            # ⚠️ 二次认证是**操作者本人**（代录人）的凭据 ⇒ 用另一个 PCS 账号
            "secondary_username": "e2e-reviewer",
            "secondary_password": "e2e-lane-placeholder",
        },
        headers=headers,
    )
    assert proxied.status_code in (200, 201), (
        f"代录客户批准失败：{proxied.status_code} {proxied.text[:400]}"
    )
    body = proxied.json()
    assert body.get("is_proxy") is True, f"代录没标 is_proxy：{body}"
    assert body.get("proxied_at"), f"代录没记时间：{body}"

    # ⚠️ **「谁代录的」不在响应里**（响应只有 attachment/approver/method/is_proxy）
    # ⇒ ⇒ 直查那一行 ⇒ ⇒ 这才是 Review Focus #2 的落点
    # ⇒ ⚠️ 断言必须是**具体那个人的 id**（不是「非空」）
    from sqlalchemy import text as _text

    async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
        row = (
            await session.execute(
                _text(
                    "SELECT customer_approval_proxy_by, customer_approval_is_proxy "
                    "FROM deliverables WHERE deliverable_id = :did"
                ),
                {"did": deliverable_id},
            )
        ).mappings().one()

    expected_proxy_by = str(e2e_seed["users"]["e2e-admin"])
    assert row["customer_approval_proxy_by"] is not None, (
        "代录**没落谁代录的**（customer_approval_proxy_by 为空）⇒ 事后无法追责"
    )
    assert str(row["customer_approval_proxy_by"]) == expected_proxy_by, (
        f"代录人不是 e2e-admin：{row['customer_approval_proxy_by']} ≠ {expected_proxy_by}"
    )
