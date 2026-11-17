#!/usr/bin/env python3
"""Stage 5 merge v2: final reconciled candidate set + soft buckets.

Every one of the 68 raw persona findings is accounted for: merged into a
group, demoted to a soft bucket, or discarded with a recorded reason.

The report review of this round forced two structural changes on top of the
first version:
  * an explicit adjudication (AUDIT_ADJUDICATION) for the one place where two
    findings proposed opposite fixes on the same line (#3 vs #14), and
  * per-group notes / blocked_by / tension / fix_type so a fixer can see the
    dependencies instead of discovering them.
"""
import json
import os
import re

RUN = "/tmp/compound-engineering-1000/ce-code-review/20261117-013829-7e9fbabe"
P = os.path.join(RUN, "personas")

personas = {}
for fn in sorted(os.listdir(P)):
    if fn.endswith(".json"):
        d = json.load(open(os.path.join(P, fn), encoding="utf-8"))
        personas[d["reviewer"]] = d

USED = set()


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def _frags(text):
    """Quoted code fragments, whitespace-normalised (two personas quote the
    same line with different indentation => the same fact)."""
    return frozenset(_norm(f) for f in re.findall(r"`([^`]{4,})`", text))


def _file_of(text):
    m = re.match(r"\s*([^:：\s]+):", text)
    return m.group(1) if m else ""


def _dup_evidence(existing, candidate):
    """Same file and overlapping quoted fragments => the same fact twice."""
    if candidate in existing:
        return True
    cf, cfrag = _file_of(candidate), _frags(candidate)
    cpayload = _payload(candidate)
    if not cfrag and not cpayload:
        return False
    for e in existing:
        if _file_of(e) != cf:
            continue
        efrag = _frags(e)
        epayload = _payload(e)
        if not efrag and not epayload:
            continue
        if not cfrag or not efrag:
            # one side has no backtick-quoted code: compare the raw payloads
            if cpayload and epayload and (
                    cpayload in epayload or epayload in cpayload):
                return True
            continue
        if cfrag <= efrag or efrag <= cfrag:
            return True
        inter = len(cfrag & efrag)
        if inter and inter / min(len(cfrag), len(efrag)) >= 0.5:
            return True
        # same file, same quoted code written differently (compressed, extra
        # semicolons, different quoting) => the same fact
        if _lcs(" ".join(sorted(cfrag)), " ".join(sorted(efrag))) >= 40:
            return True
    return False


def _payload(text):
    """The evidence text with the file prefix and the non-code prose removed."""
    t = text.split("\u2014", 1)[-1]
    t = re.sub(r"[^\w\.\(\)_=<>\[\]\{\}\'\":/,\- ]", "", t)
    return _norm(t)


def _lcs(a, b):
    """Length of the longest common substring of two short strings."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def src(reviewer, idx):
    """1-based index into that persona's findings list."""
    USED.add((reviewer, idx))
    return personas[reviewer]["findings"][idx - 1]


