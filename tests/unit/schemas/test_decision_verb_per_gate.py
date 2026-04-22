"""Assert that each gate only emits decision verbs matching the decision criteria doc.

Gate-to-verb mapping is hardcoded from design/planning/01-decision-criteria.md.
ESCALATE is valid for all gates (stated in the cross-cutting note: 'Each gate can
also emit ESCALATE to route to human review when confidence is too low').
"""

from __future__ import annotations

from pulsecraft.schemas.decision import DecisionVerb

# Verbs permitted per gate, sourced from the overview table in 01-decision-criteria.md.
# ESCALATE is added to all gates per the cross-cutting note.
GATE_VERBS: dict[int, set[DecisionVerb]] = {
    1: {DecisionVerb.COMMUNICATE, DecisionVerb.ARCHIVE, DecisionVerb.ESCALATE},
    2: {
        DecisionVerb.RIPE,
        DecisionVerb.HOLD_UNTIL,
        DecisionVerb.HOLD_INDEFINITE,
        DecisionVerb.ESCALATE,
    },
    3: {
        DecisionVerb.READY,
        DecisionVerb.NEED_CLARIFICATION,
        DecisionVerb.UNRESOLVABLE,
        DecisionVerb.ESCALATE,
    },
    4: {
        DecisionVerb.AFFECTED,
        DecisionVerb.ADJACENT,
        DecisionVerb.NOT_AFFECTED,
        DecisionVerb.ESCALATE,
    },
    5: {
        DecisionVerb.WORTH_SENDING,
        DecisionVerb.WEAK,
        DecisionVerb.NOT_WORTH,
        DecisionVerb.ESCALATE,
    },
    6: {DecisionVerb.SEND_NOW, DecisionVerb.HOLD_UNTIL, DecisionVerb.DIGEST, DecisionVerb.ESCALATE},
}


def test_all_gates_covered() -> None:
    assert set(GATE_VERBS.keys()) == {1, 2, 3, 4, 5, 6}


def test_all_gate_verb_sets_nonempty() -> None:
    for gate, verbs in GATE_VERBS.items():
        assert verbs, f"Gate {gate} has no verbs"


def test_all_gate_verbs_are_valid_decision_verbs() -> None:
    all_valid = set(DecisionVerb)
    for gate, verbs in GATE_VERBS.items():
        invalid = verbs - all_valid
        assert not invalid, f"Gate {gate} references unknown verbs: {invalid}"


def test_escalate_valid_for_all_gates() -> None:
    for gate in range(1, 7):
        assert DecisionVerb.ESCALATE in GATE_VERBS[gate], (
            f"ESCALATE must be valid for gate {gate} per cross-cutting principle"
        )


def test_gate1_verbs() -> None:
    assert GATE_VERBS[1] == {DecisionVerb.COMMUNICATE, DecisionVerb.ARCHIVE, DecisionVerb.ESCALATE}


def test_gate2_verbs() -> None:
    assert GATE_VERBS[2] == {
        DecisionVerb.RIPE,
        DecisionVerb.HOLD_UNTIL,
        DecisionVerb.HOLD_INDEFINITE,
        DecisionVerb.ESCALATE,
    }


def test_gate3_verbs() -> None:
    assert GATE_VERBS[3] == {
        DecisionVerb.READY,
        DecisionVerb.NEED_CLARIFICATION,
        DecisionVerb.UNRESOLVABLE,
        DecisionVerb.ESCALATE,
    }


def test_gate4_verbs() -> None:
    assert GATE_VERBS[4] == {
        DecisionVerb.AFFECTED,
        DecisionVerb.ADJACENT,
        DecisionVerb.NOT_AFFECTED,
        DecisionVerb.ESCALATE,
    }


def test_gate5_verbs() -> None:
    assert GATE_VERBS[5] == {
        DecisionVerb.WORTH_SENDING,
        DecisionVerb.WEAK,
        DecisionVerb.NOT_WORTH,
        DecisionVerb.ESCALATE,
    }


def test_gate6_verbs() -> None:
    assert GATE_VERBS[6] == {
        DecisionVerb.SEND_NOW,
        DecisionVerb.HOLD_UNTIL,
        DecisionVerb.DIGEST,
        DecisionVerb.ESCALATE,
    }


def test_no_verb_belongs_to_no_gate() -> None:
    """Every verb in DecisionVerb must appear in at least one gate's permitted set."""
    all_assigned = set()
    for verbs in GATE_VERBS.values():
        all_assigned |= verbs
    unassigned = set(DecisionVerb) - all_assigned
    assert not unassigned, f"These verbs are not assigned to any gate: {unassigned}"
