# Processo-Agil Wiki Delta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a reproducible, read-only Azure DevOps audit that compares four wiki pages with the current `Processo-Agil` definition, writes four local delta reports, and publishes four sibling pages under one Notion hub.

**Architecture:** A standard-library Python package will fetch only allowlisted read operations, normalize Azure responses, evaluate an explicit catalog of wiki claims, and render deterministic Markdown. Raw snapshots remain ignored under `out/`; curated reports and methodology remain versionable under `docs/audit/`. Notion publishing uses the authenticated connector after local verification, so no Notion secret enters the repository.

**Tech Stack:** Python 3.13 standard library, `unittest`, Azure DevOps REST API 7.1, Notion connector.

**Spec:** `docs/superpowers/specs/2026-08-21-processo-agil-wiki-delta-design.md`

## Global Constraints

- Azure DevOps organization is exactly `bancodonordeste`.
- Process is selected by exact name `Processo-Agil`; its expected current ID is `9d82e632-9028-4a6b-86f8-3edb3281cb15`.
- Wiki ID is `87014e24-4977-4d27-8e12-c05208008d95`; page IDs are exactly `35`, `10`, `9`, and `37`.
- Azure operations must be semantically read-only and present in the method-route allowlist.
- Allowed optional POSTs are WIQL execution and work-item batch retrieval only; no Azure `POST` creation, `PUT`, `PATCH`, `DELETE`, or method override.
- Computer Use is a last resort only when documented REST reads cannot resolve a material question.
- Never print, persist, or include `AZDO_PAT` in exceptions, logs, snapshots, docs, or tests.
- Use only the Python standard library; do not add runtime or test dependencies.
- Existing files are user-owned. Do not commit, stage, push, branch, rebase, or publish Git history without separate authorization.
- Every behavior change follows RED → GREEN → REFACTOR, and each RED failure must be observed before implementation.
- The four Notion delta pages must be direct children of the same hub page under the existing `Azure` page.

---

## File Map

| Path | Responsibility |
|---|---|
| `.gitignore` | Exclude secrets, credentials, caches, virtualenvs, builds, logs, local databases, editor/OS files, and generated output. |
| `pyproject.toml` | Declare Python 3.13 package metadata without dependencies. |
| `README.md` | One-screen quick start, commands, output locations, safety boundary. |
| `src/doc_azure/__init__.py` | Package marker and public version only. |
| `src/doc_azure/settings.py` | Safe `.env` parsing, immutable settings, idempotent runtime directory setup. |
| `src/doc_azure/azure_client.py` | Method-route allowlist, authenticated JSON requests, safe errors and response metadata. |
| `src/doc_azure/collector.py` | Discover wiki/process and collect raw plus normalized evidence. |
| `src/doc_azure/models.py` | Finding status and immutable finding/result structures. |
| `src/doc_azure/claims.py` | Load, validate and evaluate the explicit claim catalog. |
| `src/doc_azure/renderer.py` | Render inventory and four deterministic Markdown delta reports. |
| `src/doc_azure/audit.py` | Orchestrate fixture or live collection, comparison and atomic writes. |
| `src/doc_azure/verification.py` | Inspect required artifacts and scan versionable content safely. |
| `config/wiki_claims.json` | Auditable source excerpts, expected facts, check kinds and manual limitations. |
| `scripts/setup.py` | Single-command, idempotent setup and environment validation. |
| `scripts/run_audit.py` | Single-command live collection, comparison and report generation. |
| `scripts/verify.py` | Single-command offline tests, compilation and artifact/security checks. |
| `tests/test_settings.py` | Environment and idempotent setup behavior. |
| `tests/test_azure_client.py` | Semantic read-only boundary and safe HTTP behavior. |
| `tests/test_collector.py` | Exact discovery, collection and WIT grouping. |
| `tests/test_claims.py` | Claim classification, source drift and evidence rendering. |
| `tests/test_renderer.py` | Four-page separation and deterministic Markdown. |
| `tests/test_run_audit.py` | End-to-end local fixture execution. |
| `tests/fixtures/` | Minimal complete Azure responses used only by tests. |
| `docs/audit/README.md` | Work performed, result index and reproduction path. |
| `docs/audit/methodology.md` | Evidence model, read-only method semantics and limitations. |
| `docs/audit/decisions.md` | Decisions, reasons and rejected alternatives. |
| `docs/audit/delta-page-35-readme.md` | Delta for Wiki page 35. |
| `docs/audit/delta-page-10-template-politicas.md` | Delta for Wiki page 10. |
| `docs/audit/delta-page-9-changelog.md` | Delta for Wiki page 9. |
| `docs/audit/delta-page-37-apendice-tecnico.md` | Delta for Wiki page 37. |
| `docs/audit/session-log.md` | Commands, RED/GREEN evidence, collection time, Notion receipts and remaining uncertainty. |

