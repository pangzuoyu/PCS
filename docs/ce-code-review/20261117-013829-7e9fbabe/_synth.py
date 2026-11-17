#!/usr/bin/env python3
"""Stage 5 synthesis: assemble synthesized-findings.json from the merged set,
the triage groups and the validator verdicts."""
import json
import os

RUN = "/tmp/compound-engineering-1000/ce-code-review/20261117-013829-7e9fbabe"

mech = json.load(open(os.path.join(RUN, "mechanical-merged.json"), encoding="utf-8"))
groups = json.load(open(os.path.join(RUN, "triage-groups.json"), encoding="utf-8"))
vi = json.load(open(os.path.join(RUN, "validator-input.json"), encoding="utf-8"))
cand = json.load(open(os.path.join(RUN, "merged-candidates.json"), encoding="utf-8"))
ADJUDICATIONS = (cand[0].get("adjudications") if isinstance(cand, list) else None) or []

vpath = os.path.join(RUN, "validator-verdicts.json")
verdicts = {}
if os.path.exists(vpath):
    raw = json.load(open(vpath, encoding="utf-8"))
    for v in raw.get("verdicts", []):
        if isinstance(v, dict) and isinstance(v.get("#"), int):
            verdicts[v["#"]] = v

selected = {f["#"] for f in vi["findings"]}
PROTECTED = {"memory-safety", "concurrency", "data-loss", "authorization-authentication",
             "injection", "public-contract", "secrets-exposure", "cryptography"}


# Evidence the merge leaf itself verified by reading the source at the reviewed
# head (independent of any persona claim).
MERGE_LEAF_VERIFIED = {
    3: [
        "MERGE-LEAF VERIFIED pcs-backend/app/workers/report_tasks.py:101-111 - the dup query runs first "
        "and `if dup is not None:` deletes the placeholder row and returns at line 111, so line 118 "
        "(`row.data_version = digest`) is unreachable on that path",
        "MERGE-LEAF VERIFIED pcs-backend/app/services/report/report_service.py:420 generate -> 428 "
        "store_rendered -> 513 _upsert_report_file -> 612-618 builds a ReportFile with "
        "content_hash=kw['content_hash'] and NO data_version; report_tasks.py:167-173 calls generate "
        "before _finalize, so the dup query always matches that row and the surviving row never gets "
        "data_version => GET /report/{id}/hash keeps returning an empty string",
    ],
    4: [
        "MERGE-LEAF VERIFIED pcs-backend/tests/e2e_flows/test_e2e_report.py:90-94 - `pytest.xfail(...)` "
        "is called imperatively inside the test body, so it raises and aborts the test; the download "
        "assertions at lines 96-100 never run when the hash is empty",
    ],
    5: [
        "MERGE-LEAF VERIFIED pcs-frontend/e2e/real_backend_flows.spec.ts:133-134 - the test's own "
        "comment says the streams list endpoint runs the ROLE gate first and that a CHECKER gets 403, "
        "then line 144-148 compares unauthorized.status() with nonexistent.status() => both are the "
        "role gate's 403, so the project guard branch is never exercised",
    ],
    11: [
        "MERGE-LEAF VERIFIED .wolf/STATUS.md:86 - the section header claims the lessons are already in "
        "'cerebrum / docs/solutions' and lists bug-2166 / bug-2169 / bug-2170, but `git diff "
        "d73d1ac..f3b35e5 -- docs/solutions` is empty and no file under docs/solutions/ mentions any of "
        "those three bug numbers",
        "MERGE-LEAF VERIFIED .wolf/STATUS.md:50-51 - points at "
        ".gstack/qa-reports/qa-report-pcs-frontend-2026-11-16-p10b.md and says '本轮还没跑', while the "
        "report on disk is qa-report-pcs-frontend-2026-11-17-p10b.md (different date) and it does exist",
    ],
    16: [
        "MERGE-LEAF VERIFIED pcs-backend/scripts/pytest_e2e.sh:32-35 - the E2E lane exports "
        "PG_PYTEST_MARK=e2e and PCS_E2E_LANE=1 and then `exec bash scripts/pytest_pg.sh`, so the E2E "
        "lane inherits exactly the same gate ③ at pytest_pg.sh:83 that only greps for '[1-9][0-9]* passed'",
    ],
    17: [
        "MERGE-LEAF VERIFIED pcs-backend/app/schemas/pipe_class.py:77 - "
        "`source: Literal[\"COMPANY_STD\", \"PROJECT\"]` while the seeded row uses source=\"E2E_SEED\"",
        "MERGE-LEAF VERIFIED pcs-backend/app/schemas/pipe_class.py:85-95 - the _check_dn model_validator "
        "raises unless dn_series_json carries {min,max} with 0<min<=max, and line 62 types "
        "sch_series_json as dict[str, str]; the seeded row has dn_series_json={\"DN150\": 1.0} and "
        "sch_series_json={\"DN150\": 40.0} => reading that row through PipeClassResponse raises => 500",
    ],
    23: [
        "MERGE-LEAF VERIFIED pcs-frontend/src/constants/env.ts:12-13 - "
        "`import.meta.env.VITE_PROJECT_ID ?? '00000000-0000-0000-0000-000000000001'` => without an "
        "injected VITE_PROJECT_ID the pages query the placeholder project",
        "MERGE-LEAF VERIFIED pcs-frontend/playwright.config.ts real-backend webServer - sets only "
        "VITE_ENABLE_MOCK=false (no VITE_PROJECT_ID); package.json:20 sets VITE_ENABLE_MOCK=false and "
        "VITE_API_PROXY_TARGET (default http://localhost:8000). Neither spec file reads any env var: "
        "the flow spec hardcodes FLOW_PROJECT_ID = '2488b011-14fc-584b-966e-1e2dfaeb9eb7', so the "
        "page under test and the seeded project can diverge",
    ],
    9: [
        "MERGE-LEAF VERIFIED pcs-frontend/src/pages/routeWrappers.tsx:85-92 - the token comes from the "
        "session, the call is a bare `fetch` (no axios interceptor, so no 401 handling and no timeout), "
        "a non-2xx response becomes `null` and `.catch(() => {})` swallows network errors => the "
        "component stays in its loading state forever with no error surfaced",
    ],
}


