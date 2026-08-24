"""Tests for typed claim evaluators and exact evidence pointers."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from delta.catalog import CheckSpec, ClaimSpec, DocumentaryClaim
from delta.evaluator import EvaluationError, evaluate_claim
from delta.evidence import EvidenceError
from delta.models import FindingStatus
from doc_azure.snapshot import SnapshotWriter


PROCESS_ID = "9b6f2d8e-8d31-4f26-a781-8e2a9e9a0f47"
OTHER_PROCESS_ID = "7a35dc12-6ca5-4358-9afe-a9aeb9540171"
USER_STORY = "Custom.UserStory"
EPIC = "Microsoft.VSTS.WorkItemTypes.Epic"
WIKI_TEXT = "# Wiki\nCampo Bloqueado\nHistórico do campo\nWITs ativos\n"
COLLECTED_AT = datetime(2026, 8, 24, tzinfo=timezone.utc)


def seed_evidence(
    root: Path,
    *,
    process_type_id: str = PROCESS_ID,
    map_process_id: str = PROCESS_ID,
) -> None:
    wiki = SnapshotWriter(root / "out" / "wiki")
    wiki.write_text("leiame.md", WIKI_TEXT)
    wiki.commit_manifest(collected_at=COLLECTED_AT, requests=())

    process = SnapshotWriter(root / "out" / "process")
    process.write_json(
        "process.json",
        {"name": "Processo-Agil", "typeId": process_type_id},
    )
    process.write_json(
        "artifact-map.json",
        {
            "schema_version": 1,
            "process_name": "Processo-Agil",
            "process_id": map_process_id,
            "globals": {
                "processes": "processes.json",
                "process": "process.json",
                "work_item_types": "workitemtypes.json",
                "process_behaviors": "behaviors.json",
            },
            "work_item_types": [
                {
                    "name": "Epic",
                    "reference_name": EPIC,
                    "customization": "system",
                    "is_disabled": True,
                    "artifacts": _artifact_paths(EPIC),
                },
                {
                    "name": "História de Usuário",
                    "reference_name": USER_STORY,
                    "customization": "custom",
                    "is_disabled": False,
                    "artifacts": _artifact_paths(USER_STORY),
                },
            ],
        },
    )
    process.write_json(
        "behaviors.json",
        {
            "count": 1,
            "value": [
                {"referenceName": "System.RequirementBacklogBehavior", "rank": 20}
            ],
        },
    )
    process.write_json(
        f"workitemtypes/{USER_STORY}/fields.json",
        {
            "count": 2,
            "value": [
                {
                    "referenceName": "Custom.Bloqueado",
                    "name": "Bloqueado",
                    "required": True,
                },
                {
                    "referenceName": "Custom.Optional",
                    "name": "Opcional",
                },
            ],
        },
    )
    process.write_json(
        f"workitemtypes/{USER_STORY}/states.json",
        {
            "count": 2,
            "value": [
                {"name": "Backlog", "stateCategory": "Proposed"},
                {"name": "Concluído", "stateCategory": "Completed"},
            ],
        },
    )
    process.write_json(
        f"workitemtypes/{USER_STORY}/rules.json",
        {"count": 1, "value": [{"name": "Require blocked reason"}]},
    )
    process.write_json(
        f"workitemtypes/{USER_STORY}/layout.json",
        {
            "pages": [
                {
                    "sections": [
                        {
                            "groups": [
                                {
                                    "controls": [
                                        {"id": "Custom.Bloqueado", "label": "Bloqueado"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    )
    process.commit_manifest(collected_at=COLLECTED_AT, requests=())


def _artifact_paths(reference_name: str) -> dict[str, str]:
    return {
        kind: f"workitemtypes/{reference_name}/{kind}.json"
        for kind in ("fields", "states", "rules", "layout", "behaviors")
    }


def make_claim(kind: str, **parameters: object) -> ClaimSpec:
    digest = hashlib.sha256(WIKI_TEXT.encode("utf-8")).hexdigest()
    return ClaimSpec(
        id=f"35-{kind.upper()}-001",
        page_id=35,
        slug="leiame",
        finding="Alegação material",
        doc=DocumentaryClaim(
            path="out/wiki/leiame.md",
            line=2,
            excerpt="Campo Bloqueado",
            sha256=digest,
            value=str(parameters.pop("documented", "presente")),
        ),
        check=CheckSpec(kind=kind, parameters=parameters),
        limit="A divergência altera o contrato documentado.",
    )


def test_field_presence_returns_exact_field_pointer(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_presence",
        wit=USER_STORY,
        field="Custom.Bloqueado",
        expected=True,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.path == (
        f"out/process/workitemtypes/{USER_STORY}/fields.json"
    )
    assert finding.azure_evidence.selector == "/value/0/referenceName"


def test_historical_claim_is_not_proven_by_current_field_presence(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "limitation",
        documented="adicionado em 2026",
        implemented="A API expõe apenas o estado atual.",
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.NAO_VERIFICAVEL_API_PROCESSO
    assert finding.azure_evidence is None


def test_active_wit_set_excludes_disabled_work_item_types(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "active_wit_set",
        expected=[USER_STORY],
        identity="reference_name",
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.selector == "/work_item_types"
    assert EPIC not in finding.implemented


def test_wit_presence_returns_the_exact_reference_pointer(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "wit_presence",
        wit=USER_STORY,
        expected=True,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.selector == (
        "/work_item_types/1/reference_name"
    )


def test_wrong_wit_fails_closed_instead_of_searching_another_artifact(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_presence",
        wit="Custom.DoesNotExist",
        field="Custom.Bloqueado",
        expected=True,
    )

    with pytest.raises(EvaluationError, match="Custom.DoesNotExist"):
        evaluate_claim(claim, tmp_path)


def test_state_presence_returns_the_exact_state_name_pointer(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "state_presence",
        wit=USER_STORY,
        state="Concluído",
        expected=True,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.selector == "/value/1/name"


def test_field_required_uses_exact_boolean_or_reports_ambiguity(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    required = make_claim(
        "field_required",
        wit=USER_STORY,
        field="Custom.Bloqueado",
        expected=True,
    )
    undeclared = make_claim(
        "field_required",
        wit=USER_STORY,
        field="Custom.Optional",
        expected=True,
    )

    required_finding = evaluate_claim(required, tmp_path)
    undeclared_finding = evaluate_claim(undeclared, tmp_path)

    assert required_finding.status is FindingStatus.CONFIRMADO
    assert required_finding.azure_evidence is not None
    assert required_finding.azure_evidence.selector == "/value/0/required"
    assert undeclared_finding.status is FindingStatus.AMBIGUO
    assert undeclared_finding.azure_evidence is not None
    assert undeclared_finding.azure_evidence.selector == "/value/1"


@pytest.mark.parametrize(
    ("kind", "parameters", "selector"),
    (
        (
            "equals",
            {"artifact": "process.json", "pointer": "/name", "expected": "Processo-Agil"},
            "/name",
        ),
        (
            "count_equals",
            {"wit": USER_STORY, "family": "states", "expected": 2},
            "/count",
        ),
        (
            "rule_count",
            {"wit": USER_STORY, "expected": 1},
            "/count",
        ),
        (
            "layout_control",
            {"wit": USER_STORY, "control": "Custom.Bloqueado", "expected": True},
            "/pages/0/sections/0/groups/0/controls/0/id",
        ),
        (
            "behavior_rank",
            {"behavior": "System.RequirementBacklogBehavior", "expected": 20},
            "/value/0/rank",
        ),
    ),
)
def test_typed_evaluators_target_the_exact_proving_value(
    tmp_path: Path,
    kind: str,
    parameters: dict[str, object],
    selector: str,
) -> None:
    seed_evidence(tmp_path)

    finding = evaluate_claim(make_claim(kind, **parameters), tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.selector == selector


def test_equals_does_not_equate_boolean_and_integer(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    process_root = tmp_path / "out" / "process"
    replacement = SnapshotWriter(process_root)
    replacement.write_json("process.json", {"isEnabled": True})
    replacement.commit_manifest(collected_at=COLLECTED_AT, requests=())
    claim = make_claim(
        "equals",
        artifact="process.json",
        pointer="/isEnabled",
        expected=1,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.DIVERGENTE


def test_active_wit_set_rejects_incomplete_artifact_map(tmp_path: Path) -> None:
    wiki = SnapshotWriter(tmp_path / "out" / "wiki")
    wiki.write_text("leiame.md", WIKI_TEXT)
    wiki.commit_manifest(collected_at=COLLECTED_AT, requests=())
    process = SnapshotWriter(tmp_path / "out" / "process")
    process.write_json(
        "artifact-map.json",
        {
            "globals": {},
            "work_item_types": [
                {
                    "name": "História de Usuário",
                    "reference_name": USER_STORY,
                    "customization": "custom",
                    "is_disabled": False,
                    "artifacts": {},
                }
            ],
        },
    )
    process.commit_manifest(collected_at=COLLECTED_AT, requests=())
    claim = make_claim(
        "active_wit_set",
        expected=[USER_STORY],
        identity="reference_name",
    )

    with pytest.raises(EvaluationError, match="schema"):
        evaluate_claim(claim, tmp_path)


def test_artifact_map_identity_must_match_process_artifact(tmp_path: Path) -> None:
    seed_evidence(
        tmp_path,
        process_type_id=OTHER_PROCESS_ID,
        map_process_id=PROCESS_ID,
    )
    claim = make_claim(
        "active_wit_set",
        expected=[USER_STORY],
        identity="reference_name",
    )

    with pytest.raises(EvaluationError, match="identity"):
        evaluate_claim(claim, tmp_path)


def test_exact_document_hash_and_excerpt_are_required(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_presence",
        wit=USER_STORY,
        field="Custom.Bloqueado",
        expected=True,
    )
    claim = replace(
        claim,
        doc=replace(claim.doc, excerpt="linha próxima, mas incorreta"),
    )

    with pytest.raises(EvidenceError, match="exact excerpt"):
        evaluate_claim(claim, tmp_path)