GROUPS = [
    dict(id="G01", severity="P1", cls="gated_auto", owner="downstream-resolver", conf=100,
         file="pcs-backend/app/workers/report_tasks.py", line=118,
         title="data_version 赋值在 dup 早退之后永不可达 => 审计哈希端点仍恒返空串",
         sources=[("reliability", 1), ("correctness", 1)]),
    dict(id="G02", severity="P1", cls="gated_auto", owner="downstream-resolver", conf=100,
         file="pcs-backend/tests/e2e_flows/test_e2e_report.py", line=91,
         title="E2E-009 用命令式 pytest.xfail 中止用例 => 车道全绿且下载段从不执行",
         sources=[("adversarial", 4), ("testing", 1)]),
    dict(id="G03", severity="P1", cls="manual", owner="downstream-resolver", conf=100,
         file="pcs-frontend/e2e/real_backend_flows.spec.ts", line=144,
         title="越权 UI 断言恒等：bob 被角色闸挡在项目守卫之前 => 跨项目 404 分支从未执行",
         sources=[("adversarial", 1), ("learnings", 1)]),
    dict(id="G04", severity="P1", cls="manual", owner="downstream-resolver", conf=100,
         file="pcs-frontend/e2e/real_backend_route_sweep.spec.ts", line=56,
         title="路由扫描的『渲染出来了』断言恒真，且 console error / 4xx 只打印不断言",
         sources=[("adversarial", 2), ("project-standards", 1), ("learnings", 6), ("testing", 8)]),
    dict(id="G05", severity="P1", cls="gated_auto", owner="downstream-resolver", conf=100,
         file="pcs-frontend/e2e/real_backend_flows.spec.ts", line=41,
         title="签署矩阵 UI 流断的是全局内置矩阵，不是种子那张",
         sources=[("adversarial", 3), ("correctness", 7), ("maintainability", 8)]),
    dict(id="G06", severity="P1", cls="gated_auto", owner="downstream-resolver", conf=100,
         file="pcs-backend/app/services/pipe/pipe_chain_persist.py", line=112,
         title="占位管级先查后插无 savepoint => 并发首算撞主键 => 整条计算 500",
         sources=[("reliability", 2), ("correctness", 2), ("adversarial", 8)]),
    dict(id="G07", severity="P1", cls="manual", owner="human", conf=100,
         file="pcs-backend/app/services/pipe/pipe_chain_persist.py", line=95,
         title="计算端点在运行时往全局配置主表写占位管级（假公司标准 + 两套互斥定义）",
         sources=[("maintainability", 1), ("correctness", 3), ("api-contract", 4),
                  ("security", 1), ("maintainability", 2)]),
    dict(id="G08", severity="P1", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-frontend/src/pages/routeWrappers.tsx", line=87,
         title="useFetch 静默吞错且绕过 axios 401 拦截器 => token 过期后永久停在加载中",
         sources=[("reliability", 3), ("maintainability", 7)]),
    dict(id="G09", severity="P1", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/tests/e2e_flows/conftest.py", line=93,
         title="E2E 车道与种子脚本都没有目标库白名单 => 可在开发库上建 schema 并灌种子",
         sources=[("adversarial", 5), ("testing", 5), ("security", 2), ("security", 3),
                  ("reliability", 7)]),
    dict(id="G10", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/app/api/v1/report.py", line=494,
         title="审计哈希端点返回值随行龄不同（老行与复用行恒返空串）",
         sources=[("api-contract", 2)]),
    dict(id="G11", severity="P2", cls="manual", owner="human", conf=75,
         file="pcs-backend/app/workers/report_tasks.py", line=118,
         title="data_version 被塞进文件摘要 => 审计端点两字段语义塌陷",
         sources=[("api-contract", 1)]),
    dict(id="G12", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/app/api/v1/sim_imports_query.py", line=325,
         title="preview-streams 无 response_model，契约未记录本批统一的形状；注释与事实相反",
         sources=[("api-contract", 3), ("maintainability", 11)]),
    dict(id="G13", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/scripts/seed_e2e_flows.py", line=516,
         title="种子管级违反 PipeClassResponse 契约 => 按 id 查必 500",
         sources=[("correctness", 4), ("learnings", 3)]),
    dict(id="G14", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/scripts/pytest_pg.sh", line=83,
         title="闸门③只要求『至少 1 passed』=> 29/30 场景被 skip 也是绿的",
         sources=[("adversarial", 10)]),
    dict(id="G15", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py", line=73,
         title="两库 schema 一致闸只比彼此、不与代码 head 比 => 两库都落后也绿",
         sources=[("correctness", 5)]),
    dict(id="G16", severity="P2", cls="manual", owner="downstream-resolver", conf=75,
         file="pcs-backend/tests/e2e_flows/test_e2e_schema_parity.py", line=57,
         title="schema 一致性检查塞进隔离车道且直连开发库 pcs / pcs_test",
         sources=[("maintainability", 9), ("testing", 3)]),
    dict(id="G17", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/tests/e2e_flows/test_lane_smoke.py", line=240,
         title="『不写 public』守卫只覆盖 4 张表、只取一次基线",
         sources=[("adversarial", 9), ("testing", 4), ("security", 4)]),
    dict(id="G18", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/tests/e2e_flows/conftest.py", line=289,
         title="隔离只覆盖 get_db：全局 session factory 仍指 public schema",
         sources=[("adversarial", 6)]),
    dict(id="G19", severity="P2", cls="manual", owner="downstream-resolver", conf=75,
         file="pcs-backend/tests/e2e_flows/conftest.py", line=272,
         title="E2E 车道不跑 lifespan，注释称已补启动 seed 实测 0 处调用",
         sources=[("reliability", 4)]),
    dict(id="G20", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-frontend/src/pages/DashboardPage.tsx", line=40,
         title="仪表盘 404 修复条件不严：工作区无 project_id 时照旧 404",
         sources=[("correctness", 6)]),
    dict(id="G21", severity="P2", cls="manual", owner="human", conf=100,
         file="pcs-backend/app/core/errors.py", line=45,
         title="RBAC 拒绝的审计写入在车道里被静默跳过",
         sources=[("adversarial", 7)]),
    dict(id="G22", severity="P2", cls="manual", owner="human", conf=75,
         file="pcs-backend/scripts/pytest_pg.sh", line=56,
         title="flock 互斥只覆盖两条 pytest 车道，compose 迁移/种子裸奔",
         sources=[("reliability", 5)]),
    dict(id="G23", severity="P2", cls="manual", owner="human", conf=75,
         file="spec/P10 AI预留与测试部署开发规格说明书.md", line=666,
         title="本批偏离登记写进非权威 SPEC 文件，D20 与本批自述互相矛盾",
         sources=[("api-contract", 6), ("project-standards", 2)]),
    dict(id="G24", severity="P2", cls="manual", owner="human", conf=75,
         file=".wolf/STATUS.md", line=88,
         title="本批 4 条可复用解法没有回写 docs/solutions/，且 STATUS 自称已回写",
         sources=[("project-standards", 3)]),
    dict(id="G25", severity="P2", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-frontend/package.json", line=20,
         title="真后端 UI 车道依赖 4 个仓库外环境变量 => 无法从仓库复现",
         sources=[("testing", 2)]),
    dict(id="G26", severity="P3", cls="gated_auto", owner="downstream-resolver", conf=75,
         file="pcs-backend/tests/scripts/test_pytest_e2e_gate.py", line=95,
         title="flock 守卫测试用原文子串匹配（含注释）且不校验 -n；唯一入口守卫只数一个字面量",
         sources=[("learnings", 5), ("testing", 9), ("testing", 10)]),
    dict(id="G27", severity="P3", cls="advisory", owner="human", conf=75,
         file="pcs-backend/app/schemas/stream.py", line=318,
         title="响应可空但请求仍必填：case_type 读写不对称",
         sources=[("api-contract", 7)]),
    dict(id="G28", severity="P2", cls="advisory", owner="release", conf=75,
         file="pcs-backend/docs/openapi-baseline.json", line=1,
         title="契约基线只是『与当前一致』的同步锁，没有已发布契约锚点",
         sources=[("api-contract", 5)], pre_existing=True),
]