def hydrate(f, pre_existing=False):
    out = {
        "#": f.get("#"),
        "title": f["title"],
        "severity": f["severity"],
        "confidence": f["confidence"],
        "file": f["file"],
        "line": f["line"],
        "why_it_matters": f["why_it_matters"],
        "evidence": f.get("evidence", []),
        "first_evidence": f.get("first_evidence"),
        "suggested_fix": f.get("suggested_fix"),
        "autofix_class": f["autofix_class"],
        "owner": f["owner"],
        "requires_verification": f.get("requires_verification", True),
        "pre_existing": pre_existing or f.get("pre_existing", False),
        "reviewers": f.get("_reviewers", []),
        "independent_reviewers": [],
        "group": f.get("_group"),
    }
    for k in ("fix_type", "notes", "blocked_by", "tension"):
        if f.get(k):
            out[k] = f[k]
    if out.get("fix_type") is None:
        out["fix_type"] = {"manual": "design-input", "advisory": "advisory"}.get(
            f["autofix_class"], "mechanical")
    extra = MERGE_LEAF_VERIFIED.get(f.get("#"))
    if extra:
        out["evidence"] = list(out["evidence"]) + extra
    v = verdicts.get(f.get("#"))
    if v is not None:
        out["validation_status"] = v.get("status")
        out["validation_reason"] = v.get("reason")
        ps = v.get("protected_subject")
        out["protected_subject"] = ps if ps in PROTECTED else None
        if v.get("status") == "unresolved":
            # Stage 5b: an unresolved finding is report-only, never applied.
            out["owner"] = "human"
            out["autofix_class"] = "advisory"
            out["requires_verification"] = True
        elif v.get("status") == "rejected":
            out["rejected_reason"] = v.get("reason")
    else:
        out["protected_subject"] = None
    if v is not None and 'incidence not measured' in (v.get('reason') or ''):
        out["incidence_measured"] = False
    return out


primary = [hydrate(f) for f in mech["findings"]]
pre_existing = []
for i, f in enumerate(mech["pre_existing_findings"], 1):
    h = hydrate(f, True)
    h["#"] = "PE-%d" % i
    h["excluded_from_verdict"] = (
        "pre-existing: 这个形状在本批之前就存在（基线只是一道「与当前一致」的同步锁，不是已发布契约锚点）"
        "⇒ 不计入本批的 verdict；本批新增的破坏性契约变更（case_type 必填→可空）仍需要一次版本/弃用说明")
    pre_existing.append(h)

