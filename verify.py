#!/usr/bin/env -S uv run python
"""Non-mutating substantive gate for the doc-azure audit repository."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from delta.build import BuildError, FIXED_SLUGS, build_all_reports
from delta.catalog import CatalogError, load_catalog
from delta.document_coverage import CoverageError, _load_baseline, assess_documents
from delta.process_coverage import _validate_inventory
from doc_azure.audit import _process_gaps
from delta.notion import (
    NotionPublicationError,
    expected_publication_manifest,
    load_publication_manifest,
    verify_fetched_notion,
    verify_publication_gate,
)
from doc_azure.azure_client import ALLOWED_OPERATIONS, is_allowlisted_read


class VerificationError(RuntimeError):
    """Raised when a repository invariant cannot be proved."""


_VOLATILE_PROVENANCE_LINES = (
    (
        re.compile(
            r"^- Wiki: coletada em `[^`]+`; geração `[^`]+`; "
            r"SHA-256 do manifesto `[^`]+`\.$"
        ),
        "- Wiki: coletada em `<volatile>`; geração `<volatile>`; "
        "SHA-256 do manifesto `<volatile>`.\n",
    ),
    (
        re.compile(
            r"^- Processo: coletado em `[^`]+`; geração `[^`]+`; "
            r"SHA-256 do manifesto `[^`]+`\.$"
        ),
        "- Processo: coletado em `<volatile>`; geração `<volatile>`; "
        "SHA-256 do manifesto `<volatile>`.\n",
    ),
)


def _canonical_report_bytes(payload: bytes, label: str) -> bytes:
    """Normalize only run-specific provenance before stable report comparison."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise VerificationError(f"{label} is not valid UTF-8") from None
    canonical_lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        newline = raw_line[len(line):]
        replacement = next(
            (
                replacement
                for pattern, replacement in _VOLATILE_PROVENANCE_LINES
                if pattern.fullmatch(line)
            ),
            None,
        )
        if replacement is None:
            canonical_lines.append(raw_line)
        else:
            canonical_lines.append(replacement[:-1] + newline)
    return "".join(canonical_lines).encode("utf-8")


