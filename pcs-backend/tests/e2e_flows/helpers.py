"""E2E 场景共用的调用 helper —— P10-B（T3）。

## 为什么要有这一层

- **载荷只写一处** —— 计算链的输入有 8~16 个字段 ⇒ 逐场景抄一遍 = 抄 N 遍
  ⇒ 改一处要改 N 处（而且改漏的那处**报错在响应体里**，极难定位）。
- **输入用合成数据** —— 与 `tests/api/v1/test_*_calc*.py` 的合成输入**同源**
  ⇒ ⚠️ **不用**根目录 `sample/`（不入 git ⇒ 别的机器没有 ⇒ 车道不可移植）。

## ⚠️ 计算链场景是「薄壳」

E2E 测的是**编排**（端点契约 · 结果落库 · 下游可见），
**不是算法**（算法已被单测覆盖）⇒ 断言落在「**200/201 + 响应体形状 +
落库行存在 + 下游列表能看到**」，**不重复**单测里的数值断言
（不写「管径 = 57.15 mm」这种）⇒ 避免两套数值断言漂移。
"""
from __future__ import annotations

import uuid
from typing import Any

#: 一段管段（管道计算的合成输入；与 `tests/services/pipe/test_pipe_chain.py` 同源）。
PIPE_SEGMENT: dict[str, Any] = {
    "fluid_phase": "LIQUID",
    "mass_flow_kg_s": 1.0,
    "density_kg_m3": 1000.0,
    "viscosity_pa_s": 1.0e-3,
    "pipe_diameter_m": 0.05,
    "pipe_roughness_m": 4.6e-5,
    "length_m": 10.0,
}

#: 离心泵曲线（与 `tests/api/v1/test_pump.py` 同源）。
PUMP_CURVE_POINTS: list[dict[str, Any]] = [
    {"flow_m3_s": 0.005, "head_m": 36.0, "efficiency": 0.60, "npshr_m": 1.5},
    {"flow_m3_s": 0.010, "head_m": 35.0, "efficiency": 0.68, "npshr_m": 2.0},
    {"flow_m3_s": 0.020, "head_m": 33.0, "efficiency": 0.78, "npshr_m": 2.5},
    {"flow_m3_s": 0.030, "head_m": 30.0, "efficiency": 0.80, "npshr_m": 3.2},
    {"flow_m3_s": 0.040, "head_m": 26.0, "efficiency": 0.78, "npshr_m": 4.0},
    {"flow_m3_s": 0.050, "head_m": 21.0, "efficiency": 0.70, "npshr_m": 5.0},
]


def pipe_chain_body(
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    tag_number: str,
) -> dict[str, Any]:
    """`POST /api/v1/pipe/calc-chain` 的请求体。"""
    return {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "source_stream_id": str(source_stream_id),
        "tag_number": tag_number,
        "inlet_pressure_pa": 200_000.0,
        "parallel_branches": 1,
        "segments": [dict(PIPE_SEGMENT)],
    }


def pump_chain_body(
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    tag_number: str,
) -> dict[str, Any]:
    """`POST /api/v1/pump/calc-chain` 的请求体。"""
    return {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "source_stream_id": str(source_stream_id),
        "tag_number": tag_number,
        "flow_m3_s": 0.030,
        "head_m": 30.0,
        "fluid_density_kg_m3": 1000.0,
        "fluid_viscosity_pa_s": 1.0e-3,
        "vapor_pressure_pa": 5_000.0,
        "system_pressure_pa": 150_000.0,
        "pump_curve": {
            "pump_tag": "P-1001",
            "pump_type": "CENTRIFUGAL",
            "speed_rpm": 2950.0,
            "points": [dict(p) for p in PUMP_CURVE_POINTS],
            "rated_flow_m3_s": 0.030,
            "rated_head_m": 30.0,
            "rated_efficiency": 0.80,
        },
        "suction_pipe_chain": {
            "segments": [dict(PIPE_SEGMENT)],
            "inlet_pressure_pa": 150_000.0,
            "inlet_temperature_K": 298.15,
            "parallel_branches": 1,
        },
    }


