"""Classify an N-run distribution of terminal verbs against an ExpectedOutcome.

Classification is asymmetric: false_positive_risk is the worst class because
sending an unwanted notification erodes BU trust faster than holding back.
Check order: false_positive_risk → mismatch → stable → acceptable_variance → unstable.
"""

from __future__ import annotations

from pulsecraft.eval.expectations import Classification, ExpectedOutcome


def classify(
    verb_distribution: dict[str, int],
    expected: ExpectedOutcome,
) -> Classification:
    """Return classification for an N-run verb distribution.

    stable            — all runs in expected_terminal_verbs
    acceptable_variance — all runs in (expected ∪ acceptable); at least one not in expected
    unstable          — runs span beyond (expected ∪ acceptable); no false positives
    false_positive_risk — any run in false_positive_verbs
    mismatch          — no runs in (expected ∪ acceptable)
    """
    if not verb_distribution:
        return "mismatch"

    all_verbs = set(verb_distribution.keys())
    allowed = expected.expected_terminal_verbs | expected.acceptable_alternate_verbs

    # false_positive_risk — asymmetric worst class; check first
    if expected.false_positive_verbs and all_verbs & expected.false_positive_verbs:
        return "false_positive_risk"

    in_allowed = all_verbs & allowed

    # mismatch — nothing landed in allowed set
    if not in_allowed:
        return "mismatch"

    # stable — all runs in expected (no alternates used)
    if all_verbs <= expected.expected_terminal_verbs:
        return "stable"

    # acceptable_variance — all in allowed; some used alternates
    if all_verbs <= allowed:
        return "acceptable_variance"

    # unstable — some runs outside allowed (but no false positives)
    return "unstable"
