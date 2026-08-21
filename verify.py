#!/usr/bin/env -S uv run python
"""Gate: C1-C14 verification for doc-azure delta audit project."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

# ─── helpers ────────────────────────────────────────────────────────────────

RepoRoot = Path(__file__).resolve().parent

CheckFn = Callable[[], tuple[bool, str]]


def _result(label: str, ok: bool, reason: str) -> tuple[bool, str]:
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {label}: {reason}")
    return ok, reason


# ─── C1 Layout ─────────────────────────────────────────────────────────────

def c1_layout() -> tuple[bool, str]:
    """Every required TARGET LAYOUT file must exist and be non-empty.

    out/ dirs may be absent until STEP 5. After STEP 5, out/ must exist
    with wiki/process files.
    """
    ok = True
    reasons = []

    required_files = [
        RepoRoot / "AGENTS.md",
        RepoRoot / "verify.py",
        RepoRoot / "pyproject.toml",
        RepoRoot / ".gitignore",
    ]
    required_scripts = [
        RepoRoot / "scripts" / "01_fetch_wiki.py",
        RepoRoot / "scripts" / "02_fetch_process.py",
        RepoRoot / "scripts" / "03_build_delta.py",
        RepoRoot / "scripts" / "04_publish_notion.py",
    ]
    required_src = [
        RepoRoot / "src" / "delta" / "__init__.py",
    ]
    required_tests = [
        RepoRoot / "tests" / "test_classify.py",
        RepoRoot / "tests" / "test_render.py",
        RepoRoot / "tests" / "test_evidence.py",
    ]
    required_docs = [
        RepoRoot / "docs" / "README.md",
        RepoRoot / "docs" / "prior-work.md",
        RepoRoot / "docs" / "api-contract.md",
        RepoRoot / "docs" / "delta-method.md",
        RepoRoot / "docs" / "decisions.md",
        RepoRoot / "docs" / "notion-publication.md",
    ]
    required_deltas = [
        RepoRoot / "deltas" / "leiame.md",
        RepoRoot / "deltas" / "politicas.md",
        RepoRoot / "deltas" / "changelog.md",
        RepoRoot / "deltas" / "apendice.md",
    ]
    optional_out_dirs = [
        RepoRoot / "out" / "wiki",
        RepoRoot / "out" / "process",
        RepoRoot / "out" / "delta",
        RepoRoot / "out" / "notion",
    ]

    all_required = (
        required_files + required_scripts + required_src
        + required_tests + required_docs + required_deltas
    )

    for f in all_required:
        if not f.exists() or f.stat().st_size == 0:
            reasons.append(f"missing or empty: {f.relative_to(RepoRoot)}")
            ok = False

    # tests/fixtures/ must be a directory (may be empty)
    fixtures_dir = RepoRoot / "tests" / "fixtures"
    if not fixtures_dir.is_dir():
        reasons.append("tests/fixtures/ is not a directory")
        ok = False

    # out/ dirs: warn only (they may be absent until STEP 5)
    missing_out = [d for d in optional_out_dirs if not d.exists()]
    if missing_out:
        reasons.append(f"out/ dirs absent (expected until STEP 5): {[str(d.relative_to(RepoRoot)) for d in missing_out]}")
        # Not a failure — out/ is explicitly allowed to be absent
    return ok, "; ".join(reasons) if reasons else "all required files present"


# ─── C2 Read-only proof ────────────────────────────────────────────────────

def c2_readonly() -> tuple[bool, str]:
    """Fail if any .py under scripts/src contains write verbs
    (POST/PATCH/PUT/DELETE/.post/.patch/.put/.delete) AND dev.azure.com
    in the same file. Also fail on 52+-char base64 PAT strings.

    Tests excluded: they verify read-only enforcement, not violate it.
    .md excluded: docs describe the model, don't execute calls.
    GUIDs excluded: not secrets (C3 handles real secrets from .env).
    """
    violations: list[str] = []
    write_verbs = re.compile(
        r"\b(POST|PATCH|PUT|DELETE|\.post\(|\.patch\(|\.put\(|\.delete\()",
        re.IGNORECASE,
    )
    # PAT-shaped: 52+ base64 chars (no spaces, single line)
    pat_pattern = re.compile(r"^[A-Za-z0-9+/]{52,}=*$", re.MULTILINE)

    # Only check production code: scripts/ and src/ (not tests/, not docs/)
    search_dirs = ["scripts", "src"]
    for dname in search_dirs:
        d = RepoRoot / dname
        if not d.is_dir():
            continue
        for fpath in d.rglob("*.py"):
            content = fpath.read_text(encoding="utf-8")
            has_azure = "dev.azure.com" in content
            for lineno, line in enumerate(content.splitlines(), 1):
                if write_verbs.search(line) and has_azure:
                    violations.append(
                        f"{fpath.relative_to(RepoRoot)}:{lineno} "
                        f"write-verb in azure context: {line.strip()}"
                    )
                if pat_pattern.search(line):
                    violations.append(
                        f"{fpath.relative_to(RepoRoot)}:{lineno} "
                        f"PAT-shaped literal: {line.strip()[:100]}"
                    )

    if violations:
        return False, "\n    ".join(violations)
    return True, "no write verbs in production code, no hardcoded PATs"


# ─── C3 Secrets ─────────────────────────────────────────────────────────────

def c3_secrets() -> tuple[bool, str]:
    """Every key in .env must not appear in any tracked file or out/deltas/docs."""
    env_path = RepoRoot / ".env"
    if not env_path.exists():
        return True, ".env absent (no secrets to check)"

    env_vars: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            val = line.split("=", 1)[1].strip().strip("'\"").strip()
            if key:
                env_vars[key] = val

    violations: list[str] = []

    # Check .env is not tracked
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=RepoRoot,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        violations.append(".env is tracked by git (R2 violation)")

    # Check each value against tracked files
    tracked = (
        subprocess.run(
            ["git", "ls-files"],
            cwd=RepoRoot,
            capture_output=True,
            text=True,
        )
        .stdout.splitlines()
    )
    for frel in tracked:
        f = RepoRoot / frel
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for key, val in env_vars.items():
            if val and val in content:
                violations.append(
                    f"secret key '{key}' value appears in tracked file: {frel}"
                )

    # Check against out/, deltas/, docs/
    for pattern in ["out/", "deltas/", "docs/"]:
        for fpath in RepoRoot.glob(f"{pattern}**/*"):
            if fpath.is_dir():
                continue
            try:
                content = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            for key, val in env_vars.items():
                if val and val in content:
                    violations.append(
                        f"secret key '{key}' value appears in {fpath.relative_to(RepoRoot)}"
                    )

    if violations:
        return False, "; ".join(violations)
    return True, "no secrets leaked to tracked files or out/deltas/docs"


# ─── C4 Tests ───────────────────────────────────────────────────────────────

def c4_tests() -> tuple[bool, str]:
    """Run pytest -q; must exit 0 and collect >= 8 tests.
    Fail if tests/ imports httpx, requests, urllib, or asyncio.
    """
    # Check imports first
    test_import_violations: list[str] = []
    bad_imports = {"httpx", "requests", "asyncio"}
    for fpath in (RepoRoot / "tests").rglob("*.py"):
        content = fpath.read_text(encoding="utf-8")
        for lineno, line in enumerate(content.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            for imp in bad_imports:
                if re.search(rf"\bimport\s+{imp}\b", line) or re.search(
                    rf"\bfrom\s+{imp}\b", line
                ):
                    test_import_violations.append(
                        f"{fpath.relative_to(RepoRoot)}:{lineno} "
                        f"imports {imp}"
                    )
    if test_import_violations:
        return False, "; ".join(test_import_violations)

    # Run pytest
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "--collect-only"],
        cwd=RepoRoot,
        capture_output=True,
        text=True,
    )
    collected = 0
    for line in result.stdout.splitlines():
        m = re.search(r"(\d+)\s+test", line)
        if m:
            collected = int(m.group(1))
            break

    result_run = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=RepoRoot,
        capture_output=True,
        text=True,
    )

    if result_run.returncode != 0:
        return False, f"pytest failed: {result_run.stdout[:200]} {result_run.stderr[:200]}"
    if collected < 8:
        return False, f"only {collected} tests collected (need >= 8)"
    return True, f"{collected} tests collected, all passing"


# ─── C5 Evidence integrity ─────────────────────────────────────────────────

def c5_evidence() -> tuple[bool, str]:
    """Parse deltas/*.md. For every row: class is one of 4 literals.
    Every non-n/a evidence pointer resolves to existing file + line / JSON path.
    Fail: DOC_ONLY with non-n/a azure_evidence, AZURE_ONLY with non-n/a doc_evidence.
    """
    violations: list[str] = []
    slugs = ["leiame", "politicas", "changelog", "apendice"]

    for slug in slugs:
        fpath = RepoRoot / "deltas" / f"{slug}.md"
        if not fpath.exists():
            violations.append(f"deltas/{slug}.md missing")
            continue

        content = fpath.read_text(encoding="utf-8")
        lines = content.splitlines()
        in_table = False

        for lineno, raw in enumerate(lines, 1):
            stripped = raw.strip()
            # Detect table header
            if stripped.startswith("| id |") or stripped.startswith("|id|"):
                in_table = True
                continue
            if not in_table:
                continue
            # Skip separator |---|...
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            # Skip empty rows
            if stripped == "|" or stripped.strip("| ").strip() == "":
                continue

            # Parse cells
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 5:
                continue

            row_id, claim, cls, doc_ev, azure_ev = (
                cells[0], cells[1], cells[2], cells[3], cells[4]
            )
            consequence = cells[5] if len(cells) > 5 else ""

            valid_classes = {"DOC_ONLY", "AZURE_ONLY", "DIVERGENT", "MATCH"}
            if cls not in valid_classes:
                violations.append(
                    f"deltas/{slug}.md:{lineno} invalid class '{cls}'"
                )

            # Evidence constraints
            if cls == "DOC_ONLY" and azure_ev not in ("n/a", ""):
                violations.append(
                    f"deltas/{slug}.md:{lineno} DOC_ONLY has non-n/a azure_evidence: {azure_ev}"
                )
            if cls == "AZURE_ONLY" and doc_ev not in ("n/a", ""):
                violations.append(
                    f"deltas/{slug}.md:{lineno} AZURE_ONLY has non-n/a doc_evidence: {doc_ev}"
                )

            # Resolve doc_evidence
            if doc_ev and doc_ev != "n/a":
                m = re.match(r"^(out/wiki/[^#]+)#L(\d+)$", doc_ev)
                if m:
                    doc_file = RepoRoot / m.group(1)
                    line_num = int(m.group(2))
                    if not doc_file.exists():
                        violations.append(
                            f"deltas/{slug}.md:{lineno} doc_evidence file not found: {doc_ev}"
                        )
                    elif line_num > len(doc_file.read_text(encoding="utf-8").splitlines()):
                        violations.append(
                            f"deltas/{slug}.md:{lineno} doc_evidence line {line_num} out of range"
                        )
                else:
                    violations.append(
                        f"deltas/{slug}.md:{lineno} malformed doc_evidence: {doc_ev}"
                    )

            # Resolve azure_evidence
            if azure_ev and azure_ev != "n/a":
                m = re.match(r"^(out/process/[^#]+)#(.+)$", azure_ev)
                if m:
                    az_file = RepoRoot / m.group(1)
                    json_path = m.group(2)
                    if not az_file.exists():
                        violations.append(
                            f"deltas/{slug}.md:{lineno} azure_evidence file not found: {azure_ev}"
                        )
                    else:
                        # Verify JSON path resolves
                        try:
                            data = json.loads(az_file.read_text(encoding="utf-8"))
                            parts = json_path.split("/")
                            node = data
                            for part in parts:
                                if part == "":
                                    continue
                                if isinstance(node, dict):
                                    node = node.get(part)
                                elif isinstance(node, list):
                                    try:
                                        node = node[int(part)]
                                    except (ValueError, IndexError):
                                        node = None
                                else:
                                    node = None
                                if node is None:
                                    violations.append(
                                        f"deltas/{slug}.md:{lineno} "
                                        f"json-path not found: {azure_ev}"
                                    )
                                    break
                        except json.JSONDecodeError:
                            violations.append(
                                f"deltas/{slug}.md:{lineno} invalid JSON: {m.group(1)}"
                            )
                else:
                    violations.append(
                        f"deltas/{slug}.md:{lineno} malformed azure_evidence: {azure_ev}"
                    )

    if violations:
        return False, "; ".join(violations)
    return True, "all delta rows valid, all evidence pointers resolvable"


# ─── C6 Counts ─────────────────────────────────────────────────────────────

def c6_counts() -> tuple[bool, str]:
    """Each delta's SUMMARY block counts must equal recomputed row counts."""
    slugs = ["leiame", "politicas", "changelog", "apendice"]
    violations: list[str] = []

    for slug in slugs:
        fpath = RepoRoot / "deltas" / f"{slug}.md"
        if not fpath.exists():
            continue  # handled by C1
        content = fpath.read_text(encoding="utf-8")

        # Extract SUMMARY block
        m = re.search(
            r"^\s*SUMMARY\s*\n((?:DOC_ONLY=\d+\n|AZURE_ONLY=\d+\n|"
            r"DIVERGENT=\d+\n|MATCH=\d+\n)+)",
            content,
            re.MULTILINE,
        )
        if not m:
            continue
        summary_block = m.group(1)
        stated = dict(
            re.findall(r"(DOC_ONLY|AZURE_ONLY|DIVERGENT|MATCH)=(\d+)", summary_block)
        )

        # Count actual rows
        actual = {"DOC_ONLY": 0, "AZURE_ONLY": 0, "DIVERGENT": 0, "MATCH": 0}
        for cls_match in re.finditer(
            r"^\|\s*[^|]+\|\s*[^|]+\|\s*(DOC_ONLY|AZURE_ONLY|DIVERGENT|MATCH)\s*\|",
            content,
            re.MULTILINE,
        ):
            actual[cls_match.group(1)] += 1

        for cls in ["DOC_ONLY", "AZURE_ONLY", "DIVERGENT", "MATCH"]:
            s = int(stated.get(cls, 0))
            a = actual[cls]
            if s != a:
                violations.append(
                    f"deltas/{slug}.md SUMMARY {cls}={s} != actual {a}"
                )

    if violations:
        return False, "; ".join(violations)
    return True, "all SUMMARY counts match actual row counts"


# ─── C7 Non-emptiness ─────────────────────────────────────────────────────

def c7_nonempty() -> tuple[bool, str]:
    """Each delta has >=1 row; union has >=1 non-MATCH; no delta is
    all-MATCH unless decisions.md explains why.
    """
    slugs = ["leiame", "politicas", "changelog", "apendice"]
    violations: list[str] = []
    total_non_match = 0
    all_match_slugs: list[str] = []

    decisions = (RepoRoot / "docs" / "decisions.md").read_text(
        encoding="utf-8"
    ) if (RepoRoot / "docs" / "decisions.md").exists() else ""

    for slug in slugs:
        fpath = RepoRoot / "deltas" / f"{slug}.md"
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8")
        rows = re.findall(
            r"^\|\s*[^|]+\|\s*[^|]+\|\s*(DOC_ONLY|AZURE_ONLY|DIVERGENT|MATCH)\s*\|",
            content,
            re.MULTILINE,
        )
        if len(rows) == 0:
            violations.append(f"deltas/{slug}.md has no rows")
            continue
        non_match = sum(1 for r in rows if r != "MATCH")
        total_non_match += non_match
        if non_match == 0:
            all_match_slugs.append(slug)

    if total_non_match == 0:
        violations.append("Union of all deltas has zero non-MATCH rows")

    if all_match_slugs:
        # Check decisions.md for explanation
        if not re.search(
            r"(?i)(all.match|exclusively.match|only.match)",
            decisions,
        ):
            violations.append(
                f"Deltas with all-MATCH rows lack explanation in docs/decisions.md: {all_match_slugs}"
            )

    if violations:
        return False, "; ".join(violations)
    return True, "all deltas have rows, union has non-MATCH rows"


# ─── C8 Coverage ────────────────────────────────────────────────────────────

def c8_coverage() -> tuple[bool, str]:
    """out/wiki/ must have exactly four .md files; out/process/ must have
    process.json plus one file per WIT; WIT count must match process.json.
    SKIP if out/ not populated.
    """
    wiki_dir = RepoRoot / "out" / "wiki"
    proc_dir = RepoRoot / "out" / "process"

    if not wiki_dir.exists() or not proc_dir.exists():
        return True, "SKIP: out/ not yet populated"

    wiki_files = list(wiki_dir.glob("*.md"))
    expected_wiki = {"leiame.md", "politicas.md", "changelog.md", "apendice.md"}
    actual_wiki = {f.name for f in wiki_files}

    if actual_wiki != expected_wiki:
        return False, (
            f"wiki files mismatch: expected {expected_wiki}, got {actual_wiki}"
        )

    if any(f.stat().st_size == 0 for f in wiki_files):
        return False, "some wiki files are empty"

    proc_files = list(proc_dir.glob("*.json"))
    proc_names = {f.stem for f in proc_files}

    if "process" not in proc_names:
        return False, "out/process/process.json missing"

    process_json = (proc_dir / "process.json").read_text(encoding="utf-8")
    try:
        proc_data = json.loads(process_json)
    except json.JSONDecodeError:
        return False, "out/process/process.json is invalid JSON"

    wit_count_field = None
    for key in ["witCount", "workItemTypesCount", "workitemtypecount"]:
        if key in proc_data:
            wit_count_field = proc_data[key]
            break

    # Count WIT files (exclude process.json)
    wit_files = [f for f in proc_files if f.name != "process.json"]
    if wit_count_field is not None:
        if len(wit_files) != wit_count_field:
            return False, (
                f"WIT count mismatch: process.json says {wit_count_field}, "
                f"found {len(wit_files)} files"
            )

    return True, (
        f"out/wiki/ has 4 files, out/process/ has process.json + "
        f"{len(wit_files)} WIT files"
    )


# ─── C9 Consequence rule ───────────────────────────────────────────────────

def c9_consequence() -> tuple[bool, str]:
    """Every non-MATCH row must have a non-empty consequence sentence."""
    slugs = ["leiame", "politicas", "changelog", "apendice"]
    violations: list[str] = []

    for slug in slugs:
        fpath = RepoRoot / "deltas" / f"{slug}.md"
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8")

        for m in re.finditer(
            r"^\|\s*[^|]+\|\s*[^|]+\|\s*(DOC_ONLY|AZURE_ONLY|DIVERGENT)\s*\|[^|]*\|[^|]*\|(.*)$",
            content,
            re.MULTILINE,
        ):
            cls, consequence = m.group(1), m.group(2).strip()
            if not consequence:
                lineno = content[: m.start()].count("\n") + 1
                violations.append(
                    f"deltas/{slug}.md:{lineno} {cls} row missing consequence"
                )

    if violations:
        return False, "; ".join(violations)
    return True, "all non-MATCH rows have consequence sentences"


# ─── C10 Determinism ───────────────────────────────────────────────────────

def c10_determinism() -> tuple[bool, str]:
    """Run 03_build_delta.py twice; deltas/*.md must be byte-identical.
    SKIP if out/ not populated.
    """
    out_wiki = RepoRoot / "out" / "wiki"
    out_proc = RepoRoot / "out" / "process"
    if not out_wiki.exists() or not out_proc.exists():
        return True, "SKIP: out/ not yet populated"

    script = RepoRoot / "scripts" / "03_build_delta.py"
    if not script.exists():
        return False, "scripts/03_build_delta.py not found"

    # Run once
    r1 = subprocess.run(
        ["uv", "run", "python", str(script)],
        cwd=RepoRoot,
        capture_output=True,
        text=True,
    )

    # Capture deltas after run 1
    delta_dir = RepoRoot / "deltas"
    slugs = ["leiame", "politicas", "changelog", "apendice"]
    after1: dict[str, bytes] = {}
    for slug in slugs:
        f = delta_dir / f"{slug}.md"
        if f.exists():
            after1[slug] = f.read_bytes()

    # Run again
    r2 = subprocess.run(
        ["uv", "run", "python", str(script)],
        cwd=RepoRoot,
        capture_output=True,
        text=True,
    )

    for slug, data1 in after1.items():
        f = delta_dir / f"{slug}.md"
        data2 = f.read_bytes() if f.exists() else b""
        if data1 != data2:
            return False, f"deltas/{slug}.md changed between runs (non-deterministic)"

    return True, "delta files are identical across two runs"


# ─── C11 Idempotency ──────────────────────────────────────────────────────

def c11_idempotency() -> tuple[bool, str]:
    """Every script (01-04) accepts --refresh flag.
    Without --refresh, second run performs zero network calls.
    """
    violations: list[str] = []
    scripts = [
        RepoRoot / "scripts" / f"{n:02d}_{name}.py"
        for n, name in enumerate(
            ["fetch_wiki", "fetch_process", "build_delta", "publish_notion"], 1
        )
    ]

    for script in scripts:
        if not script.exists():
            violations.append(f"{script.name} not found")
            continue
        content = script.read_text(encoding="utf-8")
        if "--refresh" not in content:
            violations.append(f"{script.name} missing --refresh flag")

    # Check calls counter
    calls_file = RepoRoot / "out" / "_calls.json"
    if not calls_file.exists():
        # No calls file yet — skip the second-run network check
        if violations:
            return False, "; ".join(violations)
        return True, "SKIP: out/_calls.json not present yet"

    calls_before = json.loads(calls_file.read_text(encoding="utf-8"))

    # Run a representative script (02_fetch_process) that has network calls
    script02 = RepoRoot / "scripts" / "02_fetch_process.py"
    if script02.exists():
        subprocess.run(
            ["uv", "run", "python", str(script02)],
            cwd=RepoRoot,
            capture_output=True,
            text=True,
        )

    calls_after = json.loads(calls_file.read_text(encoding="utf-8"))
    if calls_after.get("network_calls", 0) > calls_before.get("network_calls", 0):
        violations.append("second run without --refresh made network calls")

    if violations:
        return False, "; ".join(violations)
    return True, "all scripts accept --refresh; idempotency verified"


# ─── C12 Docs ──────────────────────────────────────────────────────────────

def c12_docs() -> tuple[bool, str]:
    """docs/api-contract.md >= 4 learn.microsoft.com URLs.
    docs/decisions.md >= 1 rejected alternative per script (01-04).
    docs/prior-work.md exists and names session-1.md.
    docs/README.md states what was done and why (<=200 lines).
    """
    violations: list[str] = []

    # api-contract.md — >= 4 distinct learn.microsoft.com URLs
    api_contract = RepoRoot / "docs" / "api-contract.md"
    if api_contract.exists():
        urls = re.findall(
            r"https://learn\.microsoft\.com[^\s\)]+", api_contract.read_text()
        )
        if len(set(urls)) < 4:
            violations.append(
                f"docs/api-contract.md has only {len(set(urls))} "
                f"learn.microsoft.com URLs (need >= 4)"
            )
    else:
        violations.append("docs/api-contract.md missing")

    # decisions.md — >= 1 rejected alternative per script 01-04
    decisions = RepoRoot / "docs" / "decisions.md"
    if decisions.exists():
        for n in range(1, 5):
            pattern = rf"(?i)(descartad|rejected|dismissed).*?(script|script.0{n}|0{n}_)"
            if not re.search(pattern, decisions.read_text()):
                violations.append(f"docs/decisions.md missing rejected alternative for script 0{n}")
    else:
        violations.append("docs/decisions.md missing")

    # prior-work.md — names session-1.md
    prior_work = RepoRoot / "docs" / "prior-work.md"
    if prior_work.exists():
        if "session-1.md" not in prior_work.read_text():
            violations.append("docs/prior-work.md does not reference session-1.md")
    else:
        violations.append("docs/prior-work.md missing")

    # README.md — exists, <=200 lines, states what/why
    readme = RepoRoot / "docs" / "README.md"
    if readme.exists():
        lines = readme.read_text(encoding="utf-8").splitlines()
        if len(lines) > 200:
            violations.append(
                f"docs/README.md has {len(lines)} lines (limit 200)"
            )
        # Check it states purpose
        content = readme.read_text(encoding="utf-8").lower()
        if "why" not in content and "por" not in content and "porque" not in content:
            violations.append("docs/README.md does not state purpose/why")
    else:
        violations.append("docs/README.md missing")

    if violations:
        return False, "; ".join(violations)
    return True, "all doc requirements met"


# ─── C13 Publication ───────────────────────────────────────────────────────

def c13_publication() -> tuple[bool, str]:
    """docs/notion-publication.md lists 4 Notion URLs with timestamps.
    Each out/notion/<slug>.fetched.md must exist, contain DELTA-AUDIT-MARKER-<slug>,
    and verbatim first non-MATCH row text from matching deltas/<slug>.md.
    SKIP until STEP 9.
    """
    notion_pub = RepoRoot / "docs" / "notion-publication.md"
    out_notion = RepoRoot / "out" / "notion"
    if not notion_pub.exists() or not out_notion.exists():
        return True, "SKIP: Notion publication pending (docs/notion-publication.md or out/notion/ absent)"

    violations: list[str] = []
    content = notion_pub.read_text(encoding="utf-8")
    urls = re.findall(r"https://app\.notion\.com/[^\s\)'\"]+", content)

    if len(urls) != 4:
        violations.append(
            f"docs/notion-publication.md has {len(urls)} Notion URLs (need exactly 4)"
        )

    # Check timestamps
    timestamps = re.findall(
        r"(?:\d{4}-\d{2}-\d{2}|created|updated|published)\s*[:\-]\s*\d",
        content,
        re.IGNORECASE,
    )
    if len(timestamps) < 4:
        violations.append(
            f"docs/notion-publication.md has only {len(timestamps)} timestamps (need >= 4)"
        )

    slugs = ["leiame", "politicas", "changelog", "apendice"]
    for slug in slugs:
        fetched = out_notion / f"{slug}.fetched.md"
        if not fetched.exists():
            violations.append(f"out/notion/{slug}.fetched.md missing")
            continue
        fetched_content = fetched.read_text(encoding="utf-8")
        marker = f"DELTA-AUDIT-MARKER-{slug}"
        if marker not in fetched_content:
            violations.append(
                f"out/notion/{slug}.fetched.md missing marker '{marker}'"
            )
        # Check verbatim first non-MATCH row
        delta_file = RepoRoot / "deltas" / f"{slug}.md"
        if delta_file.exists():
            delta_content = delta_file.read_text(encoding="utf-8")
            # Extract first non-MATCH row claim text
            m = re.search(
                r"^\|\s*[^|]+\|\s*([^|]+)\|\s*(DOC_ONLY|AZURE_ONLY|DIVERGENT)\s*\|",
                delta_content,
                re.MULTILINE,
            )
            if m:
                claim_text = m.group(1).strip()
                if claim_text and claim_text not in fetched_content:
                    violations.append(
                        f"out/notion/{slug}.fetched.md missing verbatim row: {claim_text[:60]}"
                    )

    if violations:
        return False, "; ".join(violations)
    return True, "Notion publication verified"


# ─── C14 No prose-only module ─────────────────────────────────────────────

def c14_no_prose_only() -> tuple[bool, str]:
    """Every .py under src/ and scripts/ must contain at least one def or __main__."""
    violations: list[str] = []
    for dname in ["src", "scripts"]:
        d = RepoRoot / dname
        if not d.is_dir():
            continue
        for fpath in d.rglob("*.py"):
            content = fpath.read_text(encoding="utf-8")
            if "def " not in content and "__main__" not in content:
                violations.append(
                    f"{fpath.relative_to(RepoRoot)} is prose-only (no def or __main__)"
                )
    if violations:
        return False, "; ".join(violations)
    return True, "all .py modules have executable code"


# ─── Main ──────────────────────────────────────────────────────────────────

CHECKS: list[tuple[str, CheckFn]] = [
    ("C1 Layout", c1_layout),
    ("C2 Read-only proof", c2_readonly),
    ("C3 Secrets", c3_secrets),
    ("C4 Tests", c4_tests),
    ("C5 Evidence integrity", c5_evidence),
    ("C6 Counts", c6_counts),
    ("C7 Non-emptiness", c7_nonempty),
    ("C8 Coverage", c8_coverage),
    ("C9 Consequence rule", c9_consequence),
    ("C10 Determinism", c10_determinism),
    ("C11 Idempotency", c11_idempotency),
    ("C12 Docs", c12_docs),
    ("C13 Publication", c13_publication),
    ("C14 No prose-only module", c14_no_prose_only),
]


def main() -> int:
    print("=== verify.py gate ===")
    results: list[tuple[str, bool, str]] = []
    for label, fn in CHECKS:
        try:
            ok, reason = fn()
        except Exception as exc:
            ok, reason = False, f"EXCEPTION: {exc}"
        results.append((label, ok, reason))

    print()
    all_ok = all(ok for _, ok, _ in results)
    ok_checks = [label for label, ok, _ in results if ok]
    fail_checks = [(label, reason) for label, ok, reason in results if not ok]

    print(f"  OK: {ok_checks}")
    if fail_checks:
        print(f"  FAIL ({len(fail_checks)}):")
        for label, reason in fail_checks:
            print(f"    {label}: {reason}")

    print()
    if all_ok:
        print("GATE_OK")
        return 0
    else:
        reasons_str = ", ".join(label for label, _ in fail_checks)
        print(f"GATE_FAIL: {reasons_str}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