def psv_body(*, source_stream_id: uuid.UUID) -> dict[str, Any]:
    """`POST /api/v1/psv/calculate` 的请求体（FIRE 场景）。

    ⚠️ 参数是**工业级高压气体**（2 MPa / 700 K）—— 简化参数算出的面积
    远超 `T_max` ⇒ 公式无解（与 `tests/api/v1/test_psv_api.py` 同款）。
    """
    return {
        "source_stream_id": str(source_stream_id),
        "relief_scenario": "FIRE",
        "scenario_params": {
            "D_m": 1.0,
            "H_m": 5.0,
            "liquid_level_fraction": 0.5,
            "environment_factor_F": 1.0,
            "h_fg_j_per_kg": 350_000.0,
        },
        "sizing_params": {
            "relief_mass_flow_kgs": 0.005,
            "phase": "GAS",
            "P_back_pa": 2_000_000.0,
            "P_set_pa": 200_000.0,
            "T_k": 700.0,
            "M_kg_per_mol": 0.018,
            "Z": 1.0,
            "k_cp_ratio": 1.3,
        },
    }


def vessel_body(*, source_stream_id: uuid.UUID) -> dict[str, Any]:
    """`POST /api/v1/vessel/calculate` 的请求体。"""
    return {
        "source_stream_id": str(source_stream_id),
        "sizing": {
            "vessel_type": "VERTICAL",
            "rho_L_kg_m3": 850.0,
            "rho_V_kg_m3": 1.2,
            "liquid_flow_m3_s": 0.005,
            "vapor_flow_m3_s": 0.5,
            "residence_time_min": 5.0,
            "K_factor_ms": 0.10,
        },
        "hydraulics": {
            "D_m": 2.0,
            "L_m": 5.0,
            "h0_m": 1.0,
            "d_orifice_m": 0.05,
            "Cd_orifice": 0.62,
            "Q_in_liquid_m3_s": 0.005,
            "d_overflow_m": 0.1,
            "h_overflow_m": 0.3,
            "Cd_overflow": 0.62,
            "orientation": "VERTICAL",
        },
    }


def flash_body(*, stream_id: uuid.UUID) -> dict[str, Any]:
    """`POST /api/v1/flash/calculate` 的请求体（PT_FLASH · SI 单位）。"""
    return {
        "calc_type": "PT_FLASH",
        "stream_id": str(stream_id),
        "T_K": 335.0,
        "P_Pa": 1.0e6,
    }


async def advance_stream_to_checked(
    client, stream_id: uuid.UUID, *, role_headers
) -> dict[str, Any]:
    """把一条物流从 DRAFT 推进到 **CHECKED**（走**真实端点**）。

    ⚠️ 为什么需要它：计算链的入口守卫要求输入物流 `CHECKED`
    ⇒ 而 PRO/II 导入出来的物流是 **DRAFT** ⇒ 不推进就 403。

    ⚠️ **两个角色的分工**（端点各自的 ACL）：
    - `POST /streams/{id}/submit` ⇒ DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN
      （⇒ 用 `e2e-designer`）
    - `POST /streams/{id}/approve` ⇒ **PROCESS_CONTROLLER / SYSTEM_ADMIN**
      （⇒ ⚠️ **CHECKER 不行** ⇒ 用 `e2e-admin`）

    ⚠️ 组成门禁：`composition_json is None` ⇒ **跳过**（纯物质）
    ⇒ PRO/II 导入的物流正是这种 ⇒ 送审不会被 422 挡住。
    """
    submitted = await client.post(
        f"/api/v1/streams/{stream_id}/submit",
        headers=role_headers("DESIGNER"),
    )
    assert submitted.status_code == 200, (
        f"物流送审失败：{submitted.status_code} {submitted.text[:300]}"
    )
    approved = await client.post(
        f"/api/v1/streams/{stream_id}/approve",
        headers=role_headers("SYSTEM_ADMIN"),
    )
    assert approved.status_code == 200, (
        f"物流批准失败：{approved.status_code} {approved.text[:300]}"
    )
    return approved.json()