# Stage 5b step 5: rejected findings leave the primary set.
confirmed = [f for f in primary if f.get("validation_status") == "confirmed"]
rejected = [f for f in primary if f.get("validation_status") == "rejected"]
unresolved = [f for f in primary if f.get("validation_status") == "unresolved"]
unvalidated = [f for f in primary if "validation_status" not in f]

kept = []
for f in primary:
    if f.get("validation_status") == "rejected":
        continue
    kept.append(f)

actionable = [f for f in kept if f["owner"] == "downstream-resolver"]
report_only = [f for f in kept if f["owner"] in ("human", "release")]

# triage groups: prune any # that was rejected
kept_ids = {f["#"] for f in kept}
tg = []
for g in groups["triage_groups"]:
    ids = [i for i in g["findings"] if int(i.lstrip("#")) in kept_ids]
    if not ids:
        continue
    g2 = dict(g)
    g2["findings"] = ids
    tg.append(g2)
ungrouped = [i for i in groups["ungrouped"] if int(i.lstrip("#")) in kept_ids]

coverage = {
    "depth": "full (floor = size_band=large, executable non-test lines 974)",
    "scope": "base d73d1ac -> head f3b35e5 on branch main; 55 files; 8659 changed lines "
             "(974 executable non-test); unclassified lines: json 1978, md 1869, txt 282, yml 15",
    "reviewers": "9 personas: correctness, project-standards, testing, maintainability, learnings, "
                 "security, api-contract, reliability, adversarial",
    "standards": "the repository-root CLAUDE.md (/home/pangzy/code_project/PCS/CLAUDE.md) is the "
                 "standards criteria and governs every changed file; no fallback standards file had to be named",
    "peer_outcome": "Cross-model peer: NOT STARTED - no peer provider CLI allowed by the skill is "
                    "installed on this machine (codex / grok / composer / cursor-agent are all absent "
                    "from PATH; CROSS_MODEL_PEERS is unset) => the adversarial lens is carried only by "
                    "the in-process `adversarial` persona, so this round has a single serving model "
                    "behind every claim and no cross-model corroboration.",
    "merge_mechanics": "68 raw persona findings -> 28 merged candidates (27 primary + 1 pre-existing). "
                       "5 raw findings (the whole security persona) arrived malformed because the "
                       "persona omitted the pre_existing field; they were reconstructed from the cited "
                       "lines and merged rather than dropped. 61 findings had first_evidence backfilled "
                       "from evidence[0] in the first helper pass; the reconciled pass needed 0 "
                       "backfills. 1 candidate was suppressed at confidence anchor 50 in the first pass "
                       "and 0 in the final pass.",
    "mode_aware_demotions": "12 candidates were demoted out of the primary set into the soft buckets "
                            "(9 residual risks + 3 testing gaps) under the mode-aware demotion rule: "
                            "single-reviewer P2/P3 maintainability/reliability items with no established "
                            "significant consequence went to residual_risks, and single-reviewer "
                            "testing/learnings absence-of-coverage items went to testing_gaps. 1 "
                            "candidate was discarded outright because its premise is contradicted on "
                            "disk (the batch-end QA report exists at "
                            ".gstack/qa-reports/qa-report-pcs-frontend-2026-11-17-p10b.md; only the "
                            ".wolf/STATUS.md wording still says it has not run, and that wording is "
                            "carried inside #11).",
    "unselected_personas": "performance (the product-code change is tiny and the performance surface "
                            "sits in test seed data) - data-migration (the diff contains no migration or "
                            "schema artifact) - agent-native (no agent-facing capability surface) - "
                            "julik-frontend-races (React/TypeScript, not Stimulus/Turbo) - swift-ios (no "
                            "Swift file) - previous-comments (standalone review, no PR) - "
                            "deployment-verification (no high-risk migration artifact)",
    "known_debt_cross_check": "bug-2165's root cause was NOT closed by this batch: the review located "
                               "the root cause (the dup early-return makes the data_version assignment "
                               "unreachable, #3) => TODO-158 can be closed against #3 rather than "
                               "staying open. The runtime write into the configuration table was already "
                               "registered as TODO-161 by the batch itself; the review raises it to a P1 "
                               "decision (#2) because it also fabricates a company-level standard every "
                               "user sees. TODO-159/160 (three frontend pages calling non-existent "
                               "endpoints, three pages 422 on first paint) are exactly what the route "
                               "sweep was supposed to catch but only printed (#7). 'E2E into CI' stays "
                               "deferred to P10-F and is not a defect of this batch.",
    "validator": None,
    "untracked_excluded": "none",
    "stale_artifacts_in_run_dir": "a report.md and a metadata.json from an EARLIER manual report-leaf run "
                                  "are still present in the run directory (they say the validator never ran "
                                  "and that the merge leaf produced no output). Both are SUPERSEDED by this "
                                  "merge and by validator-verdicts.json / validator-outcome.json; the report "
                                  "leaf must re-render both from the current artifacts.",
}

