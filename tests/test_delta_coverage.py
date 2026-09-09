"""Unknown documentary prose must remain visible rather than be classified."""

import pytest

from delta import coverage


def test_changed_requirement_reports_exact_current_excerpt():
    changes = coverage.compare_document(
        "leiame", coverage.document_fingerprint(b"Required: yes\n"), b"Required: no\n"
    )
    assert len(changes) == 1
    assert changes[0].kind == "replace"
    assert changes[0].slug == "leiame"
    assert changes[0].current_start_line == 1
    assert changes[0].current_lines == ("Required: no",)
    assert changes[0].status == "UNMAPPED_DOC_CHANGE"


def test_crlf_is_cosmetic_but_hard_break_spaces_are_not():
    baseline = coverage.document_fingerprint(b"first\nsecond\n")
    assert coverage.compare_document("leiame", baseline, b"first\r\nsecond\r\n") == ()
    assert coverage.compare_document("leiame", baseline, b"first  \nsecond\n")


@pytest.mark.parametrize("current", [b" line\n", b"line\n\n", b"LINE\n", b"line", b"line\r"])
def test_normalization_does_not_hide_markdown_or_content_changes(current):
    assert coverage.compare_document(
        "leiame", coverage.document_fingerprint(b"line\n"), current
    )


def test_added_and_removed_lines_keep_unambiguous_evidence():
    baseline = coverage.document_fingerprint(b"alpha\nbeta\ngamma\n")
    changes = coverage.compare_document("changelog", baseline, b"alpha\ngamma\nnew\n")
    assert [change.kind for change in changes] == ["delete", "insert"]
    assert changes[0].baseline_start_line == 2
    assert len(changes[0].baseline_line_hashes) == 1
    assert changes[0].current_lines == ()
    assert changes[1].current_start_line == 3
    assert changes[1].current_lines == ("new",)


def test_repeated_lines_are_not_silently_deduplicated():
    baseline = coverage.document_fingerprint(b"rule\nrule\n")
    assert coverage.compare_document("politicas", baseline, b"rule\n")


def test_unicode_changes_are_preserved_and_results_are_deterministic():
    baseline = coverage.document_fingerprint("Não\n".encode())
    current = "Nao\n".encode()
    first = coverage.compare_document("apendice", baseline, current)
    assert first[0].current_lines == ("Nao",)
    assert first == coverage.compare_document("apendice", baseline, current)


@pytest.mark.parametrize("baseline", [("not-a-hash",), (), ["0" * 64]])
def test_malformed_baseline_fails_closed(baseline):
    with pytest.raises(ValueError, match="baseline"):
        coverage.compare_document("leiame", baseline, b"line\n")


def test_non_utf8_input_is_not_replaced_silently():
    with pytest.raises(ValueError, match="UTF-8"):
        coverage.document_fingerprint(b"\xff")