#: 记录批准链的 3 级角色（**与种子的签署矩阵一致** ⇒ CHECKER→REVIEWER→APPROVER）。
#:
#: ⚠️ **提交人（DESIGNER）不在链里** —— `submit-approval` 的自审闸
#: （`APPROVAL_SELF_REVIEW_FORBIDDEN`）在「提交人的角色出现在链里」时 403
#: ⇒ 链里有 DESIGNER ⇒ 整条链走不通。
CHAIN_ROLES: tuple[str, ...] = ("CHECKER", "REVIEWER", "APPROVER")


async def make_record(
    e2e_client,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    tag_number: str,
) -> uuid.UUID:
    """造一条 **DRAFT** 记录（`PipingResult`）⇒ 返回它的 id。

    ⚠️ **为什么直接写库**：仓里**没有**建记录的端点（只有状态转移端点）
    ⇒ ⇒ 「起点态」只能由 fixture/种子造 ⇒ 而**状态必须由场景走真实端点推进**
    （否则 E2E 只是断言一个摆好的状态 ⇒ 状态机坏了 E2E 也绿）。

    ⚠️ **载荷用模板**（D8：一处真相源）⇒ 场景不各写一份 21 字段字典。
    ⚠️ **`record_hash` 要算** —— CIA（变更影响）按哈希判定「结果变了没」
    ⇒ ⇒ 空哈希 ⇒ 永远判定「没变」。
    """
    from app.models.calc import PipingResult
    from app.services.calc_lineage import compute_record_hash
    from scripts.seed_e2e_flows import PIPING_RECORD_PAYLOAD

    async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
        record = PipingResult(
            **{**PIPING_RECORD_PAYLOAD},
            project_id=project_id,
            workspace_id=workspace_id,
            tag_number=tag_number,
        )
        session.add(record)
        await session.flush()
        # ⚠️ 必须在 flush 之后算（`compute_record_hash` 读的是**已落库**的行）
        record.record_hash = compute_record_hash(record)
        await session.commit()
        return record.pipe_id


async def submit_for_approval(
    client, *, module: str, record_id: uuid.UUID, headers: dict[str, str]
) -> dict[str, Any]:
    """`POST /records/{module}/{id}/submit-approval` ⇒ DRAFT → IN_APPROVAL。"""
    resp = await client.post(
        f"/api/v1/records/{module}/{record_id}/submit-approval",
        json={"reason": "E2E 场景送审"},
        headers=headers,
    )
    assert resp.status_code == 200, (
        f"送审失败：{resp.status_code} {resp.text[:300]}"
    )
    return resp.json()