# --- soft buckets -------------------------------------------------------
RESIDUAL = [
    ("maintainability", 3), ("maintainability", 4), ("maintainability", 5),
    ("maintainability", 6), ("maintainability", 10), ("maintainability", 12),
    ("reliability", 6), ("security", 5), ("learnings", 4),
]
TESTING_GAPS = [
    ("testing", 6), ("testing", 7), ("learnings", 2),
]
DISCARDED = [
    ("project-standards", 4,
     "premise contradicted on disk: the batch-end QA report exists at "
     ".gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md; only the "
     ".wolf/STATUS.md wording still says it has not run, which is folded into G24"),
]

# ---------------------------------------------------------------------------
# Merge-leaf adjudications and per-group overrides.
# Every one of these was raised by the report review of this round; each one
# either removes a contradiction between two findings or records a dependency
# the fixer needs.
# ---------------------------------------------------------------------------
AUDIT_ADJUDICATION = {
    "id": "A1",
    "topic": "GET /report/{id}/hash 的 record_hash_digest 到底该读哪一列（#3 / #4 / #12 / #14 共用）",
    "decision_needed": "审计端点要的是「交付的报表文件的 sha256」还是「登记时冻结的数据版本」。本批把文件摘要塞进了 data_version，于是 #3 的修法（把 digest 写进 data_version）与 #14 的修法（别把文件摘要塞进 data_version）方向相反 —— 两条不能同时执行。",
    "ground_truth": "pcs-backend/app/api/v1/report.py:480-483 自己就写着 `digest == row.content_hash`（那里算的就是交付文件的 sha256）⇒ content_hash 就是这一行交付文件的哈希，而且它在每一行上都有值（含本批之前的老行）；data_version 是通用的「数据版本」列，本批把它挪用成了文件摘要。",
    "recommended_default": "_expected_digest（report.py:486-494）改读 `row.content_hash or \"\"`；删掉 report_tasks.py:118 那行 `row.data_version = digest`（它本来就在 dup 早退之后不可达）；data_version 留给它自己的语义。",
    "why_this_default": "一处改动同时闭合三条：#3（端点不再恒返空串）· #12（老行与复用行也有值 ⇒ 不需要 backfill）· #14（两字段不再塌成同一个值）。代价：report.py:487-492 的 docstring（明说「任务体必须写 data_version」「端点语义不变」）必须一并改。",
    "alternative": "`row.data_version or row.content_hash` + 把 digest 写到存活的那一行（#3 的原修法）。它保住了本批「端点语义不变」的原始意图，但它是临时兼容：老行仍返空串（除非另补一条回填），而且 data_version 继续承担文件摘要的语义（#14 的塌陷不解）⇒ 若选它，必须在契约里明确标注「临时方案，不是最终语义」。",
    "affects": ["#3", "#4", "#12", "#14"],
    "must_be_decided_by": "human —— 这是产品语义决定（审计要证明的是「报表文件」还是「记录集」）；merge leaf 不替人拍板，只保证四条发现互相不矛盾、且都指向同一个裁决。",
    "not_allowed": "在裁决之前同时执行 #3 与 #14 两套相反的改法。",
}

