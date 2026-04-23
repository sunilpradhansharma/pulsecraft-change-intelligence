"""Unit tests for the eval classifier."""

from __future__ import annotations

from pulsecraft.eval.classifier import classify
from pulsecraft.eval.expectations import ExpectedOutcome


def _expected(
    expected_verbs: set[str],
    acceptable: set[str] | None = None,
    false_positive: set[str] | None = None,
) -> ExpectedOutcome:
    return ExpectedOutcome(
        agent="signalscribe",
        fixture="test.json",
        expected_terminal_verbs=frozenset(expected_verbs),
        acceptable_alternate_verbs=frozenset(acceptable or set()),
        false_positive_verbs=frozenset(false_positive or set()),
    )


# --- stable ---


def test_stable_all_runs_in_expected():
    exp = _expected({"READY"})
    assert classify({"READY": 3}, exp) == "stable"


def test_stable_all_runs_in_expected_multiverb():
    exp = _expected({"NEED_CLARIFICATION", "UNRESOLVABLE", "HOLD_INDEFINITE"})
    assert classify({"NEED_CLARIFICATION": 2, "UNRESOLVABLE": 1}, exp) == "stable"


# --- acceptable_variance ---


def test_acceptable_variance_some_in_expected_some_in_alternate():
    exp = _expected({"ESCALATE"}, acceptable={"NEED_CLARIFICATION", "ARCHIVE"})
    assert classify({"ESCALATE": 2, "ARCHIVE": 1}, exp) == "acceptable_variance"


def test_acceptable_variance_all_in_alternate():
    exp = _expected({"ESCALATE"}, acceptable={"ARCHIVE"})
    assert classify({"ARCHIVE": 3}, exp) == "acceptable_variance"


# --- unstable ---


def test_unstable_runs_outside_allowed():
    exp = _expected({"READY"}, acceptable={"ARCHIVE"})
    assert classify({"READY": 2, "UNRESOLVABLE": 1}, exp) == "unstable"


def test_unstable_mixed_with_unknown_verb():
    exp = _expected({"ARCHIVE"}, acceptable={"ESCALATE"})
    # READY is not in allowed set and not in false_positive_verbs
    assert classify({"ARCHIVE": 2, "READY": 1}, exp) == "unstable"


# --- false_positive_risk ---


def test_false_positive_risk_any_run_in_fp_verbs():
    exp = _expected({"ARCHIVE"}, false_positive={"READY"})
    assert classify({"ARCHIVE": 2, "READY": 1}, exp) == "false_positive_risk"


def test_false_positive_risk_all_runs_fp():
    exp = _expected({"ARCHIVE"}, false_positive={"READY"})
    assert classify({"READY": 3}, exp) == "false_positive_risk"


def test_false_positive_risk_beats_mismatch():
    exp = _expected({"ARCHIVE"}, false_positive={"READY"})
    # READY is in false_positive; ARCHIVE is expected — but READY is the fp case
    assert classify({"READY": 3}, exp) == "false_positive_risk"


# --- mismatch ---


def test_mismatch_nothing_in_allowed():
    exp = _expected({"READY"}, acceptable={"ARCHIVE"})
    assert classify({"ESCALATE": 3}, exp) == "mismatch"


def test_mismatch_empty_distribution():
    exp = _expected({"READY"})
    assert classify({}, exp) == "mismatch"


# --- edge cases ---


def test_single_run_stable():
    exp = _expected({"ARCHIVE"})
    assert classify({"ARCHIVE": 1}, exp) == "stable"


def test_false_positive_checked_before_allowed():
    """A verb that is both acceptable AND false_positive should trigger false_positive_risk.
    (Shouldn't happen in practice but ordering matters.)"""
    exp = _expected(
        {"ESCALATE"},
        acceptable={"ARCHIVE"},
        false_positive={"ARCHIVE"},  # contradictory but must respect fp priority
    )
    assert classify({"ARCHIVE": 3}, exp) == "false_positive_risk"
