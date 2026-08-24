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
from doc_azure.process_collector import MAPPING_SCHEMA_VERSION


PROCESS_ID = "9b6f2d8e-8d31-4f26-a781-8e2a9e9a0f47"
OTHER_PROCESS_ID = "7a35dc12-6ca5-4358-9afe-a9aeb9540171"
USER_STORY = "Custom.UserStory"
EPIC = "Microsoft.VSTS.WorkItemTypes.Epic"
TEST_CASE = "Microsoft.VSTS.WorkItemTypes.TestCase"
WIKI_TEXT = "# Wiki\nCampo Bloqueado\nHistórico do campo\nWITs ativos\n"
COLLECTED_AT = datetime(2026, 8, 24, tzinfo=timezone.utc)


def _default_user_story_states() -> list[dict[str, object]]:
    return [
        {"name": "Backlog", "stateCategory": "Proposed", "order": 1},
        {"name": "Concluído", "stateCategory": "Completed", "order": 2},
    ]


def seed_evidence(
    root: Path,
    *,
    process_type_id: str = PROCESS_ID,
    map_process_id: str = PROCESS_ID,
    layout_payload: object | None = None,
    user_story_states: list[dict[str, object]] | None = None,
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
            "schema_version": MAPPING_SCHEMA_VERSION,
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
                {
                    "name": "Test Case",
                    "reference_name": TEST_CASE,
                    "customization": "system",
                    "is_disabled": False,
                    "artifacts": _artifact_paths(TEST_CASE),
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
            "count": 4,
            "value": [
                {
                    "referenceName": "Custom.Bloqueado",
                    "name": "Bloqueado",
                    "customization": "custom",
                    "required": True,
                },
                {
                    "referenceName": "Custom.Optional",
                    "name": "Opcional",
                    "customization": "custom",
                },
                {
                    "referenceName": "Custom.EntrouemEstadoBacklogDate",
                    "name": "Entrou em Estado Backlog Date",
                    "customization": "custom",
                },
                {
                    "referenceName": "Custom.EntrouemEstadoConcluidoDate",
                    "name": "Entrou em Estado Concluído Date",
                    "customization": "custom",
                },
            ],
        },
    )
    process.write_json(
        f"workitemtypes/{USER_STORY}/states.json",
        {
            "count": len(user_story_states or _default_user_story_states()),
            "value": user_story_states or _default_user_story_states(),
        },
    )
    process.write_json(
        f"workitemtypes/{USER_STORY}/rules.json",
        {
            "count": 1,
            "value": [
                {
                    "name": "Require blocked reason",
                    "conditions": [
                        {
                            "conditionType": "when",
                            "field": "System.State",
                            "value": "Backlog",
                        }
                    ],
                    "actions": [
                        {
                            "actionType": "copyFromField",
                            "targetField": "Custom.EntrouemEstadoBacklogDate",
                            "value": "Microsoft.VSTS.Common.StateChangeDate",
                        }
                    ],
                }
            ],
        },
    )
    process.write_json(
        f"workitemtypes/{EPIC}/states.json",
        {
            "count": 1,
            "value": [
                {"name": "Backlog", "stateCategory": "Proposed", "order": 1}
            ],
        },
    )
    process.write_json(
        f"workitemtypes/{TEST_CASE}/fields.json",
        {
            "count": 2,
            "value": [
                {
                    "referenceName": "Custom.Bloqueado",
                    "name": "Bloqueado",
                    "customization": "custom",
                },
                {
                    "referenceName": "Custom.TestOnly",
                    "name": "Somente Teste",
                    "customization": "custom",
                },
            ],
        },
    )
    process.write_json(
        f"workitemtypes/{USER_STORY}/layout.json",
        layout_payload
        if layout_payload is not None
        else {
            "name": "História de Usuário",
            "referenceName": USER_STORY,
            "layout": {
                "pages": [
                    {
                        "sections": [
                            {
                                "groups": [
                                    {
                                        "controls": [
                                            {
                                                "id": "Custom.Bloqueado",
                                                "label": "Bloqueado",
                                                "order": 0,
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
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


def test_confirmed_current_state_preserves_a_historical_qualification(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_presence",
        wit=USER_STORY,
        field="Custom.Bloqueado",
        expected=True,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.impact_or_limit == claim.limit


def test_compound_claim_verifies_and_returns_every_exact_document_fragment(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_presence",
        wit=USER_STORY,
        field="Custom.Bloqueado",
        expected=True,
    )
    claim = replace(
        claim,
        doc_fragments=(
            DocumentaryClaim(
                path="out/wiki/leiame.md",
                line=3,
                excerpt="Histórico do campo",
                sha256=claim.doc.sha256,
                value=claim.doc.value,
            ),
        ),
    )

    finding = evaluate_claim(claim, tmp_path)

    assert [pointer.selector for pointer in finding.doc_evidence] == ["L2", "L3"]


def test_compound_claim_fails_when_any_fragment_is_not_exact(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_presence",
        wit=USER_STORY,
        field="Custom.Bloqueado",
        expected=True,
    )
    claim = replace(
        claim,
        doc_fragments=(
            DocumentaryClaim(
                path="out/wiki/leiame.md",
                line=3,
                excerpt="linha próxima, mas incorreta",
                sha256=claim.doc.sha256,
                value=claim.doc.value,
            ),
        ),
    )

    with pytest.raises(EvidenceError, match="exact excerpt"):
        evaluate_claim(claim, tmp_path)


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
        exclude_customizations=["system"],
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.selector == "/work_item_types"
    assert f"ativos excluídos: {TEST_CASE}" in finding.implemented
    assert f"desabilitados: {EPIC}" in finding.implemented


def test_active_wit_set_includes_system_types_without_explicit_filter(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "active_wit_set",
        expected=[USER_STORY, TEST_CASE],
        identity="reference_name",
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO


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


def test_state_sequence_compares_api_order_as_one_documentary_claim(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    confirmed = make_claim(
        "state_sequence",
        wit=USER_STORY,
        expected=["Backlog", "Concluído"],
    )
    divergent = make_claim(
        "state_sequence",
        wit=USER_STORY,
        expected=["Concluído", "Backlog"],
    )

    confirmed_finding = evaluate_claim(confirmed, tmp_path)
    divergent_finding = evaluate_claim(divergent, tmp_path)

    assert confirmed_finding.status is FindingStatus.CONFIRMADO
    assert divergent_finding.status is FindingStatus.DIVERGENTE
    assert confirmed_finding.azure_evidence is not None
    assert confirmed_finding.azure_evidence.selector == "/value"


def test_state_sequence_rejects_duplicate_state_names(tmp_path: Path) -> None:
    seed_evidence(
        tmp_path,
        user_story_states=[
            {"name": "Backlog", "stateCategory": "Proposed", "order": 1},
            {"name": "Backlog", "stateCategory": "Completed", "order": 2},
        ],
    )
    claim = make_claim(
        "state_sequence",
        wit=USER_STORY,
        expected=["Backlog", "Concluído"],
    )

    with pytest.raises(EvaluationError, match="state name is not unique"):
        evaluate_claim(claim, tmp_path)


def test_wit_state_set_equality_does_not_collapse_sequence_or_membership(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "wit_state_set_equal",
        left_wit=USER_STORY,
        right_wit=EPIC,
        expected=True,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.DIVERGENTE
    assert "Concluído" in finding.implemented
    assert len(finding.azure_evidence) == 2


def test_exact_field_and_state_properties_return_value_pointers(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    field = make_claim(
        "field_property",
        wit=USER_STORY,
        field="Custom.Bloqueado",
        property="customization",
        expected="custom",
    )
    state = make_claim(
        "state_property",
        wit=USER_STORY,
        state="Backlog",
        property="stateCategory",
        expected="Proposed",
    )

    field_finding = evaluate_claim(field, tmp_path)
    state_finding = evaluate_claim(state, tmp_path)

    assert field_finding.status is FindingStatus.CONFIRMADO
    assert field_finding.azure_evidence.selector == "/value/0/customization"
    assert state_finding.status is FindingStatus.CONFIRMADO
    assert state_finding.azure_evidence.selector == "/value/0/stateCategory"


def test_technical_context_reports_an_exact_current_fact_without_claiming_semantics(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "technical_context",
        artifact="behaviors.json",
        pointer="/value/0/rank",
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.AMBIGUO
    assert finding.implemented == "20"
    assert finding.azure_evidence.selector == "/value/0/rank"


def test_transition_field_coverage_compares_every_current_named_state(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "transition_field_coverage",
        wit=USER_STORY,
        direction="entry",
        expected=True,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert "2 de 2" in finding.implemented
    assert len(finding.azure_evidence) == 2
    assert [pointer.selector for pointer in finding.azure_evidence] == [
        "/value",
        "/value",
    ]


def test_field_alternative_proves_expected_absence_and_actual_identity_and_name(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_alternative",
        wit=USER_STORY,
        expected_field="Custom.Documented",
        actual_field="Custom.Optional",
        actual_name="Opcional",
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.DIVERGENTE
    assert "Custom.Optional" in finding.implemented
    assert "Opcional" in finding.implemented
    assert [pointer.selector for pointer in finding.azure_evidence] == [
        "/value",
        "/value/1/referenceName",
        "/value/1/name",
    ]


def test_rule_action_matches_the_exact_condition_and_action(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "rule_action",
        wit=USER_STORY,
        condition_field="System.State",
        condition_value="Backlog",
        action_type="copyFromField",
        target_field="Custom.EntrouemEstadoBacklogDate",
        action_value="Microsoft.VSTS.Common.StateChangeDate",
        expected=True,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence.selector == "/value/0/actions/0"


def test_unique_custom_field_minimum_deduplicates_reference_names_across_wits(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "unique_custom_field_minimum",
        wits=[USER_STORY, TEST_CASE],
        expected_minimum=5,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.implemented.startswith("5 campos")
    assert len(finding.azure_evidence) == 2


def test_active_required_field_count_excludes_disabled_and_system_wits(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "active_required_field_count",
        field="Custom.Bloqueado",
        expected=2,
        exclude_customizations=["system"],
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.DIVERGENTE
    assert finding.implemented.startswith("1 WIT ativo")
    assert USER_STORY in finding.implemented
    assert EPIC not in finding.implemented
    assert TEST_CASE not in finding.implemented
    assert finding.azure_evidence is not None
    assert len(finding.azure_evidence) == 2
    assert finding.azure_evidence[0].selector == "/work_item_types"
    assert finding.azure_evidence[1].path.endswith(
        f"workitemtypes/{USER_STORY}/fields.json"
    )
    assert finding.azure_evidence[1].selector.endswith("/required")


def test_field_name_pattern_minimum_reports_exact_matching_count(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "field_name_pattern_minimum",
        wit=USER_STORY,
        prefix="Entrou em Estado ",
        suffix=" Date",
        expected_minimum=3,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.DIVERGENTE
    assert finding.implemented.startswith("2 campos")
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.selector == "/value"


def test_rule_presence_and_layout_order_return_exact_pointers(
    tmp_path: Path,
) -> None:
    seed_evidence(tmp_path)
    rule = make_claim(
        "rule_presence",
        wit=USER_STORY,
        rule="Require blocked reason",
        expected=True,
    )
    order = make_claim(
        "layout_control_order",
        wit=USER_STORY,
        control="Custom.Bloqueado",
        expected=0,
    )

    rule_finding = evaluate_claim(rule, tmp_path)
    order_finding = evaluate_claim(order, tmp_path)

    assert rule_finding.status is FindingStatus.CONFIRMADO
    assert rule_finding.azure_evidence is not None
    assert rule_finding.azure_evidence.selector == "/value/0/name"
    assert order_finding.status is FindingStatus.CONFIRMADO
    assert order_finding.azure_evidence is not None
    assert order_finding.azure_evidence.selector.endswith("/controls/0/order")


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
            "/layout/pages/0/sections/0/groups/0/controls/0/id",
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


def test_layout_control_absence_points_to_expanded_pages(tmp_path: Path) -> None:
    seed_evidence(tmp_path)
    claim = make_claim(
        "layout_control",
        wit=USER_STORY,
        control="Custom.DoesNotExist",
        expected=False,
    )

    finding = evaluate_claim(claim, tmp_path)

    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence is not None
    assert finding.azure_evidence.selector == "/layout/pages"


@pytest.mark.parametrize(
    "layout_payload",
    (
        {"referenceName": USER_STORY},
        {"referenceName": "Custom.Wrong", "layout": {"pages": []}},
        {"referenceName": USER_STORY, "layout": []},
    ),
)
def test_layout_control_rejects_malformed_expanded_response(
    tmp_path: Path,
    layout_payload: dict[str, object],
) -> None:
    seed_evidence(tmp_path, layout_payload=layout_payload)
    claim = make_claim(
        "layout_control",
        wit=USER_STORY,
        control="Custom.Bloqueado",
        expected=True,
    )

    with pytest.raises(EvaluationError, match="layout"):
        evaluate_claim(claim, tmp_path)


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