_OVERRIDES = {
    # --- the audit-digest adjudication cluster (#3 / #4 / #12 / #14) --------
    "G01": {
        "fix_type": "mechanical",
        "notes": "本条与 #12 同源（审计端点读哪一列）⇒ 先做裁决 A1，再按裁决改；本条自己的 suggested_fix 已写成与 #12 一致的版本，不要与旧版 #14 的改法混用。",
        "suggested_fix": "按裁决 A1 落地（推荐默认）：`_expected_digest`（report.py:486-494）改读 `row.content_hash or \"\"`（report.py:480-483 已证明 content_hash 就是交付文件的 sha256），并删掉 report_tasks.py:118 那行不可达的 `row.data_version = digest`；同时把 report.py:487-492 的 docstring 改成与实现一致。若改选 A1 的替代方案，则改成把 digest 写到**存活的那一行**（report_service._upsert_report_file 建行时一并写 + _finalize 的 dup 分支补写），并明确标注那是临时兼容（老行需另补回填）。",
    },
    "G10": {
        "fix_type": "mechanical",
        "notes": "与 #3 同源 ⇒ 见裁决 A1；本条的「随行龄不同」在推荐默认下自动消失（content_hash 每行都有）。",
        "suggested_fix": "按裁决 A1 落地（推荐默认）：`_expected_digest` 改读 `row.content_hash or \"\"` ⇒ 老行（data_version 为 NULL）与复用行（data_version 从未写入）都直接有值，不需要回填、不需要按行龄分支。若改选 A1 的替代方案，则老行仍需一条回填或一条「读不到就明说缺失」的分支。",
    },
    "G11": {
        "fix_type": "design-input",
        "notes": "本条是 A1 裁决要回答的问题本身：data_version 要不要承担文件摘要的语义。",
        "suggested_fix": "按裁决 A1 落地（推荐默认）：`row.data_version` 与 `record_hash_digest` 的语义分开 —— 审计端点改读 `row.content_hash`（report.py:480-483 已证明它等于交付文件的 sha256），`data_version` 留给「数据版本号」自己的语义，并把 report.py:487-492 的 docstring 改成与实现一致。若改选 A1 的替代方案，则必须在契约里写明「data_version 本表承载文件摘要」并登记这是临时语义。",
    },
    "G02": {
        "fix_type": "mechanical",
        "notes": "本条的硬断言断什么，取决于裁决 A1（见本条的 suggested_fix）。",
        "suggested_fix": "把 E2E-009 拆成两条用例：(a) 对 record_hash_digest 做硬断言 —— 断言内容随裁决 A1 而定：若审计端点改读 content_hash，则断言 record_hash_digest == 该行的 content_hash（且非空）；若保留 data_version 承载，则断言它是非空的 64 位 hex；(b) 下载段（200 + 字节数 > 0）单独成用例，不再被上面的 xfail 一起中止。不要用命令式 `pytest.xfail()` 放在用例顶层（它会中止后续所有语句）。",
    },
    # --- the placeholder pipe class cluster --------------------------------
    "G06": {
        "fix_type": "mechanical",
        "blocked_by": "#2 的裁决：若 #2 裁决为「改成数据迁移种一行」，本条（并发 savepoint）随之作废；只有当运行时兜底保留时才需要它。",
        "notes": "本条的修法与 #2 互斥依赖，先裁 #2 再动代码。",
    },
    "G07": {
        "fix_type": "design-input",
        "blocked_by": "#17 依赖本条的裁决方向（种子行是否也允许出现在公司管级列表）；#1 依赖本条（见 #1 的 blocked_by）。",
        "notes": "本条是这一簇的根决策：占位行归谁（迁移种一行 / 允许运行时兜底）。#6 与 #17 的修法都随它变。",
    },
    # --- the seed row / contract cluster -----------------------------------
    "G13": {
        "fix_type": "mechanical",
        "notes": "本条的修法随 #2 的裁决变（种子行要不要出现在公司管级列表）⇒ 见本条的 tension。",
        "tension": "与 #2 的张力：种子行若按 PipeClassResponse.source 的 Literal 改成 source=\"COMPANY_STD\"（契约里只有 COMPANY_STD / PROJECT），它同样会出现在公司管级列表里。测试数据出现在产品列表是否可接受需要一并裁决（种子只跑在隔离 schema / pcs_pgtest 上），可选：① 接受（隔离环境里可接受）；② 扩契约加一个 Literal（如 E2E_SEED）—— 契约面更大，且 list_company 的过滤要跟着改；③ 公司列表过滤掉种子行。不要只改种子形状而不管列表可见性。",
        "suggested_fix": "种子管级行按 PipeClassResponse 契约改：source 取字面量内的值（COMPANY_STD 或 PROJECT）、dn_series_json 带 {min,max} 且 0<min<=max、sch_series_json 用 dict[str, str]（契约里是 DN→Sch 壁厚映射），并在快车道加一条「按 id 取该行不 500」的断言。另见本条的 tension：改成 COMPANY_STD 会让它出现在公司管级列表（与 #2 同一个问题），需要连同列表可见性一起裁。",
    },
    # --- guard / isolation cluster -----------------------------------------
    "G09": {
        "fix_type": "mechanical",
        "notes": "fail-closed：库名不在白名单 ⇒ 非零退出，不要 warning。",
    },
    "G17": {
        "fix_type": "mechanical",
        "notes": "守卫要快照本批写的所有表，且基线取在种子**之前**。",
    },
    "G18": {
        "fix_type": "mechanical",
        "notes": "隔离 session factory 要注入全局 session factory 的使用点（errors.py:51 / ws.py:77）。",
    },
    "G19": {
        "fix_type": "mechanical",
        "notes": "补 lifespan 的两处启动 seed，或删掉那句撒谎的注释；两者选一，别留第三种状态。",
    },
    "G14": {
        "fix_type": "mechanical",
        "notes": "闸门③改为「无 skip 且 passed 数 ≥ 场景数」；闸门②的收集数也可以一起断言。",
    },
    "G15": {
        "fix_type": "mechanical",
        "notes": "与 #20 同文件同主题（test_e2e_schema_parity.py），建议一次改完；分在两个 triage 组只因为根因不同（一个是「比对基准不对」，一个是「不该在这个车道」）。",
    },
    "G16": {
        "fix_type": "mechanical",
        "notes": "与 #21 同文件同主题（test_e2e_schema_parity.py），建议一次改完：把两库一致检查移出 E2E 车道（它是发布前检查），并加上「与 alembic head 比」这一条。",
    },
    "G22": {
        "fix_type": "design-input",
        "notes": "锁的覆盖面要人定（compose 的 migrate/seed 能不能也走同一把锁）。",
        "suggested_fix": "把互斥从「脚本内的 flock」提升到「库级别的互斥」：① 让 compose 的 migrate/seed 服务也走同一个锁（或改成由 scripts/pytest_pg.sh 负责迁移）；② 锁文件放在每用户私有且不会被系统清理的位置（如 `${XDG_RUNTIME_DIR:-/tmp}/pcs-pgtest-lane.lock`，并先 `install -m 600 /dev/null` 建文件、拒绝符号链接），不要改用仓内 `.tmp/` —— 该目录既不在 .gitignore 里（当前 .gitignore 只有 __pycache__/.pytest_cache/.ruff_cache/.mypy_cache）也会出现在 git status 里；③ 在 `exec 9>` 失败时给出明确 FAIL 而不是 shell 重定向错误；④ 守卫测试补一条「默认路径下的两条 lane 互斥」用例（子进程实测），而不是只测覆盖后的临时路径。",
    },
    "G26": {
        "fix_type": "mechanical",
        "notes": "守卫测试本身要改断言方式（剥注释 + 断命令形状），不是加新用例。",
    },
    "G24": {
        "fix_type": "design-input",
        "notes": "本批 4 条可复用解法要回写 docs/solutions/（CLAUDE.md 的要求），且 STATUS.md 里「已进 docs/solutions」与「本轮还没跑」这两句都要与事实一致（QA 报告其实已存在于 .gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md，日期也不是 STATUS 写的 11-16）。",
    },
    "G23": {
        "fix_type": "design-input",
        "notes": "先裁「哪份 SPEC 是准」（仓里 V1.0 与 V1.3.1 两份都在，V1.0 的 D20 说 V1.3.1 不存在，本批说以 V1.3.1 为准），再把偏离登记写进权威那份。",
    },
    "G27": {
        "fix_type": "advisory",
        "notes": "advisory：读改写不对称目前没有现有消费者踩到（前端消费点已空值安全）⇒ 报告级登记即可。",
    },
    # --- frontend cluster ---------------------------------------------------
    "G03": {
        "fix_type": "design-input",
        "notes": "autofix_class=manual：换账号还是换断言形状，要先定「越权用例该断 403 还是断 404」这一步的意图（按计划 §Review Focus 3，应断 404 ⇒ 需要一个能过角色闸但无授权行的账号）。",
    },
    "G04": {
        "fix_type": "design-input",
        "notes": "autofix_class=manual：45 条路由里哪些页面允许有 4xx（TODO-159/160 的既有缺口）要人裁定白名单。",
        "suggested_fix": "把『#root 存在』换成页面专有特征，两条路径并用：(a) 有种子专有值的页面（物流一览 / 交付物 / 签署矩阵 / 设备一览 等 5 条 UI 流覆盖的页面）断「种子专有字符串出现在页面上」（项目 id、流名 E2E-FLOW-S-001、交付物标题 E2E 流程级种子计算书、矩阵名 E2E_FLOWS_RECORD_3_LEVEL）；(b) 其余页面断「页面标题或空态文案出现 且 #root 下有非空子节点」—— 这抓得到白屏，抓不到「渲染了但拿不到数据」，那一类留给 console error / 4xx 断言来兜。另加两条全局断言：整轮扫描下来 console error 为空、且 4xx/5xx 列表只包含显式白名单里的页面（TODO-159/160 的 6 个页面按页面清单写死，其余一律红）。白名单的页面清单要人裁定（因此本条是 manual）。",
    },
    "G08": {
        "fix_type": "mechanical",
        "notes": "统一走 src/api/client.ts 的 axios（或至少区分 401 与其它错误并暴露错误态 + 超时）。",
    },
    "G20": {
        "fix_type": "mechanical",
        "notes": "守卫条件改成「拿到了非占位 project_id」而不是「选了工作区」。",
    },
    "G25": {
        "fix_type": "mechanical",
        "notes": "把跑法写进仓库（package.json 的 script 或 pcs-frontend/README），带默认值。",
    },
    "G05": {
        "fix_type": "mechanical",
        "notes": "validation=unresolved ⇒ 这是**验证闸门**不是已确认缺陷：confidence 100 只覆盖「名字对不上」这个事实，不覆盖「内置矩阵在目标库里存不存在」。查迁移 p9_013 与目标库再决定是改断言名字还是改种子名；证据到手前不要当已确认缺陷去改。",
    },
    # --- report-only decision items ----------------------------------------
    "G12": {
        "fix_type": "mechanical",
        "notes": "补 response_model（让本批统一的 {\"streams\":[...]} 形状进 OpenAPI）+ 修那句与事实相反的注释（import_service.py:496 与 :612 两处写的都是 list）。",
    },
    "G21": {
        "fix_type": "mechanical",
        "notes": "本条依赖 #8：PCS_E2E_LANE 本身不可靠（#8 = 车道与种子没有目标库白名单），所以修法不能只把早退条件从 PYTEST_CURRENT_TEST 换成 PCS_E2E_LANE —— 那等于把审计留痕的开关绑在一个已知不可靠的变量上。",
        "suggested_fix": "等 #8 的目标库白名单落地之后，把 RBAC 审计的早退条件改成「当前连接的是隔离/测试库才写」（用 current_database() 或车道注入的 session factory 判定），而不是用 PCS_E2E_LANE 单点判定；在此之前不要把 PCS_E2E_LANE 当成唯一判据。车道里再加一条断言：一次 403 之后 audit_logs 里确实多了一行。",
    },
    "G14B": {},
}

