"""Build raw-returns.json from the per-reviewer artifacts (merge-tier fields only)."""
import json
import pathlib

RUN = pathlib.Path("/tmp/compound-engineering-1000/ce-code-review/20261006-sprint4")
# project-standards' on-disk artifact failed JSON validation; its valid in-band
# compact return is staged alongside and used instead (per subagent-template).
SOURCES = {
    "correctness": "correctness.json",
    "security": "security.json",
    "adversarial": "adversarial.json",
    "project-standards": "project-standards-compact.json",
    "testing": "testing.json",
    "maintainability": "maintainability.json",
    "api-contract": "api-contract.json",
    "data-migration": "data-migration.json",
    "reliability": "reliability.json",
    "performance": "performance.json",
}
MERGE_TIER = [
    "title", "severity", "file", "line", "confidence", "autofix_class", "owner",
    "requires_verification", "pre_existing", "suggested_fix", "first_evidence",
]

returns, total, degraded = [], 0, []
for name, fname in SOURCES.items():
    p = RUN / fname
    d = json.loads(p.read_text())
    fs = [{k: f.get(k) for k in MERGE_TIER} for f in d.get("findings", [])]
    total += len(fs)
    entry = {
        "reviewer": name,
        "findings": fs,
        "residual_risks": d.get("residual_risks", []),
        "testing_gaps": d.get("testing_gaps", []),
    }
    if d.get("artifact_status"):
        entry["artifact_status"] = d["artifact_status"]
        degraded.append(name)
    returns.append(entry)

(RUN / "raw-returns.json").write_text(
    json.dumps(returns, ensure_ascii=False, indent=1))

print("reviewers collected:", len(returns), "/ 10")
print("total findings:", total)
print("degraded (artifact invalid, compact return used):", degraded or "none")
for r in returns:
    c = {s: sum(1 for f in r["findings"] if f["severity"] == s)
         for s in ("P0", "P1", "P2", "P3")}
    print(f"  {r['reviewer']:<20} {len(r['findings']):>2}  "
          f"P0={c['P0']} P1={c['P1']} P2={c['P2']} P3={c['P3']}")
