"""Eval runner — executes N invocations of one agent against one fixture.

Run isolation:
  SignalScribe — direct invocation; ChangeBrief produced each run.
  BUAtlas      — SignalScribe runs ONCE (setup) to produce a stable ChangeBrief;
                 BUAtlas runs N times against that brief for the specified bu_id.
  PushPilot    — SignalScribe + BUAtlas each run ONCE (setup); PushPilot runs N times.

The 'setup' invocations (SS for BA; SS+BA for PP) are not counted in run_index,
cost, or elapsed for the target agent — they are pure prerequisites.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from pulsecraft.eval.classifier import classify
from pulsecraft.eval.expectations import Classification, ExpectedOutcome


@dataclass
class EvalRun:
    """Result of one invocation of the target agent."""

    agent: str
    fixture: str
    run_index: int  # 1..N
    terminal_verb: str | None
    secondary_verb: str | None  # gate-5 quality for BUAtlas; None otherwise
    confidence: float | None
    elapsed_s: float
    cost_usd: float
    error: str | None  # non-None when invocation raised


@dataclass
class FixtureEvalResult:
    """Aggregated result for one (agent, fixture[, bu_id]) across N runs."""

    agent: str
    fixture: str
    bu_id: str | None
    runs: list[EvalRun]
    verb_distribution: dict[str, int]  # terminal_verb → count across N runs
    classification: Classification
    expected: ExpectedOutcome
    total_cost_usd: float
    total_elapsed_s: float
    skipped: bool = False  # True when BU not in candidate set
    skip_reason: str = ""


def _load_env() -> None:
    import os

    env_path = Path(__file__).parents[3] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _run_signalscribe(
    expected: ExpectedOutcome,
    fixture_path: Path,
    *,
    n_runs: int,
) -> FixtureEvalResult:
    from pulsecraft.agents.signalscribe import SignalScribe
    from pulsecraft.schemas.change_artifact import ChangeArtifact

    artifact = ChangeArtifact.model_validate(json.loads(fixture_path.read_text()))
    ss = SignalScribe()

    runs: list[EvalRun] = []
    for i in range(1, n_runs + 1):
        t0 = time.monotonic()
        try:
            brief = ss.invoke(artifact)
            elapsed = time.monotonic() - t0
            terminal_verb = str(brief.decisions[-1].verb) if brief.decisions else None
            confidence = brief.decisions[-1].confidence if brief.decisions else None
            cost_usd = brief.usd_estimate or 0.0
            runs.append(
                EvalRun(
                    agent="signalscribe",
                    fixture=expected.fixture,
                    run_index=i,
                    terminal_verb=terminal_verb,
                    secondary_verb=None,
                    confidence=confidence,
                    elapsed_s=elapsed,
                    cost_usd=cost_usd,
                    error=None,
                )
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            runs.append(
                EvalRun(
                    agent="signalscribe",
                    fixture=expected.fixture,
                    run_index=i,
                    terminal_verb=None,
                    secondary_verb=None,
                    confidence=None,
                    elapsed_s=elapsed,
                    cost_usd=0.0,
                    error=f"{type(exc).__name__}: {str(exc)[:120]}",
                )
            )

    return _build_result(runs, expected)


def _run_buatlas(
    expected: ExpectedOutcome,
    fixture_path: Path,
    *,
    n_runs: int,
) -> FixtureEvalResult:
    from pulsecraft.agents.buatlas import BUAtlas
    from pulsecraft.agents.signalscribe import SignalScribe
    from pulsecraft.config.loader import get_bu_profile, get_bu_registry
    from pulsecraft.schemas.change_artifact import ChangeArtifact
    from pulsecraft.schemas.personalized_brief import Relevance
    from pulsecraft.skills.registry import lookup_bu_candidates

    assert expected.bu_id, "BUAtlas eval requires bu_id in ExpectedOutcome"

    artifact = ChangeArtifact.model_validate(json.loads(fixture_path.read_text()))

    # Setup: run SignalScribe once to get a ChangeBrief
    ss = SignalScribe()
    brief = ss.invoke(artifact)

    # Check whether the target BU is in the candidate set
    registry = get_bu_registry()
    candidates = lookup_bu_candidates(brief, registry)
    if expected.bu_id not in candidates:
        return FixtureEvalResult(
            agent="buatlas",
            fixture=expected.fixture,
            bu_id=expected.bu_id,
            runs=[],
            verb_distribution={},
            classification="mismatch",
            expected=expected,
            total_cost_usd=0.0,
            total_elapsed_s=0.0,
            skipped=True,
            skip_reason=(
                f"{expected.bu_id} not in candidate set "
                f"(SignalScribe impact_areas={brief.impact_areas}). "
                "See expectations.py note for this fixture."
            ),
        )

    bu_profile = get_bu_profile(expected.bu_id)
    ba = BUAtlas()

    runs: list[EvalRun] = []
    for i in range(1, n_runs + 1):
        t0 = time.monotonic()
        try:
            pb = ba.invoke(brief, bu_profile)
            elapsed = time.monotonic() - t0
            terminal_verb = str(pb.relevance)
            secondary_verb = str(pb.message_quality) if pb.relevance == Relevance.AFFECTED else None
            confidence = pb.confidence_score
            cost_usd = pb.usd_estimate or 0.0
            runs.append(
                EvalRun(
                    agent="buatlas",
                    fixture=expected.fixture,
                    run_index=i,
                    terminal_verb=terminal_verb,
                    secondary_verb=secondary_verb,
                    confidence=confidence,
                    elapsed_s=elapsed,
                    cost_usd=cost_usd,
                    error=None,
                )
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            runs.append(
                EvalRun(
                    agent="buatlas",
                    fixture=expected.fixture,
                    run_index=i,
                    terminal_verb=None,
                    secondary_verb=None,
                    confidence=None,
                    elapsed_s=elapsed,
                    cost_usd=0.0,
                    error=f"{type(exc).__name__}: {str(exc)[:120]}",
                )
            )

    return _build_result(runs, expected)


def _run_pushpilot(
    expected: ExpectedOutcome,
    fixture_path: Path,
    *,
    n_runs: int,
) -> FixtureEvalResult:
    from pulsecraft.agents.buatlas import BUAtlas
    from pulsecraft.agents.pushpilot import PushPilot
    from pulsecraft.agents.signalscribe import SignalScribe
    from pulsecraft.config.loader import get_bu_profile, get_bu_registry
    from pulsecraft.schemas.change_artifact import ChangeArtifact
    from pulsecraft.schemas.personalized_brief import Relevance
    from pulsecraft.skills.registry import lookup_bu_candidates

    assert expected.bu_id, "PushPilot eval requires bu_id in ExpectedOutcome"

    artifact = ChangeArtifact.model_validate(json.loads(fixture_path.read_text()))

    # Setup: run SignalScribe once, then BUAtlas once for the target BU
    ss = SignalScribe()
    brief = ss.invoke(artifact)

    registry = get_bu_registry()
    candidates = lookup_bu_candidates(brief, registry)
    if expected.bu_id not in candidates:
        return FixtureEvalResult(
            agent="pushpilot",
            fixture=expected.fixture,
            bu_id=expected.bu_id,
            runs=[],
            verb_distribution={},
            classification="mismatch",
            expected=expected,
            total_cost_usd=0.0,
            total_elapsed_s=0.0,
            skipped=True,
            skip_reason=(
                f"{expected.bu_id} not in candidate set "
                f"(SignalScribe impact_areas={brief.impact_areas})."
            ),
        )

    bu_profile = get_bu_profile(expected.bu_id)
    ba = BUAtlas()
    pb = ba.invoke(brief, bu_profile)

    if pb.relevance != Relevance.AFFECTED:
        return FixtureEvalResult(
            agent="pushpilot",
            fixture=expected.fixture,
            bu_id=expected.bu_id,
            runs=[],
            verb_distribution={},
            classification="mismatch",
            expected=expected,
            total_cost_usd=0.0,
            total_elapsed_s=0.0,
            skipped=True,
            skip_reason=(
                f"BUAtlas returned {pb.relevance!r} for {expected.bu_id} — "
                "PushPilot eval requires AFFECTED."
            ),
        )

    pp = PushPilot()

    runs: list[EvalRun] = []
    for i in range(1, n_runs + 1):
        t0 = time.monotonic()
        try:
            output = pp.invoke(pb, bu_profile)
            elapsed = time.monotonic() - t0
            terminal_verb = str(output.decision)
            cost_usd = output.usd_estimate or 0.0
            runs.append(
                EvalRun(
                    agent="pushpilot",
                    fixture=expected.fixture,
                    run_index=i,
                    terminal_verb=terminal_verb,
                    secondary_verb=None,
                    confidence=output.confidence_score,
                    elapsed_s=elapsed,
                    cost_usd=cost_usd,
                    error=None,
                )
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            runs.append(
                EvalRun(
                    agent="pushpilot",
                    fixture=expected.fixture,
                    run_index=i,
                    terminal_verb=None,
                    secondary_verb=None,
                    confidence=None,
                    elapsed_s=elapsed,
                    cost_usd=0.0,
                    error=f"{type(exc).__name__}: {str(exc)[:120]}",
                )
            )

    return _build_result(runs, expected)


def _build_result(runs: list[EvalRun], expected: ExpectedOutcome) -> FixtureEvalResult:
    verb_distribution: dict[str, int] = {}
    for r in runs:
        key = r.terminal_verb or "ERROR"
        verb_distribution[key] = verb_distribution.get(key, 0) + 1

    classification = classify(verb_distribution, expected)

    return FixtureEvalResult(
        agent=expected.agent,
        fixture=expected.fixture,
        bu_id=expected.bu_id,
        runs=runs,
        verb_distribution=verb_distribution,
        classification=classification,
        expected=expected,
        total_cost_usd=sum(r.cost_usd for r in runs),
        total_elapsed_s=sum(r.elapsed_s for r in runs),
    )


def run_agent_eval(
    expected: ExpectedOutcome,
    fixture_path: Path,
    *,
    n_runs: int = 3,
) -> FixtureEvalResult:
    """Execute n_runs of expected.agent against fixture_path. Return structured result."""
    _load_env()

    dispatch = {
        "signalscribe": _run_signalscribe,
        "buatlas": _run_buatlas,
        "pushpilot": _run_pushpilot,
    }
    fn = dispatch[expected.agent]
    return fn(expected, fixture_path, n_runs=n_runs)
