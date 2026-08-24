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
        "active_wit_set",
        "ambiguous",
        "count_equals",
        "equals",
        "field_presence",
        "field_required",
        "layout_control",
        "limitation",
        "rule_count",
        "state_presence",
        "wit_presence",
    }
    identifiers = {claim.id for claim in claims}
    assert sum(identifier.startswith("10-POLICY-") for identifier in identifiers) == 18
    assert sum(identifier.startswith("37-STATE-") for identifier in identifiers) == 12
    assert sum(identifier.startswith("37-RULE-") for identifier in identifiers) == 12
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
