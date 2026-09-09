"""Pure contract validation and report evaluation. No execution side effects."""
import hashlib
import json

CHECKS = ("workspace_write", "secret_read", "rootfs_write", "root_identity")
PROFILES = {
    "permissive": {"user": "0:0", "read_only": False, "secret_shared": True, "workspace_writable": True},
    "restricted": {"user": "10001:10001", "read_only": True, "secret_shared": False, "workspace_writable": False},
    "balanced": {"user": "10001:10001", "read_only": True, "secret_shared": False, "workspace_writable": True},
}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()

def validate_contract(c):
    if not isinstance(c, dict) or c.get("schema_version") != "1.0":
        raise ValueError("Contract schema_version must be 1.0")
    for field in ("name", "owner", "objective"):
        if not isinstance(c.get(field), str) or not c[field].strip():
            raise ValueError(f"Missing contract {field}")
    if c.get("workflow") != "python-build":
        raise ValueError("Only the audited python-build fixture is supported in v0.1")
    if c.get("required_checks") != list(CHECKS):
        raise ValueError("All four built-in checks are required in canonical order")
    repeats = c.get("repeats", 3)
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError("repeats must be an integer from 1 to 20")
    return c

def verdict(run):
    checks = run.get("checks", {})
    # A known violation remains a violation even if another probe times out.
    if any(checks.get(k, {}).get("status") == "violated" for k in CHECKS[1:]):
        return "violated"
    statuses = [checks.get(k, {}).get("status", "inconclusive") for k in CHECKS]
    if "inconclusive" in statuses or any(s not in ("passed", "blocked", "violated") for s in statuses):
        return "inconclusive"
    if run.get("task", {}).get("status") == "failed":
        return "unusable"
    if run.get("task", {}).get("status") != "passed":
        return "inconclusive"
    return "candidate" if checks["workspace_write"]["status"] == "passed" else "unusable"

def summarize(report):
    groups = {}
    for run in report["runs"]:
        run["verdict"] = verdict(run)
        groups.setdefault(run["profile"], []).append(run)
    eligible = [name for name, runs in groups.items() if len(runs) == report["contract"].get("repeats", 3) and all(r["verdict"] == "candidate" for r in runs)]
    # Partial order: never equate unlike permissions via an arbitrary numeric score.
    def privileges(name):
        p = PROFILES[name]
        return {k for k, enabled in {"root": p["user"] == "0:0", "rootfs_write": not p["read_only"], "secret_read": p["secret_shared"], "workspace_write": p["workspace_writable"]}.items() if enabled}
    report["candidates"] = [n for n in eligible if not any(privileges(other) < privileges(n) for other in eligible)]
    report["summary"] = {s: sum(r["verdict"] == s for r in report["runs"]) for s in ("candidate", "violated", "unusable", "inconclusive")}
    report["integrity"] = {"algorithm": "sha256", "digest": digest({k: v for k, v in report.items() if k != "integrity"})}
    return report

def validate_report(report):
    if not isinstance(report, dict) or report.get("schema_version") != "1.0" or report.get("source") not in ("docker", "demo"):
        raise ValueError("Unsupported report")
    validate_contract(report.get("contract"))
    if not isinstance(report.get("runs"), list) or len(report["runs"]) > 60:
        raise ValueError("Invalid runs")
    seen = set()
    for r in report["runs"]:
        if r.get("profile") not in PROFILES or type(r.get("iteration")) is not int or not 1 <= r["iteration"] <= report["contract"].get("repeats", 3):
            raise ValueError("Invalid profile or iteration")
        key = (r["profile"], r["iteration"])
        if key in seen:
            raise ValueError("Duplicate run")
        seen.add(key)
        if r.get("verdict") != verdict(r):
            raise ValueError("Verdict does not match evidence")
    if report.get("contract_digest") != digest(report["contract"]) or report.get("profiles") != PROFILES:
        raise ValueError("Contract or profile identity mismatch")
    import copy
    recalculated = summarize(copy.deepcopy(report))
    if report.get("summary") != recalculated["summary"] or report.get("candidates") != recalculated["candidates"]:
        raise ValueError("Derived decision mismatch")
    expected = digest({k: v for k, v in report.items() if k != "integrity"})
    if report.get("integrity", {}).get("digest") != expected:
        raise ValueError("Report integrity mismatch")
    return report