if verdicts:
    counts = {"confirmed": len(confirmed), "rejected": len(rejected),
              "unresolved": len(unresolved), "malformed": 0, "failed": 0,
              "shortcut_skipped": 0, "unvalidated": len(unvalidated)}
    coverage["validator"] = {
        "batch": "one batch of %d findings (every P0/P1 and every remaining actionable finding), "
                 "ordered by severity then stable #; the batch was never split into a second batch and "
                 "no finding was skipped, so the shortcut count is 0. Finding #2 (a P1 whose owner is "
                 "`human`) was left out by the first selection pass on an owner-based rule; the rule is "
                 "that every P0/P1 is selected, so it was validated in the SAME validator agent and the "
                 "batch artifact (validator-input.json) now carries all %d."
                 % (len(selected), len(selected)),
        "counts": counts,
        "outcome": "verdicts",
        "note": "no cross-model shortcut applied: the shortcut requires an ordinary reviewer plus an "
                "adversarial-<provider> reviewer whose artifact records independence_verified:true, and "
                "the peer never ran",
        "unresolved_gates": "finding #6 (P1) is the only unresolved entry: the name mismatch is verified "
                            "but whether the built-in DEFAULT_RECORD_3_LEVEL row exists in the target "
                            "database was not established inside the budget (migration p9_013 not read). "
                            "It stays in the report as a verification gate with owner=human and "
                            "autofix_class=advisory; it is NOT in the actionable queue and no fixer may "
                            "apply it as if it were confirmed.",
        "protected_subject_review": "the merge leaf re-checked every verdict's protected_subject against "
                                    "the eight policy keys independently of the validator: all 21 values "
                                    "are valid keys or null, and 7 findings carry a protected subject "
                                    "(#1 concurrency, #3/#12/#13/#17 public-contract, "
                                    "#5/#9 authorization-authentication, #8 data-loss). No finding was "
                                    "rejected, so no protected-subject reclassification was needed. "
                                    "Confirmation grants no new apply authority.",
        "incidence_not_measured": "#1 and #8 were confirmed with the note that incidence was not "
                                  "measured: the code permits the failure but no test or query showed it "
                                  "occurring.",
    }
else:
    coverage["validator"] = {"batch": "not collected", "outcome": "infrastructure-failure",
                              "note": "the validator batch produced no usable verdict file"}