merged = []
for g in GROUPS:
    ev, reviewers, why, fix = [], [], None, None
    for rev, idx in g["sources"]:
        f = src(rev, idx)
        reviewers.append(rev)
        for e in f.get("evidence", []):
            if not _dup_evidence(ev, e):
                ev.append(e)
        if why is None:
            why = f.get("why_it_matters")
            fix = f.get("suggested_fix")
    merged.append({
        "title": g["title"],
        "severity": g["severity"],
        "file": g["file"],
        "line": g["line"],
        "why_it_matters": why,
        "autofix_class": g["cls"],
        "owner": g["owner"],
        "requires_verification": True,
        "confidence": g["conf"],
        "evidence": ev,
        "pre_existing": g.get("pre_existing", False),
        "suggested_fix": fix,
        "first_evidence": ev[0] if ev else None,
        "_group": g["id"],
        "_reviewers": reviewers,
    })
    extra = _OVERRIDES.get(g["id"], {})
    for k, v in extra.items():
        merged[-1][k] = v

# G01 and G06 were the same defect written twice in the first draft of this
# script; keep exactly one of them.
_seen = {}
for m in merged:
    key = (m["title"], m["file"])
    if key in _seen:
        raise SystemExit("duplicate merged candidate: %s" % (key,))
    _seen[key] = m


def soft_text(pairs):
    out = []
    for rev, idx in pairs:
        f = src(rev, idx)
        out.append("[%s] %s (%s:%s) - %s" % (rev, f["title"], f["file"], f["line"],
                                             f.get("why_it_matters", "")[:400]))
    return out


residual_texts = soft_text(RESIDUAL)
testing_texts = soft_text(TESTING_GAPS)
for rev, idx, _reason in DISCARDED:
    src(rev, idx)

out = {
    "reviewer": "merge-leaf",
    "findings": merged,
    "residual_risks": residual_texts,
    "testing_gaps": testing_texts,
    "adjudications": [AUDIT_ADJUDICATION],
}
with open(os.path.join(RUN, "merged-candidates.json"), "w", encoding="utf-8") as fh:
    json.dump([out], fh, ensure_ascii=False, indent=1)

missing = []
for rev, d in personas.items():
    for i, f in enumerate(d["findings"], 1):
        if (rev, i) not in USED:
            missing.append((rev, i, f["title"]))
print("groups:", len(merged), " residual:", len(residual_texts), " testing_gaps:", len(testing_texts))
print("unaccounted raw findings:", missing if missing else "none")
