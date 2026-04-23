"""Eval harness integration tests — expensive, opt-in.

Run with:
    PULSECRAFT_RUN_EVAL_TESTS=1 pytest tests/eval/test_agent_evals.py -v -m eval

Each test invokes a real LLM agent (N=3 runs) and asserts:
  - classification != "mismatch"
  - classification != "false_positive_risk"

Skipped cases (BU not in candidate set) are not tested.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pulsecraft.eval.expectations import EXPECTATIONS, ExpectedOutcome
from pulsecraft.eval.runner import run_agent_eval

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "changes"

pytestmark = pytest.mark.eval

_EVAL_RUNS = int(os.environ.get("PULSECRAFT_EVAL_RUNS", "3"))


@pytest.fixture(autouse=True)
def _require_eval_flag():
    if not os.environ.get("PULSECRAFT_RUN_EVAL_TESTS"):
        pytest.skip("Set PULSECRAFT_RUN_EVAL_TESTS=1 to run eval tests")


def _eval_id(e: ExpectedOutcome) -> str:
    fixture_stem = e.fixture.replace("change_", "").replace(".json", "")
    bu = f"-{e.bu_id}" if e.bu_id else ""
    return f"{e.agent}-{fixture_stem}{bu}"


@pytest.mark.parametrize("expected", EXPECTATIONS, ids=_eval_id)
def test_agent_eval_passes(expected: ExpectedOutcome) -> None:
    fixture_path = FIXTURES_DIR / expected.fixture
    result = run_agent_eval(expected, fixture_path, n_runs=_EVAL_RUNS)

    if result.skipped:
        pytest.skip(f"Skipped: {result.skip_reason}")

    assert result.classification != "mismatch", (
        f"{expected.agent} on {expected.fixture}"
        + (f" / {expected.bu_id}" if expected.bu_id else "")
        + f": observed {result.verb_distribution}, "
        f"expected one of {sorted(expected.expected_terminal_verbs)}"
    )
    assert result.classification != "false_positive_risk", (
        f"{expected.agent} on {expected.fixture}"
        + (f" / {expected.bu_id}" if expected.bu_id else "")
        + f": at least one run landed in false-positive set "
        f"{sorted(expected.false_positive_verbs)} — observed {result.verb_distribution}"
    )
