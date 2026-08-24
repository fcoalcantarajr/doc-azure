"""Tests for the explicit, versioned wiki-claim catalog."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from delta.catalog import CatalogError, ClaimSpec, load_catalog


FIXTURE = Path(__file__).parent / "fixtures" / "audit" / "wiki_claims.json"
PRODUCTION_CATALOG = Path(__file__).parents[1] / "config" / "wiki_claims.json"


def load_payload() -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def write_catalog(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_catalog_preserves_order_and_builds_typed_claims() -> None:
    claims = load_catalog(FIXTURE)

    assert len(claims) == 1
    assert isinstance(claims[0], ClaimSpec)
    assert claims[0].id == "35-FIELD-001"
    assert claims[0].doc.path == "out/wiki/leiame.md"
    assert claims[0].check.kind == "field_presence"
    assert claims[0].check.parameters["field"] == "Custom.Bloqueado"


def test_catalog_rejects_duplicate_ids(tmp_path: Path) -> None:
    payload = load_payload()
    payload["claims"] = [
        *payload["claims"],  # type: ignore[list-item]
        copy.deepcopy(payload["claims"][0]),  # type: ignore[index]
    ]

    with pytest.raises(CatalogError, match="duplicate"):
        load_catalog(write_catalog(tmp_path, payload))


def test_catalog_rejects_unsupported_check_kind(tmp_path: Path) -> None:
    payload = load_payload()
    payload["claims"][0]["check"]["kind"] = "keyword_search"  # type: ignore[index]

    with pytest.raises(CatalogError, match="unsupported"):
        load_catalog(write_catalog(tmp_path, payload))


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda claim: claim.update(slug="changelog"), "page_id"),
        (
            lambda claim: claim["doc"].update(path="out/wiki/changelog.md"),
            "doc.path",
        ),
        (lambda claim: claim["doc"].update(sha256="not-a-hash"), "sha256"),
        (lambda claim: claim.update(limit=" "), "limit"),
    ),
)
def test_catalog_rejects_inconsistent_or_incomplete_claims(
    tmp_path: Path,
    mutation: object,
    message: str,
) -> None:
    payload = load_payload()
    claim = payload["claims"][0]  # type: ignore[index]
    mutation(claim)  # type: ignore[operator]

    with pytest.raises(CatalogError, match=message):
        load_catalog(write_catalog(tmp_path, payload))


def test_catalog_allows_an_empty_limit_for_an_unqualified_confirmed_claim(
    tmp_path: Path,
) -> None:
    payload = load_payload()
    payload["claims"][0]["limit"] = ""  # type: ignore[index]

    claims = load_catalog(write_catalog(tmp_path, payload))

    assert claims[0].limit == ""


def test_catalog_supports_multiple_exact_fragments_from_one_page_hash(
    tmp_path: Path,
) -> None:
    payload = load_payload()
    claim = payload["claims"][0]  # type: ignore[index]
    second = copy.deepcopy(claim["doc"])
    second.update(line=3, excerpt="Histórico do campo")
    claim["doc"] = [claim["doc"], second]

    claims = load_catalog(write_catalog(tmp_path, payload))

    assert [document.line for document in claims[0].documents] == [2, 3]


def test_catalog_rejects_multiple_fragments_with_different_page_hashes(
    tmp_path: Path,
) -> None:
    payload = load_payload()
    claim = payload["claims"][0]  # type: ignore[index]
    second = copy.deepcopy(claim["doc"])
    second.update(line=3, excerpt="Histórico do campo", sha256="0" * 64)
    claim["doc"] = [claim["doc"], second]

    with pytest.raises(CatalogError, match="same page hash"):
        load_catalog(write_catalog(tmp_path, payload))


def test_catalog_rejects_missing_kind_specific_parameters(tmp_path: Path) -> None:
    payload = load_payload()
    del payload["claims"][0]["check"]["field"]  # type: ignore[index]

    with pytest.raises(CatalogError, match="field"):
        load_catalog(write_catalog(tmp_path, payload))


def test_catalog_rejects_count_family_without_an_envelope(tmp_path: Path) -> None:
    payload = load_payload()
    payload["claims"][0]["check"] = {  # type: ignore[index]
        "kind": "count_equals",
        "wit": "Custom.UserStory",
        "family": "layout",
        "expected": 1,
    }

    with pytest.raises(CatalogError, match="family"):
        load_catalog(write_catalog(tmp_path, payload))


def test_catalog_rejects_malformed_active_wit_customization_filter(
    tmp_path: Path,
) -> None:
    payload = load_payload()
    payload["claims"][0]["check"] = {  # type: ignore[index]
        "kind": "active_wit_set",
        "identity": "reference_name",
        "expected": ["Custom.UserStory"],
        "exclude_customizations": ["system", "system"],
    }

    with pytest.raises(CatalogError, match="exclude_customizations"):
        load_catalog(write_catalog(tmp_path, payload))


def test_production_catalog_covers_all_fixed_pages_and_material_checks() -> None:
    claims = load_catalog(PRODUCTION_CATALOG)

    assert len(claims) >= 111
    assert {(claim.page_id, claim.slug) for claim in claims} == {
        (9, "changelog"),
        (10, "politicas"),
        (35, "leiame"),
        (37, "apendice"),
    }
    assert {claim.check.kind for claim in claims} == {
        "active_required_field_count",
        "active_wit_set",
        "ambiguous",
        "count_equals",
        "equals",
        "field_presence",
        "field_property",
        "field_required",
        "layout_control",
        "layout_control_order",
        "limitation",
        "rule_count",
        "rule_action",
        "rule_presence",
        "state_presence",
        "state_property",
        "state_sequence",
        "technical_context",
        "transition_field_coverage",
        "unique_custom_field_minimum",
        "wit_state_set_equal",
        "wit_presence",
    }
    identifiers = {claim.id for claim in claims}
    assert sum(identifier.startswith("10-POLICY-") for identifier in identifiers) == 18
    assert {f"37-STATE-{index:03d}" for index in range(1, 13)} <= identifiers
    assert {f"37-RULE-{index:03d}" for index in range(1, 13)} <= identifiers
    assert {
        "9-RTC-001",
        "9-RTC-002",
        "9-ORIGINAL-001",
        "9-ORIGINAL-002",
        "9-ORIGINAL-003",
        "9-COMPLETED-001",
        "9-WIT-INCIDENTE-001",
        "9-EXIT-EXAMPLE-001",
        "9-ENTRY-EXAMPLE-001",
        "9-DEPLOY-HML-001",
        "9-DEPLOY-HML-002",
    } <= identifiers
    assert {
        "35-WITS-001",
        "35-BLOCK-001",
        "35-FIELDS-001",
        "35-FIELDS-002",
        "10-STATE-PO-001",
        "10-STATE-HS-001",
        "10-STATE-HU-001",
        "10-STATE-IT-001",
        "10-STATE-AE-001",
        "10-STATE-INCIDENTE-001",
        "10-STATE-KAIZEN-001",
        "10-STATE-AE-INCIDENTE-001",
        "9-ENTRY-COVERAGE-HU-001",
        "9-EXIT-COVERAGE-HU-001",
        "9-ENTRY-AE-COPY-001",
        "9-STATECATEGORY-AE-001",
        "37-WITS-001",
        "37-FIELD-INITIATIVE-PERIOD-001",
        "37-FIELD-IT-ACCEPTANCE-001",
        "37-STATE-KAIZEN-AE-001",
        "37-RULE-AE-COPY-001",
        "37-BEHAVIOR-STRATEGIC-001",
    } <= identifiers
    assert not {
        "35-RULES-001",
        "35-STATE-001",
        "10-STATE-001",
        "9-RTC3-002",
        "9-RTC3-003",
        "9-ENTRY-COVERAGE-001",
        "9-EXIT-COVERAGE-001",
        "9-COEXEC-001",
        "9-COEXEC-002",
        "9-ORDER-001",
        "37-FIELDCOUNT-001",
        "37-FIELDCOUNT-002",
        "37-FIELDCOUNT-003",
        "37-LAYOUT-001",
        "37-LAYOUT-002",
        "37-LAYOUT-003",
        "37-LAYOUT-004",
        "37-LAYOUT-005",
        "37-LAYOUT-006",
        "37-LAYOUT-007",
    } & identifiers