def run_checked(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one local command and fail without replaying possibly sensitive output."""

    if not command or any(not isinstance(part, str) or not part for part in command):
        raise VerificationError("subprocess command is invalid")
    completed = subprocess.run(
        list(command),
        cwd=Path(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"subprocess {command[0]!r} failed with exit code "
            f"{completed.returncode}"
        )
    return completed


def verify_reports(root: Path) -> None:
    """Rebuild all claims in a temporary directory and compare exact bytes."""

    repository_root = Path(root)
    catalog = repository_root / "config" / "wiki_claims.json"
    try:
        with tempfile.TemporaryDirectory(prefix="doc-azure-verify-") as temporary:
            rebuilt = build_all_reports(
                repository_root,
                catalog,
                Path(temporary),
                coverage_baseline=(
                    repository_root / "config" / "document-coverage.json"
                    if (repository_root / "config" / "document-coverage.json").exists()
                    else None
                ),
            )
            for rebuilt_path in rebuilt:
                versioned_path = repository_root / "deltas" / rebuilt_path.name
                try:
                    expected = _read_regular_file(
                        rebuilt_path, "rebuilt report"
                    )
                    actual = _read_regular_file(
                        versioned_path, "versioned report"
                    )
                except VerificationError:
                    raise
                if _canonical_report_bytes(actual, "versioned report") != _canonical_report_bytes(
                    expected, "rebuilt report"
                ):
                    raise VerificationError(
                        f"deltas/{rebuilt_path.name} differs from verified rebuild"
                    )
    except BuildError as error:
        raise VerificationError(f"verified report rebuild failed: {error}") from None


def verify_coverage_baselines(root: Path) -> None:
    """Validate versioned coverage contracts and current snapshots when present."""

    repository_root = Path(root)
    catalog_path = repository_root / "config" / "wiki_claims.json"
    document_path = repository_root / "config" / "document-coverage.json"
    process_path = repository_root / "config" / "process-coverage.json"
    if not all(path.is_file() and not path.is_symlink() for path in (
        catalog_path, document_path, process_path
    )):
        raise VerificationError("coverage baseline files are missing")
    try:
        claims = load_catalog(catalog_path)
        _load_baseline(document_path, catalog_path, claims)
        payload = json.loads(process_path.read_bytes())
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version", "catalog_sha256", "entries"
        } or type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise VerificationError("process coverage baseline schema is invalid")
        if payload["catalog_sha256"] != hashlib.sha256(catalog_path.read_bytes()).hexdigest():
            raise VerificationError("process coverage baseline catalog hash differs")
        _validate_inventory(payload["entries"])
        wiki_current = (repository_root / "out" / "wiki" / "CURRENT").exists()
        process_current = (repository_root / "out" / "process" / "CURRENT").exists()
        if wiki_current:
            documentary = assess_documents(repository_root, catalog_path, document_path)
            if documentary.changes:
                raise VerificationError("current wiki snapshot has unmapped documentary changes")
        if process_current:
            gaps, _ = _process_gaps(repository_root, catalog_path, process_path)
            if gaps:
                raise VerificationError("current process snapshot differs from coverage baseline")
    except (CatalogError, CoverageError, OSError, UnicodeError, ValueError, TypeError) as error:
        if isinstance(error, VerificationError):
            raise
        raise VerificationError(f"coverage baseline is invalid: {type(error).__name__}") from None


def verify_secret_literals(root: Path) -> None:
    """Reject tracked or generated files containing a sensitive .env value."""

    repository_root = Path(root)
    env_path = repository_root / ".env"
    if not env_path.exists():
        return
    secret_values = _load_secret_values(env_path)
    tracked = _tracked_files(repository_root)
    if ".env" in tracked or any(
        path.startswith(".env.") and path != ".env.example" for path in tracked
    ):
        raise VerificationError("a secret environment file is tracked")
    if not secret_values:
        return

    leaked_paths: set[str] = set()
    for path in _candidate_secret_scan_files(repository_root, tracked):
        try:
            body = path.read_bytes()
        except OSError:
            raise VerificationError(
                f"cannot scan {path.relative_to(repository_root)} for secrets"
            ) from None
        if any(value in body for value in secret_values):
            leaked_paths.add(path.relative_to(repository_root).as_posix())
    if leaked_paths:
        raise VerificationError(
            "secret literal found in: " + ", ".join(sorted(leaked_paths))
        )


def verify_gitignore(root: Path) -> None:
    """Require an ignore pattern for every user-requested local artifact class."""

    path = Path(root) / ".gitignore"
    try:
        patterns = {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except (OSError, UnicodeError):
        raise VerificationError(".gitignore is missing or unreadable") from None
    categories = {
        "secrets": ({".env", ".env.*"}, {"*.pem", "*.key"}),
        "credentials": ({"*credentials*.json"}, {"*token*.json", "*token*.txt"}),
        "python caches": ({"__pycache__/", "*.py[cod]"}, {".pytest_cache/"}),
        "virtual environments": ({".venv/", "venv/", "env/"},),
        "builds": ({"build/", "dist/"}, {"*.egg-info/"}, {"out/"}),
        "editor and OS state": ({".DS_Store", "Thumbs.db"}, {".idea/", ".vscode/"}, {"*.swp", "*.swo"}),
        "logs": ({"*.log", "logs/"},),
        "local databases": ({"*.db", "*.sqlite", "*.sqlite3"},),
        "local agent state": ({".worktrees/", ".superpowers/", ".opencode/"},),
    }
    for category, required_groups in categories.items():
        if any(not (patterns & alternatives) for alternatives in required_groups):
            raise VerificationError(f"gitignore category is incomplete: {category}")


def verify_read_allowlist() -> None:
    """Exercise the imported semantic operation table instead of scanning verbs."""

    if not ALLOWED_OPERATIONS or any(
        operation.method not in {"GET", "POST"} for operation in ALLOWED_OPERATIONS
    ):
        raise VerificationError("Azure operation allowlist contains an invalid method")
    post_operations = tuple(
        operation for operation in ALLOWED_OPERATIONS if operation.method == "POST"
    )
    if len(post_operations) != 2:
        raise VerificationError("Azure query-only POST allowlist is not exact")

    allowed_samples = (
        ("GET", "/Project/_apis/wiki/wikis/Wiki/pages/35"),
        ("GET", "/_apis/work/processes"),
        ("GET", "/_apis/work/processes/process-id/workitemtypes"),
        ("POST", "/Project/_apis/wit/wiql"),
        ("POST", "/Project/_apis/wit/workitemsbatch"),
    )
    if any(not is_allowlisted_read(method, path) for method, path in allowed_samples):
        raise VerificationError("an approved Azure read route is not allowlisted")
    rejected_samples = (
        ("POST", "/_apis/work/processes"),
        ("POST", "/Project/_apis/wiki/wikis/Wiki/pages/35"),
        ("POST", "/Project/_apis/wit/wiql/query-id"),
        ("PUT", "/_apis/work/processes/process-id"),
        ("PATCH", "/_apis/work/processes/process-id"),
        ("DELETE", "/_apis/work/processes/process-id"),
    )
    if any(is_allowlisted_read(method, path) for method, path in rejected_samples):
        raise VerificationError("a mutating or non-query Azure route is allowlisted")


def verify_notion_artifacts(root: Path, *, require_fetched: bool = False) -> None:
    """Check fixed page identities, current hashes, and optional read-back receipts."""

    repository_root = Path(root)
    try:
        if require_fetched:
            verify_publication_gate(repository_root)
            return
        expected = expected_publication_manifest(repository_root)
        notion_root = repository_root / "out" / "notion"
        manifest_path = notion_root / "publication-manifest.json"
        fetched_root = notion_root / "fetched"
        if manifest_path.exists():
            actual = load_publication_manifest(manifest_path)
            if actual != expected:
                raise VerificationError(
                    "Notion publication manifest is stale relative to reports"
                )
        else:
            actual = None
        if fetched_root.exists():
            if actual is None:
                raise VerificationError(
                    "Notion fetched receipts exist without a publication manifest"
                )
            verify_fetched_notion(actual, fetched_root)
        elif require_fetched:
            raise VerificationError("verified Notion fetched receipts are missing")
        if require_fetched and actual is None:
            raise VerificationError("Notion publication manifest is missing")
    except NotionPublicationError as error:
        raise VerificationError(f"Notion verification failed: {error}") from None


def verify_layout(root: Path) -> None:
    """Require the executable, documentation, test, and report contract."""

    repository_root = Path(root)
    required = (
        "AGENTS.md",
        ".gitignore",
        "pyproject.toml",
        "verify.py",
        "config/wiki_claims.json",
        "scripts/setup.py",
        "scripts/01_fetch_wiki.py",
        "scripts/02_fetch_process.py",
        "scripts/03_build_delta.py",
        "scripts/04_prepare_notion.py",
        "src/delta/build.py",
        "src/delta/render.py",
        "src/delta/notion.py",
        "src/delta/notion_gate.py",
        "src/delta/notion_semantics.py",
        "tests/test_delta_builder.py",
        "tests/test_delta_render.py",
        "tests/test_prepare_notion.py",
        "tests/test_notion_publication_gate.py",
        "tests/test_script_entrypoints.py",
        "tests/test_verify.py",
        "docs/delta-method.md",
        "docs/decisions.md",
        "docs/notion-publication.md",
        "docs/session-2026-08-26.md",
        *(f"deltas/{slug}.md" for slug in FIXED_SLUGS),
    )
    missing = [
        relative
        for relative in required
        if not _is_nonempty_regular_file(repository_root / relative)
    ]
    if missing:
        raise VerificationError("required files are missing: " + ", ".join(missing))
    legacy = (
        "scripts/04_publish_notion.py",
        "tests/test_classify.py",
        "tests/test_render.py",
        "tests/test_evidence.py",
    )
    present = [relative for relative in legacy if (repository_root / relative).exists()]
    if present:
        raise VerificationError("legacy contract files remain: " + ", ".join(present))


def verify_python_modules(root: Path) -> None:
    """Reject syntax errors and Python files containing only a prose docstring."""

    repository_root = Path(root)
    for directory in ("src", "scripts"):
        for path in sorted((repository_root / directory).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeError, SyntaxError):
                raise VerificationError(
                    f"Python module is unreadable or invalid: {path.relative_to(repository_root)}"
                ) from None
            executable_nodes = [
                node
                for node in tree.body
                if not (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                )
            ]
            if not executable_nodes:
                raise VerificationError(
                    f"prose-only Python module: {path.relative_to(repository_root)}"
                )


def verify_documented_contract(root: Path) -> None:
    """Require the current status model and reject the retired heuristic model."""

    repository_root = Path(root)
    combined = "\n".join(
        (repository_root / relative).read_text(encoding="utf-8")
        for relative in ("AGENTS.md", "docs/delta-method.md")
    )
    for status in (
        "CONFIRMADO",
        "DIVERGENTE",
        "NAO_VERIFICAVEL_API_PROCESSO",
        "AMBIGUO",
    ):
        if status not in combined:
            raise VerificationError(f"documented status is missing: {status}")
    for retired in ("DOC_ONLY", "AZURE_ONLY", "MATCH"):
        if retired in combined:
            raise VerificationError(f"retired heuristic status remains: {retired}")


def verify_script_entrypoints(root: Path) -> None:
    """Prove every user-facing script can be invoked with one command."""

    repository_root = Path(root)
    for name in (
        "setup.py",
        "01_fetch_wiki.py",
        "02_fetch_process.py",
        "03_build_delta.py",
        "04_prepare_notion.py",
        "prepare_baselines.py",
        "run_audit.py",
    ):
        run_checked((sys.executable, f"scripts/{name}", "--help"), repository_root)


def verify_repository(root: Path, *, require_fetched: bool = False) -> None:
    """Run every non-mutating repository gate in dependency order."""

    repository_root = Path(root)
    verify_layout(repository_root)
    verify_gitignore(repository_root)
    verify_coverage_baselines(repository_root)
    verify_read_allowlist()
    verify_python_modules(repository_root)
    verify_documented_contract(repository_root)
    verify_secret_literals(repository_root)
    verify_reports(repository_root)
    verify_notion_artifacts(repository_root, require_fetched=require_fetched)
    verify_script_entrypoints(repository_root)
    run_checked(("uv", "run", "pytest", "-q"), repository_root)


def _load_secret_values(env_path: Path) -> tuple[bytes, ...]:
    sensitive_fragments = (
        "PAT",
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "CREDENTIAL",
        "API_KEY",
        "PRIVATE_KEY",
    )
    values: list[bytes] = []
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise VerificationError(".env is unreadable") from None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = key.strip().upper()
        cleaned = value.strip().strip("'\"")
        if any(fragment in normalized_key for fragment in sensitive_fragments):
            if cleaned:
                values.append(cleaned.encode("utf-8"))
    return tuple(dict.fromkeys(values))


def _tracked_files(root: Path) -> set[str]:
    if not (root / ".git").exists():
        return set()
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise VerificationError("git could not enumerate tracked files")
    try:
        return {
            item for item in completed.stdout.decode("utf-8").split("\0") if item
        }
    except UnicodeError:
        raise VerificationError("git returned non-UTF-8 tracked paths") from None


def _candidate_secret_scan_files(root: Path, tracked: Iterable[str]) -> tuple[Path, ...]:
    candidates = {
        root / relative
        for relative in tracked
        if relative != ".env" and not relative.startswith(".env.")
    }
    for relative in ("out", "deltas", "docs", "config", "scripts", "src", "tests"):
        directory = root / relative
        if directory.is_dir():
            candidates.update(directory.rglob("*"))
    for relative in ("AGENTS.md", "README.md", "verify.py", "pyproject.toml"):
        candidates.add(root / relative)
    return tuple(
        sorted(
            (
                path
                for path in candidates
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda path: path.as_posix(),
        )
    )


def _read_regular_file(path: Path, label: str) -> bytes:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow)
    except OSError:
        raise VerificationError(
            f"{label} must be a regular file: {path.name}"
        ) from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise VerificationError(
                f"{label} must be a regular file: {path.name}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _is_nonempty_regular_file(path: Path) -> bool:
    if path.is_symlink():
        return False
    try:
        metadata = path.stat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode) and metadata.st_size > 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the optional final-publication requirement."""

    parser = argparse.ArgumentParser(description="Verify the complete doc-azure audit.")
    parser.add_argument(
        "--require-publication",
        action="store_true",
        help="require exact connector-fetched receipts for all four Notion pages",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the gate and emit one stable completion marker."""

    arguments = parse_args(argv)
    try:
        verify_repository(
            PROJECT_ROOT,
            require_fetched=arguments.require_publication,
        )
    except (OSError, UnicodeError, VerificationError) as error:
        print(f"GATE_FAIL: {error}", file=sys.stderr)
        return 1
    print("GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