async def approval_step(
    client,
    *,
    module: str,
    record_id: uuid.UUID,
    headers: dict[str, str],
    decision: str = "PASS",
    reason: str | None = None,
) -> dict[str, Any]:
    """`POST /records/{module}/{id}/approval-step` ⇒ 批当前这一步。

    ⚠️ **`decision` 的词表是 `PASS` / `REJECT`**（不是 APPROVE/REJECT）
    ⇒ 写错 ⇒ 422 `literal_error` ⇒ 「端点坏了」的假象。
    """
    body: dict[str, Any] = {"decision": decision}
    if reason is not None:
        body["reason"] = reason
    resp = await client.post(
        f"/api/v1/records/{module}/{record_id}/approval-step",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, (
        f"approval-step 失败（decision={decision}）：{resp.status_code} {resp.text[:300]}"
    )
    return resp.json()


async def approve_record_chain(
    client,
    *,
    module: str,
    record_id: uuid.UUID,
    role_headers,
    decision: str = "PASS",
    until_role: str | None = None,
) -> list[dict[str, Any]]:
    """送审 + 走完（或走完到）批准链 ⇒ 每一步**换角色**。

    ⚠️ **每一步都要用对的那一步的角色** —— 端点要求
    `actor.role == record.approval_role`（= 矩阵这一步该谁签）
    ⇒ 用错角色 ⇒ 403 `APPROVAL_ROLE_MISMATCH` ⇒ 链条卡死。

    ⚠️ `until_role` ⇒ 只走到**那个角色那一步**（含）⇒ 用来测「驳回后重交」。
    """
    steps: list[dict[str, Any]] = []
    # ⚠️ **两处都要 await** —— 漏一个 ⇒ 请求根本没发出去 ⇒ 记录停在 DRAFT
    # ⇒ 症状是「409 APPROVAL_NOT_ACTIVE / 记录还是 DRAFT」⇒ 看着像端点坏了。
    await submit_for_approval(
        client, module=module, record_id=record_id, headers=role_headers("DESIGNER")
    )
    return await approve_record_steps(
        client,
        module=module,
        record_id=record_id,
        role_headers=role_headers,
        decision=decision,
        until_role=until_role,
    )


async def approve_record_steps(
    client,
    *,
    module: str,
    record_id: uuid.UUID,
    role_headers,
    decision: str = "PASS",
    until_role: str | None = None,
) -> list[dict[str, Any]]:
    """**只走链**（不送审）⇒ 每一步换角色。

    ⚠️ 与 `approve_record_chain` 分开，是因为有些场景**已经送审过**
    （例如「先用错的角色试一次」）⇒ 再送审一次 ⇒
    **409 `RECORD_INVALID_TRANSITION`（IN_APPROVAL 不能执行 SUBMIT_FOR_CHECK）**。
    """
    steps: list[dict[str, Any]] = []
    for role in CHAIN_ROLES:
        steps.append(
            await approval_step(
                client,
                module=module,
                record_id=record_id,
                headers=role_headers(role),
                decision=decision,
                reason="E2E 场景批注" if decision != "PASS" else None,
            )
        )
        if until_role is not None and role == until_role:
            break
    return steps


async def run_report_task(
    e2e_client,
    *,
    report_type: str,
    project_id: uuid.UUID,
    record_ids: list[uuid.UUID],
    output_format: str = "XLSX",
) -> str:
    """**直调** ARQ 任务体（`generate_report_task`）⇒ 返回 `report_file_id`。

    ⚠️ **为什么直调**：任务入队走 **Redis** ⇒ 车道**没有 worker**
    ⇒ 只入队不消费 ⇒ 行永远停在 `PENDING` ⇒ 「轮询到 SUCCESS」不可达
    ⇒ ⇒ 把 worker 的那段代码**在测试里跑一次**（同 D6 对 AI 审计的做法）。
    ⚠️ **`ctx` 里必须放 `session_factory`** —— worker 从不注入 `ctx["db"]`
    （实测过 `KeyError` ⇒ bug-166 的教训）⇒ 且 factory 要绑**隔离 schema**。
    """
    from app.workers.report_tasks import generate_report_task

    factory = e2e_client._e2e_session_factory  # type: ignore[attr-defined]
    ctx = {
        "session_factory": factory,
        "job_id": str(uuid.uuid4()),
        "job_try": 1,
    }
    return await generate_report_task(
        ctx,
        report_type=report_type,
        project_id=str(project_id),
        record_ids=[str(r) for r in record_ids],
        output_format=output_format,
        style_json={},
        ctx_vars={"project_no": "", "doc_no": "", "rev": ""},
    )


async def post_calc(
    client, url: str, body: dict[str, Any], *, headers: dict[str, str]
) -> dict[str, Any]:
    """调一个计算端点 ⇒ 断言 **201** ⇒ 返回响应体。

    ⚠️ **只断状态码 + 形状**，**不**断数值 ⇒ 算法由单测负责（薄壳）。
    ⚠️ 报错时把**响应体**带出来 ⇒ 端点的错误信封里才有真因。
    """
    resp = await client.post(url, json=body, headers=headers)
    assert resp.status_code == 201, (
        f"{url} 返回 {resp.status_code}（期望 201）：{resp.text[:400]}"
    )
    return resp.json()


__all__ = [
    "CHAIN_ROLES",
    "PIPE_SEGMENT",
    "advance_stream_to_checked",
    "approval_step",
    "approve_record_chain",
    "approve_record_steps",
    "make_record",
    "submit_for_approval",
    "run_report_task",
    "PUMP_CURVE_POINTS",
    "flash_body",
    "pipe_chain_body",
    "post_calc",
    "psv_body",
    "pump_chain_body",
    "vessel_body",
]
