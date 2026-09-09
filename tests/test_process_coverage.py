"""Inventory changes outside known assertions must remain observable."""

import pytest

from delta import process_coverage


def test_new_removed_and_changed_properties_have_exact_pointers():
    old = process_coverage.fingerprint_json({"fields": [{"name": "A", "required": False}]})
    new = process_coverage.fingerprint_json({"fields": [{"name": "B", "type": "string"}]})
    changes = process_coverage.compare_inventory(old, new)
    assert [(change.pointer, change.kind) for change in changes] == [
        ("/fields/0/name", "changed"),
        ("/fields/0/required", "removed"),
        ("/fields/0/type", "added"),
    ]


def test_object_order_is_cosmetic_but_array_order_is_preserved():
    assert process_coverage.fingerprint_json({"a": 1, "b": 2}) == process_coverage.fingerprint_json({"b": 2, "a": 1})
    assert process_coverage.fingerprint_json([1, 2]) != process_coverage.fingerprint_json([2, 1])


@pytest.mark.parametrize("first,second", [(True, 1), (1, "1"), (None, "null"), ({}, []), ([{}], []), ({"x": []}, {})])
def test_types_and_empty_structures_are_not_lost(first, second):
    assert process_coverage.compare_inventory(
        process_coverage.fingerprint_json(first), process_coverage.fingerprint_json(second)
    )


def test_pointer_escaping_is_unambiguous():
    result = process_coverage.fingerprint_json({"a/b~c": 1})
    assert "/a~1b~0c" in result


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "invalid"}, ("tuple",)])
def test_non_json_inputs_fail_closed(value):
    with pytest.raises(ValueError):
        process_coverage.fingerprint_json(value)


@pytest.mark.parametrize("value", [{}, {"": "bad"}, {"bad-pointer": "0" * 64}])
def test_invalid_baseline_is_not_treated_as_clean(value):
    with pytest.raises(ValueError, match="inventory"):
        process_coverage.compare_inventory(value, {"": "0" * 64})
