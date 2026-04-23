"""Single source of truth for expected (agent, fixture) → verb-set mappings.

Each ExpectedOutcome defines what the targeted agent should produce when
run against the given fixture. Classifications (see classifier.py) measure
N-run distributions against these sets.

IMPORTANT — verb string conventions:
  SignalScribe terminal_verb : uppercase (DecisionVerb.value, e.g. "READY")
  BUAtlas terminal_verb      : lowercase Relevance.value (e.g. "affected")
  BUAtlas secondary_verb     : lowercase MessageQuality.value (e.g. "worth_sending")
  PushPilot terminal_verb    : lowercase DeliveryDecision.value (e.g. "send_now")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AgentName = Literal["signalscribe", "buatlas", "pushpilot"]
Classification = Literal[
    "stable",
    "acceptable_variance",
    "unstable",
    "false_positive_risk",
    "mismatch",
]


@dataclass(frozen=True)
class ExpectedOutcome:
    """Expected behavior for one (agent, fixture[, bu_id]) combination."""

    agent: AgentName
    fixture: str  # filename relative to fixtures/changes/
    # All verbs that count as "correct" for this fixture
    expected_terminal_verbs: frozenset[str]
    # Verbs that are defensibly close — not wrong, but not ideal
    acceptable_alternate_verbs: frozenset[str] = field(default_factory=frozenset)
    # Verbs that indicate the agent was MORE permissive than intended
    # (e.g., AFFECTED when ADJACENT was expected, or READY on an ambiguous input)
    false_positive_verbs: frozenset[str] = field(default_factory=frozenset)
    # BU under test — required for buatlas and pushpilot
    bu_id: str | None = None
    # Human-readable note for report generation
    notes: str = ""


# ---------------------------------------------------------------------------
# SignalScribe expectations (terminal_verb = last decision's verb, uppercase)
# Gate stopped at 1 → ARCHIVE / ESCALATE
# Gate stopped at 2 → HOLD_UNTIL / HOLD_INDEFINITE / ESCALATE
# Gate reached 3   → READY / NEED_CLARIFICATION / UNRESOLVABLE / ESCALATE
# ---------------------------------------------------------------------------

_SS_EXPECTATIONS: list[ExpectedOutcome] = [
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_001_clearcut_communicate.json",
        expected_terminal_verbs=frozenset({"READY"}),
        notes=(
            "Clear rollout signal — redesigned PA validation form visible to all HCP portal users. "
            "Should proceed through all 3 gates without early stop."
        ),
    ),
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_002_pure_internal_refactor.json",
        expected_terminal_verbs=frozenset({"ARCHIVE"}),
        false_positive_verbs=frozenset({"READY"}),
        notes=(
            "Internal message-queue client migration, no user-visible change. "
            "ARCHIVE at gate 1 is the only correct outcome. "
            "READY would mean the agent committed to communicating a purely internal refactor."
        ),
    ),
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_003_ambiguous_escalate.json",
        expected_terminal_verbs=frozenset({"ESCALATE"}),
        acceptable_alternate_verbs=frozenset(
            {"NEED_CLARIFICATION", "UNRESOLVABLE", "HOLD_INDEFINITE", "ARCHIVE"}
        ),
        false_positive_verbs=frozenset({"READY"}),
        notes=(
            "Designed-ambiguous: 'Portal Release — Sprint 47 Improvements' with vague language. "
            "Design intent is ESCALATE (ask a human). Dryrun 2026-04-23 shows ARCHIVE 2/2 times. "
            "ARCHIVE is defensible (too vague to act on) but differs from design intent. "
            "All uncertainty signals acceptable; READY would mean the agent committed to "
            "communicating a deliberately vague artifact."
        ),
    ),
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_004_early_flag_hold_until.json",
        expected_terminal_verbs=frozenset({"HOLD_UNTIL"}),
        acceptable_alternate_verbs=frozenset({"HOLD_INDEFINITE"}),
        false_positive_verbs=frozenset({"READY"}),
        notes=(
            "Feature flag enabled but not yet rolled out. "
            "HOLD_UNTIL at gate 2 is the expected verdict (hold until rollout is confirmed). "
            "HOLD_INDEFINITE is acceptable (agent chose longer-form hold). "
            "READY would mean the agent treated a not-yet-deployed feature as ready to communicate."
        ),
    ),
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_005_muddled_need_clarification.json",
        expected_terminal_verbs=frozenset(
            {"NEED_CLARIFICATION", "UNRESOLVABLE", "HOLD_INDEFINITE"}
        ),
        acceptable_alternate_verbs=frozenset({"ARCHIVE"}),
        false_positive_verbs=frozenset({"READY"}),
        notes=(
            "Muddled artifact with contradictory or incomplete signals. "
            "Any 'uncertainty' terminal verb is correct. ARCHIVE is acceptable (truly unresolvable). "
            "READY would mean the agent committed to communicating muddled content."
        ),
    ),
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_006_multi_bu_affected_vs_adjacent.json",
        expected_terminal_verbs=frozenset({"READY"}),
        notes=(
            "Analytics Portal new filtering/export capabilities — clear new feature. "
            "Should proceed through all 3 gates."
        ),
    ),
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_007_mlr_sensitive.json",
        expected_terminal_verbs=frozenset({"READY"}),
        notes=(
            "HCP Educational Module update — clinical content. "
            "SignalScribe should say READY; MLR review is enforced by policy at step 5, not gate 3. "
            "Agent should NOT self-censor on MLR sensitivity."
        ),
    ),
    ExpectedOutcome(
        agent="signalscribe",
        fixture="change_008_post_hoc_already_shipped.json",
        expected_terminal_verbs=frozenset({"READY"}),
        acceptable_alternate_verbs=frozenset({"ARCHIVE"}),
        notes=(
            "Post-hoc already-shipped change (notification wording standardization). "
            "READY is expected (retroactive communication still valuable). "
            "ARCHIVE is acceptable (agent may recognize it as already complete). "
            "No false-positive risk — READY on a shipped change is not harmful."
        ),
    ),
]

# ---------------------------------------------------------------------------
# BUAtlas expectations (terminal_verb = Relevance.value, lowercase)
# secondary_verb = MessageQuality.value (lowercase, only if AFFECTED)
# false_positive: AFFECTED when ADJACENT/NOT_AFFECTED expected = unwanted notification
# ---------------------------------------------------------------------------

_BA_EXPECTATIONS: list[ExpectedOutcome] = [
    ExpectedOutcome(
        agent="buatlas",
        fixture="change_001_clearcut_communicate.json",
        bu_id="bu_alpha",
        expected_terminal_verbs=frozenset({"affected"}),
        false_positive_verbs=frozenset(),
        notes=(
            "bu_alpha owns specialty_pharmacy + hcp_portal_ordering — directly in the PA form change. "
            "AFFECTED is the only correct verdict."
        ),
    ),
    ExpectedOutcome(
        agent="buatlas",
        fixture="change_006_multi_bu_affected_vs_adjacent.json",
        bu_id="bu_zeta",
        expected_terminal_verbs=frozenset({"affected"}),
        false_positive_verbs=frozenset(),
        notes=(
            "bu_zeta owns analytics_portal + reporting_dashboard — directly in scope. "
            "Dryrun 2026-04-23 confirmed AFFECTED."
        ),
    ),
    ExpectedOutcome(
        agent="buatlas",
        fixture="change_006_multi_bu_affected_vs_adjacent.json",
        bu_id="bu_delta",
        expected_terminal_verbs=frozenset({"adjacent"}),
        acceptable_alternate_verbs=frozenset({"not_affected"}),
        false_positive_verbs=frozenset({"affected"}),
        notes=(
            "bu_delta owns clinical_trial_operations + reporting (generic). "
            "Analytics Portal changes may touch reporting adjacently but not core delta BU scope. "
            "ADJACENT expected; AFFECTED would be a false positive (unwanted notification). "
            "WARNING: bu_delta may not appear in the candidate set if SignalScribe uses "
            "specific impact area terms — the runner will skip if bu_delta is not a candidate."
        ),
    ),
    ExpectedOutcome(
        agent="buatlas",
        fixture="change_007_mlr_sensitive.json",
        bu_id="bu_gamma",
        expected_terminal_verbs=frozenset({"affected"}),
        false_positive_verbs=frozenset(),
        notes=(
            "bu_gamma owns medical_information_portal + clinical_evidence_library. "
            "HCP Educational Module update directly impacts gamma's domain. "
            "Dryrun 2026-04-23 confirmed AFFECTED."
        ),
    ),
]

# ---------------------------------------------------------------------------
# PushPilot expectations (terminal_verb = DeliveryDecision.value, lowercase)
# Tests PushPilot's gate-6 timing judgment using PersonalizedBriefs derived
# from real fixture → SignalScribe → BUAtlas chains.
# DIGEST is a false positive for high-priority (P0/P1) changes.
# ---------------------------------------------------------------------------

_PP_EXPECTATIONS: list[ExpectedOutcome] = [
    ExpectedOutcome(
        agent="pushpilot",
        fixture="change_001_clearcut_communicate.json",
        bu_id="bu_alpha",
        expected_terminal_verbs=frozenset({"send_now", "hold_until"}),
        false_positive_verbs=frozenset({"digest"}),
        notes=(
            "bu_alpha P0 priority change during business hours. "
            "SEND_NOW is the ideal outcome; HOLD_UNTIL acceptable if agent sees timing risk. "
            "DIGEST is wrong — batching a P0 notification misrepresents urgency."
        ),
    ),
    ExpectedOutcome(
        agent="pushpilot",
        fixture="change_006_multi_bu_affected_vs_adjacent.json",
        bu_id="bu_zeta",
        expected_terminal_verbs=frozenset({"send_now", "hold_until"}),
        false_positive_verbs=frozenset({"digest"}),
        notes=(
            "bu_zeta analytics change — SEND_NOW or HOLD_UNTIL expected. "
            "bu_zeta's profile will determine whether digest is acceptable channel; "
            "since this is a high-priority feature update, DIGEST is a false positive risk."
        ),
    ),
    ExpectedOutcome(
        agent="pushpilot",
        fixture="change_007_mlr_sensitive.json",
        bu_id="bu_gamma",
        expected_terminal_verbs=frozenset({"send_now", "hold_until"}),
        false_positive_verbs=frozenset({"digest"}),
        notes=(
            "bu_gamma MLR-sensitive change. PushPilot should recommend send_now or hold_until. "
            "MLR restriction is enforced by policy (HITL trigger), not by PushPilot's gate-6 decision. "
            "DIGEST would be wrong — MLR review requires explicit approval, not batching."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Combined public list
# ---------------------------------------------------------------------------

EXPECTATIONS: list[ExpectedOutcome] = _SS_EXPECTATIONS + _BA_EXPECTATIONS + _PP_EXPECTATIONS