out = {
    "run_id": "20261117-013829-7e9fbabe",
    "run_dir": RUN,
    "generated_by": "merge leaf (Stage 5 + Stage 5b steps 1-3)",
    "scope": {"base": "d73d1ac", "head": "f3b35e5", "branch": "main",
              "mode": "local-aligned", "tree_is_reviewed_head": True,
              "diff": os.path.join(RUN, "full.diff"), "files": os.path.join(RUN, "files.txt")},
    "plan": {"path": "docs/superpowers/plans/2026-11-13-p10-batch-b-fullflow-e2e.md",
             "source": "explicit"},
    "primary_findings": kept,
    "pre_existing_findings": pre_existing,
    "rejected_findings": rejected,
    "residual_risks": mech["residual_risks"],
    "testing_gaps": mech["testing_gaps"],
    "actionable_findings": actionable,
    "report_only_findings": report_only,
    "triage_groups": tg,
    "ungrouped_findings": ungrouped,
    "grouping": groups["grouping"],
    "adjudications": ADJUDICATIONS,
    "verdict_inputs": {
        "open_p1": [f["#"] for f in kept if f["severity"] == "P1" and f["owner"] == "downstream-resolver"],
        "open_p1_report_only": [f["#"] for f in kept if f["severity"] == "P1" and f["owner"] != "downstream-resolver"],
        "open_p2": [f["#"] for f in kept if f["severity"] == "P2" and f["owner"] == "downstream-resolver"],
        "unresolved_gates": [f["#"] for f in kept if f.get("validation_status") == "unresolved"],
        "rule": ("the verdict must be stated explicitly (merge / merge with fixes / do not merge) and must read "
                 "severity across the WHOLE primary set, not the actionable queue alone: an open P0 forbids "
                 "'ready to merge' and an open P1 caps it at 'ready with fixes' - and an unresolved P1 gate "
                 "still counts as an open P1 (withholding a gate from the actionable queue withholds apply "
                 "authority, it never clears the blocker). With %d open P1s in the actionable queue "
                 "(%s) and %d P1 report-only (%s) plus %d P2 actionable (%s), the batch cannot be called "
                 "'ready to merge' without an explicit human decision on the design items (#2, #6, #14) and "
                 "the audit-digest adjudication A1." % (
                     len([f for f in kept if f["severity"] == "P1" and f["owner"] == "downstream-resolver"]),
                     ", ".join("#%d" % f["#"] for f in kept if f["severity"] == "P1" and f["owner"] == "downstream-resolver"),
                     len([f for f in kept if f["severity"] == "P1" and f["owner"] != "downstream-resolver"]),
                     ", ".join("#%d" % f["#"] for f in kept if f["severity"] == "P1" and f["owner"] != "downstream-resolver"),
                     len([f for f in kept if f["severity"] == "P2" and f["owner"] == "downstream-resolver"]),
                     ", ".join("#%d" % f["#"] for f in kept if f["severity"] == "P2" and f["owner"] == "downstream-resolver"))),
        "format": ("the verdict sentence must also name the minimum set to fix first (the P1s in the "
                   "actionable queue) and, if a conditional merge is considered, say which TODOs may not be "
                   "closed on the strength of it"),
    },
    "rendering_contract": {
        "evidence": ("every finding carries first_evidence (a complete quote) plus the full evidence array. "
                     "Render a SHORT label in the table cell and the complete evidence in the detail block. "
                     "Never truncate an evidence string mid-sentence - a truncated quote reads like a "
                     "production bug in the report."),
        "pipes": ("literal `|` inside any evidence or code fragment must be escaped as a backslash-pipe in a markdown "
                  "table cell (e.g. `select(PipeClass).where(...)` has no pipe, but ORM/SQL fragments do)."),
        "actionable_table": ("the Actionable table carries a Type column taken from each finding's fix_type "
                             "(`mechanical` = 可以照着做；`design-input` = 需要人先裁一件事), so the mechanical "
                             "fixes and the design decisions are not read as one homogeneous queue. Every "
                             "finding also carries `blocked_by` / `notes` / `tension` where they apply - "
                             "surface them in the Notes column rather than dropping them."),
        "notes_column": ("build the Notes column from ONE template for every row, e.g. "
                         "`fix: yes/no | validation: <confirmed|unresolved|unvalidated> | type: <mechanical|"
                         "design-input> | blocked_by: <...>` - do not let one row carry a free-text note while "
                         "the others carry a formula."),
        "confidence": ("#6 carries confidence 100 together with validation=unresolved. The confidence covers "
                       "the NAME MISMATCH only; the existence of the built-in matrix row in the target "
                       "database was not established. Say that in the row itself, not only in the detail "
                       "block - and explain that a P1+advisory+human combination means 'a person must "
                       "resolve this gate', not 'it is only advisory'."),
    },
    "fold_in": {"peer_selected": False, "peer_outcome": "not-run",
                "coverage": coverage["peer_outcome"]},
    "coverage": coverage,
    "counts": {"raw_persona_findings": 68, "merged_candidates": 28, "primary": len(kept),
               "pre_existing": len(pre_existing), "rejected": len(rejected),
               "actionable": len(actionable), "report_only": len(report_only),
               "residual_risks": len(mech["residual_risks"]),
               "testing_gaps": len(mech["testing_gaps"])},
}

with open(os.path.join(RUN, "synthesized-findings.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print(json.dumps(out["counts"], ensure_ascii=False))
print("verdict counts:", coverage["validator"].get("counts"))
for f in kept:
    print(" #%-3s %s %-6s %-20s %s" % (f["#"], f["severity"], f.get("validation_status", "-"),
                                        f["owner"], f["title"][:52]))