---

### Task 1: Safe project foundation and idempotent setup

**Files:**
- Modify: `.gitignore`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Create: `src/doc_azure/__init__.py`
- Create: `src/doc_azure/settings.py`
- Create: `scripts/setup.py`
- Create: `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings.load(project_root: Path) -> Settings`
- Produces: `ensure_runtime_directories(project_root: Path) -> tuple[Path, ...]`
- `Settings` fields: `organization`, `project`, `wiki_id`, `page_ids`, `process_name`, `process_id`, `api_version`, `pat`, `output_root`.

- [ ] **Step 1: Write failing settings and setup tests**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from doc_azure.settings import Settings, ensure_runtime_directories


class SettingsTests(TestCase):
    def test_load_reads_pat_without_exposing_it_in_repr(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("AZDO_PAT=secret-value\n", encoding="utf-8")

            settings = Settings.load(root)

            self.assertEqual(settings.pat, "secret-value")
            self.assertNotIn("secret-value", repr(settings))

    def test_setup_is_idempotent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            first = ensure_runtime_directories(root)
            second = ensure_runtime_directories(root)

            self.assertEqual(first, second)
            self.assertTrue(all(path.is_dir() for path in second))
```

- [ ] **Step 2: Run the focused tests and observe RED**

Run: `PYTHONPATH=src python -m unittest tests.test_settings -v`  
Expected: import failure for missing `doc_azure.settings`.

- [ ] **Step 3: Implement immutable settings and idempotent setup**

Use a frozen dataclass. Parse only simple `KEY=VALUE` lines, ignore comments and
blank lines, strip matching single/double quotes, and let an existing process
environment variable override `.env`. Raise `SettingsError("AZDO_PAT is required; add it to .env or the environment")` without including the value.

```python
@dataclass(frozen=True, repr=False)
class Settings:
    organization: str
    project: str
    wiki_id: str
    page_ids: tuple[int, ...]
    process_name: str
    process_id: str
    api_version: str
    pat: str
    output_root: Path

    @classmethod
    def load(cls, project_root: Path) -> "Settings":
        file_values: dict[str, str] = {}
        env_path = project_root / ".env"
        if env_path.exists():
            for line_number, raw_line in enumerate(
                env_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    raise SettingsError(f"Invalid .env entry on line {line_number}")
                key, value = (part.strip() for part in line.split("=", 1))
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                file_values[key] = value
        pat = os.environ.get("AZDO_PAT") or file_values.get("AZDO_PAT")
        if not pat:
            raise SettingsError(
                "AZDO_PAT is required; add it to .env or the environment"
            )
        return cls(
            organization="bancodonordeste",
            project="Torre CCR - Concessão de Crédito",
            wiki_id="87014e24-4977-4d27-8e12-c05208008d95",
            page_ids=(35, 10, 9, 37),
            process_name="Processo-Agil",
            process_id="9d82e632-9028-4a6b-86f8-3edb3281cb15",
            api_version="7.1",
            pat=pat,
            output_root=project_root / "out",
        )

    def __repr__(self) -> str:
        return (
            "Settings(organization='bancodonordeste', "
            "process_name='Processo-Agil', pat='<redacted>')"
        )


def ensure_runtime_directories(project_root: Path) -> tuple[Path, ...]:
    paths = (
        project_root / "out" / "raw",
        project_root / "out" / "normalized",
        project_root / "out" / "reports",
        project_root / "out" / "notion",
    )
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths
```

Make `scripts/setup.py` add `src/` to `sys.path`, call both interfaces, and print only directory paths plus `Configuration OK`.

- [ ] **Step 4: Expand `.gitignore` by requested category**

Include at minimum:

```gitignore
# Secrets and credentials
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
*credentials*.json
*credentials*.yaml
*credentials*.yml
*token*.json
*token*.txt

# Python caches and virtual environments
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.venv/
venv/
env/

# Builds and generated artifacts
build/
dist/
*.egg-info/
out/

# Logs and local databases
*.log
logs/
*.db
*.sqlite
*.sqlite3

# Editors and operating systems
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp
*.swo
```

- [ ] **Step 5: Verify GREEN and setup idempotence**

Run: `PYTHONPATH=src python -m unittest tests.test_settings -v`  
Expected: both tests pass.

Run twice: `python scripts/setup.py`  
Expected: both runs exit 0, print the same directories, and never print the PAT.

- [ ] **Step 6: Review scope and Git state**

Run: `git diff -- .gitignore pyproject.toml README.md src/doc_azure/settings.py scripts/setup.py tests/test_settings.py`  
Expected: only foundation changes; no secret values.

Do not commit because no commit permission was given.

---

### Task 2: Semantically read-only Azure REST client

**Files:**
- Create: `src/doc_azure/azure_client.py`
- Create: `tests/test_azure_client.py`

**Interfaces:**
- Produces: `ReadOperation(method: str, path_pattern: Pattern[str])`
- Produces: `is_allowlisted_read(method: str, path: str) -> bool`
- Produces: `AzureClient.request_json(method: str, path: str, *, query: Mapping[str, str] | None = None, body: Mapping[str, object] | None = None) -> ApiResponse`
- Produces: `ApiResponse(payload: Mapping[str, object], headers: Mapping[str, str], url: str)`

- [ ] **Step 1: Write failing allowlist and redaction tests**

```python
class ReadOnlyBoundaryTests(TestCase):
    def test_allows_get_process_metadata(self):
        self.assertTrue(
            is_allowlisted_read(
                "GET",
                "/_apis/work/processes/process-id/workitemtypes",
            )
        )

    def test_allows_documented_post_queries(self):
        self.assertTrue(is_allowlisted_read("POST", "/project/_apis/wit/wiql"))
        self.assertTrue(
            is_allowlisted_read("POST", "/project/_apis/wit/workitemsbatch")
        )

    def test_rejects_post_query_creation_and_mutating_verbs(self):
        self.assertFalse(is_allowlisted_read("POST", "/project/_apis/wit/queries"))
        for method in ("PUT", "PATCH", "DELETE"):
            self.assertFalse(is_allowlisted_read(method, "/_apis/work/processes/x"))

    def test_error_message_redacts_pat(self):
        def failing_transport(request, timeout):
            raise URLError("connection failed")

        client = AzureClient(
            "https://dev.azure.com/org",
            "top-secret",
            failing_transport,
        )
        with self.assertRaises(AzureReadError) as raised:
            client.request_json("GET", "/_apis/work/processes")
        self.assertNotIn("top-secret", str(raised.exception))
```

- [ ] **Step 2: Observe RED**

Run: `PYTHONPATH=src python -m unittest tests.test_azure_client -v`  
Expected: import failure for `doc_azure.azure_client`.

- [ ] **Step 3: Implement the smallest allowlisted client**

Allow GET routes only when their normalized path matches one of:

```text
^/[^/]+/_apis/wiki/wikis/[^/]+/pages(?:/[0-9]+)?$
^/_apis/work/processes(?:/.*)?$
^/[^/]+/_apis/wit/(?:wiql|workitemsbatch|workitems(?:/.*)?)$
^/_apis/wit/(?:wiql|workitemsbatch|workitems(?:/.*)?)$
```

Allow POST only when the normalized path ends exactly in
`/_apis/wit/wiql` or `/_apis/wit/workitemsbatch`. Always append
`api-version=7.1`; use `urllib.parse.urlencode`. Do not expose a general headers
argument and never send `X-HTTP-Method-Override`.

Use Basic auth with `base64.b64encode(f":{pat}".encode())` only inside request
construction. On errors, report method, sanitized URL, HTTP status and response
message capped at 500 characters; strip authorization-like strings.

- [ ] **Step 4: Verify GREEN and mutation boundary**

Run: `PYTHONPATH=src python -m unittest tests.test_azure_client -v`  
Expected: all tests pass.

Mutation check: temporarily change the WIQL suffix to `queries`; the POST allowlist test must fail. Restore and rerun GREEN.

---

### Task 3: Complete process and wiki collector

**Files:**
- Create: `src/doc_azure/collector.py`
- Create: `tests/test_collector.py`
- Create: `tests/fixtures/processes.json`
- Create: `tests/fixtures/work_item_types.json`
- Create: `tests/fixtures/behaviors.json`
- Create: `tests/fixtures/wiki_page_35.json`
- Create: `tests/fixtures/wit_states.json`
- Create: `tests/fixtures/wit_fields.json`
- Create: `tests/fixtures/wit_rules.json`
- Create: `tests/fixtures/wit_layout.json`
- Create: `tests/fixtures/wit_behaviors.json`

**Interfaces:**
- Consumes: `Settings`, `AzureClient.request_json`
- Produces: `find_exact_process(processes, name: str) -> Mapping[str, object]`
- Produces: `classify_work_item_types(wits, business_names) -> Mapping[str, list[Mapping[str, object]]]`
- Produces: `collect_audit_snapshot(client: AzureClient, settings: Settings) -> Mapping[str, object]`
- Produces snapshot keys: `collected_at`, `wiki`, `process`, `work_item_types`, `behaviors`, `evidence_urls`.

- [ ] **Step 1: Write failing collector tests**

```python
class ProcessDiscoveryTests(TestCase):
    BUSINESS_WITS = frozenset({
        "Objetivo Estratégico",
        "Resultado Chave",
        "Iniciativa",
        "Problema ou Oportunidade",
        "Hipótese de Solução",
        "História de Usuário",
        "Item Técnico",
        "Atendimento Expresso",
        "Incidente",
        "Kaizen",
        "Bug",
        "Tarefa",
    })

    @classmethod
    def setUpClass(cls):
        cls.wit_fixture = json.loads(
            (FIXTURES / "work_item_types.json").read_text(encoding="utf-8")
        )

    def test_exactly_one_process_is_required(self):
        process = find_exact_process(
            {"value": [{"name": "Processo-Agil", "typeId": "expected"}]},
            "Processo-Agil",
        )
        self.assertEqual(process["typeId"], "expected")

    def test_ambiguous_process_name_is_rejected(self):
        payload = {"value": [
            {"name": "Processo-Agil", "typeId": "one"},
            {"name": "Processo-Agil", "typeId": "two"},
        ]}
        with self.assertRaises(ProcessDiscoveryError):
            find_exact_process(payload, "Processo-Agil")

    def test_wits_are_grouped_without_counting_system_tests_as_business(self):
        grouped = classify_work_item_types(
            self.wit_fixture["value"],
            self.BUSINESS_WITS,
        )
        self.assertEqual(len(grouped["business_active"]), 12)
        self.assertEqual(
            [wit["name"] for wit in grouped["system_active"]],
            ["Test Case", "Test Plan", "Test Suite"],
        )
        self.assertIn("User Story", [wit["name"] for wit in grouped["disabled"]])
```

Add an integration-style fixture test asserting that each business WIT contains
`states`, `fields`, `rules`, `layout`, and `behaviors`, and that all four wiki
page IDs and SHA-256 fingerprints are present.

- [ ] **Step 2: Observe RED**

Run: `PYTHONPATH=src python -m unittest tests.test_collector -v`  
Expected: import failure for `doc_azure.collector`.

- [ ] **Step 3: Implement exact discovery and normalization**

Use the official WIT behavior-association route:

```text
/_apis/work/processes/{process_id}/workitemtypesbehaviors/{wit_ref}/behaviors
```

For each of the 12 business WITs collect:

```python
{
    "name": "História de Usuário",
    "reference_name": "Custom.bdf28a37-53f0-4d55-820b-2e86d5a2d3e4",
    "is_disabled": False,
    "customization": "custom",
    "description": "",
    "states": (
        {"name": "Backlog", "category": "Proposed", "order": 1},
        {"name": "Concluído", "category": "Completed", "order": 26},
    ),
    "fields": (
        {"name": "Bloqueado", "reference_name": "Custom.Bloqueado", "required": True},
    ),
    "rules": (
        {"name": "Motivo do Bloqueio", "is_disabled": False},
    ),
    "layout": {"pages": ()},
    "behaviors": (
        {"behavior": "System.RequirementBacklogBehavior", "is_default": True},
    ),
}
```

Sort WIT groups by casefolded name, states by numeric order, fields by reference
name, and rules by name then ID. Preserve full raw payloads separately in the
runner; do not mutate fixture or response mappings in place.

- [ ] **Step 4: Verify GREEN and endpoint completeness**

Run: `PYTHONPATH=src python -m unittest tests.test_collector -v`  
Expected: all tests pass.

Mutation check: make `isDisabled=true` count as active; the grouping test must
fail. Restore and rerun GREEN.

---

### Task 4: Explicit claim model and deterministic delta evaluation

**Files:**
- Create: `src/doc_azure/models.py`
- Create: `src/doc_azure/claims.py`
- Create: `tests/test_claims.py`

**Interfaces:**
- Consumes: normalized snapshot and `config/wiki_claims.json` records.
- Produces: `FindingStatus` values `CONFIRMADO`, `DIVERGENTE`, `NAO_VERIFICAVEL_API_PROCESSO`, `AMBIGUO`.
- Produces: `Finding(claim_id, page_id, status, statement, documented, implemented, evidence, rationale)`.
- Produces: `evaluate_claim(claim, snapshot, wiki_content) -> Finding`.
- Produces: `evaluate_catalog(catalog, snapshot) -> tuple[Finding, ...]`.

- [ ] **Step 1: Write failing evaluation tests**

```python
class ClaimEvaluationTests(TestCase):
    def test_equal_state_count_is_confirmed(self):
        finding = evaluate_claim(STATE_COUNT_CLAIM, SNAPSHOT, WIKI_CONTENT)
        self.assertEqual(finding.status, FindingStatus.CONFIRMADO)
        self.assertEqual(finding.implemented, "27")

    def test_wrong_rule_count_is_divergent(self):
        finding = evaluate_claim(RULE_COUNT_CLAIM, SNAPSHOT, WIKI_CONTENT)
        self.assertEqual(finding.status, FindingStatus.DIVERGENTE)
        self.assertEqual(finding.implemented, "42")

    def test_governance_claim_is_not_misreported_as_missing(self):
        finding = evaluate_claim(POLICY_CLAIM, SNAPSHOT, WIKI_CONTENT)
        self.assertEqual(
            finding.status,
            FindingStatus.NAO_VERIFICAVEL_API_PROCESSO,
        )

    def test_missing_source_excerpt_stops_stale_comparison(self):
        with self.assertRaises(SourceDriftError):
            evaluate_claim(STATE_COUNT_CLAIM, SNAPSHOT, "page changed")
```

- [ ] **Step 2: Observe RED**

Run: `PYTHONPATH=src python -m unittest tests.test_claims -v`  
Expected: imports fail for the missing models/evaluator.

- [ ] **Step 3: Implement domain-specific checks**

Support only these check kinds:

```text
process_property
business_wit_names
behavior_ranks
state_count
state_names_equal
state_contains
field_present
field_required_count
field_prefix_count
rule_count
layout_labels
manual_not_verifiable
manual_ambiguous
```

Do not implement JSONPath or arbitrary expression evaluation. Each evaluator
must format the observed value and cite the exact REST route recorded in the
snapshot. `manual_*` claims require a non-empty rationale and evidence-scope
explanation.

- [ ] **Step 4: Verify GREEN and status mutation coverage**

Run: `PYTHONPATH=src python -m unittest tests.test_claims -v`  
Expected: all tests pass.

Mutation checks: swap `CONFIRMADO` and `DIVERGENTE` comparison branches, then
remove the source excerpt check. Each mutation must cause a named test failure;
restore and rerun GREEN.

---

### Task 5: Four separate deterministic Markdown renderings

**Files:**
- Create: `src/doc_azure/renderer.py`
- Create: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `tuple[Finding, ...]`, snapshot metadata and page descriptors.
- Produces: `render_delta_page(page, findings, metadata) -> str`.
- Produces: `render_all_reports(findings, metadata) -> Mapping[int, str]`.
- Produces: `write_reports(reports, docs_root, generated_root) -> tuple[Path, ...]`.

- [ ] **Step 1: Write failing rendering tests**

```python
class ReportRenderingTests(TestCase):
    def test_each_page_receives_only_its_findings(self):
        reports = render_all_reports(FINDINGS, METADATA)
        self.assertEqual(set(reports), {35, 10, 9, 37})
        self.assertIn("p35-wits", reports[35])
        self.assertNotIn("p10-dor", reports[35])

    def test_report_contains_freshness_scope_and_all_statuses(self):
        report = render_delta_page(PAGE_37, FINDINGS_37, METADATA)
        for marker in (
            "Coleta UTC",
            "Escopo da evidência",
            "CONFIRMADO",
            "DIVERGENTE",
            "NAO_VERIFICAVEL_API_PROCESSO",
            "AMBIGUO",
        ):
            self.assertIn(marker, report)

    def test_rendering_is_deterministic(self):
        self.assertEqual(
            render_delta_page(PAGE_35, FINDINGS_35, METADATA),
            render_delta_page(PAGE_35, tuple(reversed(FINDINGS_35)), METADATA),
        )
```

- [ ] **Step 2: Observe RED**

Run: `PYTHONPATH=src python -m unittest tests.test_renderer -v`  
Expected: import failure for `doc_azure.renderer`.

- [ ] **Step 3: Implement concise report sections**

Render, in order:

```text
Resumo executivo
Escopo e fontes
Contagem por classificação
Achados (table: classe, afirmação, documentado, implementado, evidência)
Itens não verificáveis
Incertezas e limites
Reprodução
```

Sort findings by severity (`DIVERGENTE`, `AMBIGUO`,
`NAO_VERIFICAVEL_API_PROCESSO`, `CONFIRMADO`) then claim ID. Escape Markdown
table pipes and replace embedded newlines with `<br>`.

- [ ] **Step 4: Verify GREEN**

Run: `PYTHONPATH=src python -m unittest tests.test_renderer -v`  
Expected: all tests pass and generated text is stable.

---

### Task 6: Material claim catalog and one-command live audit

**Files:**
- Create: `config/wiki_claims.json`
- Create: `src/doc_azure/audit.py`
- Create: `scripts/run_audit.py`
- Create: `tests/test_run_audit.py`
- Create: `tests/fixtures/audit_bundle.json`
- Create: `docs/audit/methodology.md`
- Create: `docs/audit/decisions.md`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `run(project_root: Path, client: AzureClient | None = None, collected_at: datetime | None = None) -> AuditRunResult`.
- Produces: `run_fixture_audit(fixture_path: Path, output_root: Path, collected_at: datetime) -> AuditRunResult`.
- Produces: raw JSON under `out/raw`, normalized JSON under `out/normalized`, four generated copies under `out/reports`, and four curated docs under `docs/audit`.

- [ ] **Step 1: Write a failing fixture end-to-end test**

```python
class AuditRunTests(TestCase):
    def test_fixture_run_writes_exactly_four_distinct_reports(self):
        with TemporaryDirectory() as directory:
            result = run_fixture_audit(
                fixture_path=FIXTURES / "audit_bundle.json",
                output_root=Path(directory),
                collected_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
            )
            self.assertEqual(len(result.reports), 4)
            self.assertEqual(
                {path.name for path in result.reports},
                {
                    "delta-page-35-readme.md",
                    "delta-page-10-template-politicas.md",
                    "delta-page-9-changelog.md",
                    "delta-page-37-apendice-tecnico.md",
                },
            )
            self.assertGreater(result.status_counts["DIVERGENTE"], 0)
```

- [ ] **Step 2: Observe RED**

Run: `PYTHONPATH=src python -m unittest tests.test_run_audit -v`  
Expected: failure because the runner and catalog do not exist.

- [ ] **Step 3: Add the explicit material claims**

The catalog must include, at minimum, these independently identifiable claims:

```text
Page 35
p35-process-identity
p35-twelve-business-wits
p35-seven-ranked-backlogs
p35-hu-it-27-states
p35-ae-incident-15-vs-kaizen-14
p35-blocked-required-ten
p35-custom-fields-over-fifty
p35-entry-and-exit-fields
p35-daily-hours-script
p35-eleven-squads-migrated
p35-board-state-column-policy

Page 10
p10-problem-state-name-and-discarded
p10-hypothesis-discarded
p10-hu-it-flow
p10-incident-ae-state-order
p10-blocking-rules
p10-wip-limits
p10-dor-dod
p10-cadences-and-roles
p10-tags-convention
p10-metric-formulas
p10-parent-child-cardinality

Page 9
p9-nature-field
p9-stage-forecast-field
p9-rtc-status-field
p9-priority-fields
p9-ae-awaiting-development
p9-story-points-task
p9-rtc-request-two-three-scope
p9-coexecutors-one-two
p9-coexecutor-three
p9-state-removal-current-result
p9-incident-current-existence
p9-entry-field-and-rule-counts
p9-exit-field-scope
p9-daily-pipeline-history
p9-version-chronology
p9-baseline-wit-count

Page 37
p37-state-counts-all-wits
p37-bug-nine-not-eight
p37-ae-and-incident-fifteen-not-fourteen
p37-rule-count-hu-it
p37-rule-count-ae
p37-rule-count-incident
p37-rule-count-kaizen
p37-rule-count-hypothesis
p37-rule-count-bug-task
p37-visible-layout-fields
p37-coexecutor-layouts
p37-transition-field-vs-rule-distinction
```

Every record must contain `source_excerpt`. Manual claims must explicitly state
why process metadata cannot prove or refute them. Historical changelog claims
must distinguish “current state matches” from “change occurred in that version”.

- [ ] **Step 4: Implement the runner**

The runner must:

1. load settings and create directories;
2. collect all four pages and process facets;
3. atomically write raw and normalized JSON with sorted keys;
4. load/evaluate the catalog;
5. render and atomically write all four reports;
6. print only timestamps, counts and paths—never raw responses or secrets.

Use `tempfile.NamedTemporaryFile` in the destination directory followed by
`Path.replace` for atomic writes. A failed run must not leave a truncated
report.

- [ ] **Step 5: Document method and decisions**

`methodology.md` must document:

- API current-state authority and changelog temporal limitation;
- semantic read-only allowlist, including the two documented POST query routes;
- distinction between WIT definition, layout, board configuration, actual use,
  external pipeline and policy;
- four result statuses and why absence of representation is not divergence;
- exact official Microsoft Learn links from the design.

`decisions.md` must record the selected architecture and rejection of manual-only
comparison, raw-dump-only output, unrestricted language parsing, local Notion
tokens and premature Computer Use.

- [ ] **Step 6: Verify GREEN offline**

Run: `PYTHONPATH=src python -m unittest tests.test_run_audit -v`  
Expected: fixture run passes and writes four files.

Run: `PYTHONPATH=src python -m unittest discover -s tests -v`  
Expected: all tests pass.

- [ ] **Step 7: Run the live audit**

Run: `python scripts/run_audit.py`  
Expected: exit 0, four page reports, one raw snapshot, one normalized snapshot,
and no Computer Use because REST answered all required definitions.

Inspect the generated counts and manually reconcile every divergence against
the raw endpoint evidence before accepting the reports.

---

### Task 7: Human-readable handoff, Notion publication and final verification

**Files:**
- Create: `docs/audit/README.md`
- Create: `docs/audit/session-log.md`
- Modify: `README.md`
- Create: `src/doc_azure/verification.py`
- Create: `scripts/verify.py`

**Interfaces:**
- Consumes: four verified report files.
- Produces: Notion hub plus four direct child pages.
- Produces: `inspect_required_artifacts(project_root: Path) -> ArtifactInspection`.
- Produces: `verify.py` exit 0 only when offline tests, compilation, required files and safe tracked-content scan pass.

- [ ] **Step 1: Write the failing verifier test before the verifier**

Add to `tests/test_run_audit.py`:

```python
def test_required_handoff_files_are_reported_missing(self):
    with TemporaryDirectory() as directory:
        result = inspect_required_artifacts(Path(directory))
        self.assertFalse(result.ok)
        self.assertIn("docs/audit/README.md", result.missing)
```

Run: `PYTHONPATH=src python -m unittest tests.test_run_audit -v`  
Expected: fail because `inspect_required_artifacts` does not exist.

- [ ] **Step 2: Implement the verifier and handoff docs**

`scripts/verify.py` must execute with `subprocess.run(check=False)`:

```text
python -m unittest discover -s tests -v
python -m compileall -q src scripts
```

It must then check required file existence and scan versionable files obtained
from `git ls-files --cached --others --exclude-standard` for:

```text
AZDO_PAT=<non-placeholder value>
Authorization: Basic
Bearer <token-like value>
dev.azure.com URLs containing userinfo
```

The scan reports only file path, line number and pattern name, never matched
content. Exclude `.env` through Git ignore behavior rather than reading it.

`docs/audit/README.md` must link the four reports and explain the dominant
findings. `session-log.md` must record commands and observed RED/GREEN results,
live collection timestamp, Azure read methods used, and the fact that no Azure
mutation or Computer Use occurred.

- [ ] **Step 3: Run offline final verification**

Run: `python scripts/verify.py`  
Expected: all tests pass, compilation succeeds, all artifacts exist, and no
secret patterns are reported.

- [ ] **Step 4: Read the Notion enhanced Markdown specification**

Call Notion fetch with `id="notion://docs/enhanced-markdown-spec"`. Use only
syntax supported by that response; do not guess table/callout syntax.

- [ ] **Step 5: Create and verify the Notion hub**

Create one page under existing `Azure` page ID
`2a1412e0-8c26-803b-a988-dc619a396e45`:

```text
Auditoria Processo-Agil x Wiki — 2026-08-21
```

Its body must identify organization/process, collection timestamp, local
methodology, the four source wiki links and the four classifications. Fetch the
created hub and verify title plus parent before creating children.

- [ ] **Step 6: Create four sibling delta pages in one call**

Use the verified hub `page_id` as the common parent and create exactly:

```text
Delta — Leia-me Processo da Organização Única
Delta — Template de políticas explícitas
Delta — Changelog
Delta — Apêndice Técnico Processo Organização Única
```

Use the corresponding local report as each body, omitting any duplicate H1
title because the title is a Notion property.

- [ ] **Step 7: Read back all five Notion pages**

Fetch hub and all four children. Verify:

- every child has the same hub parent;
- each title is exact;
- each contains its source wiki URL, collection timestamp, summary, findings
  table and limitation section;
- no report content was truncated;
- page 35 content does not contain page 10-only claim IDs, and analogous
  cross-page contamination is absent.

Record the five verified Notion URLs in `docs/audit/session-log.md` using
`apply_patch`, then rerun `python scripts/verify.py`.

- [ ] **Step 8: Completion audit against the original request**

Run and inspect:

```text
git status --short
git diff --check
git check-ignore -v .env .DS_Store out/example.json .venv/example *.log *.sqlite3
python scripts/setup.py
python scripts/run_audit.py
python scripts/verify.py
```

Confirm one-by-one: four wikis read; process read via REST; every page has its
own local and Notion delta; all children share one location; `.gitignore`
covers every requested category; scripts are functional and single-command;
docs explain work, reasons, decisions and rejected alternatives; no Azure write
was made; no secret is versionable.

Do not commit or publish Git history without new authorization.
