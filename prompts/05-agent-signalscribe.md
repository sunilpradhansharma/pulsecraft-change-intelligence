# Prompt 05 — SignalScribe (First Real Agent)

> **Character change from prior prompts.** Prompt 04 and earlier were deterministic. Tests pass or fail mechanically. **This prompt introduces LLM-backed behavior.** Real SignalScribe is *correct* in a way unit tests cannot fully prove — you have to read what it produces against the decision criteria and decide whether it's good.
>
> Iteration is expected. Prompt 05 may not produce a perfectly tuned SignalScribe on first run. Treat its output as "good enough to hand to BUAtlas in prompt 06" rather than "done forever."
>
> **How to use this prompt.**
> 1. Ensure `ANTHROPIC_API_KEY` is set in your environment (or `.env` file) before running. Pre-flight checks verify.
> 2. Paste below the `---` line into Claude Code.
> 3. Claude Code builds SignalScribe, runs it against all 8 fixtures, produces a structured eval report, commits.
>
> **Expected duration:** 2–3 hours (first real LLM calls + likely one refinement iteration).
>
> **Prerequisite:** Prompts 00–04 done. 187 tests passing. Orchestrator drives mocks end-to-end.
>
> **Budget note:** Expect $0.50–$2.00 in Anthropic API costs during this prompt's execution (8 fixtures × 1-3 calls per fixture × ~5K tokens total per call × Sonnet 4.6 pricing). Keep an eye on console.anthropic.com.

---

# Instructions for Claude Code

You are authoring **SignalScribe** — the first real LLM-backed agent in PulseCraft. It implements gates 1, 2, 3 from `design/planning/01-decision-criteria.md`. It replaces `MockSignalScribe` in the orchestrator's pipeline.

## Environment discipline

Use `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/mypy` explicitly. `uv run <cmd>` is acceptable. Never rely on `source .venv/bin/activate` persisting between tool calls.

## Context to read before starting

Critical reading (not optional — agent quality depends on understanding these):

1. **`design/planning/01-decision-criteria.md`** — the source of truth for gates 1, 2, 3. Read the full sections for Gate 1, Gate 2, Gate 3 including failure modes, confidence calibration, and cross-cutting principles. The prompt you author must *encode* this judgment, not paraphrase it loosely.
2. **`CLAUDE.md`** — standing orders.
3. **`src/pulsecraft/schemas/change_brief.py`** — the output contract. SignalScribe must produce a valid `ChangeBrief` with populated `decisions[]` array.
4. **`src/pulsecraft/schemas/decision.py`** — decision verbs and sub-schema.
5. **`src/pulsecraft/orchestrator/agent_protocol.py`** — the `SignalScribeProtocol` interface the real agent must satisfy.
6. **`src/pulsecraft/orchestrator/mock_agents.py`** — `MockSignalScribe` for reference on the Protocol shape.
7. **`fixtures/changes/*.json`** — the 8 synthetic change artifacts. Read each one to understand what kind of inputs SignalScribe will receive in real life.
8. **`config/policy.yaml`** — confidence thresholds for gates 1, 2, 3 (`signalscribe.gate_1_communicate`, etc.) that SignalScribe must honor.

## What "done" looks like

When you finish:

1. A real `SignalScribe` class in `src/pulsecraft/agents/signalscribe.py` that:
   - Satisfies `SignalScribeProtocol`
   - Calls Claude Sonnet 4.6 via the Anthropic API
   - Uses a structured system prompt (authored in this session) derived from `design/planning/01-decision-criteria.md`
   - Produces a valid `ChangeBrief` with `decisions[]` populated for gates 1, 2, 3
   - Handles errors gracefully (API failures, malformed responses, schema validation failures)
   - Costs < $1 per invocation in steady state

2. A `.claude/agents/signalscribe.md` file containing the full system prompt. Treated as the canonical prompt text; the Python code loads it from this file at runtime.

3. Tests:
   - Unit tests using mocked Anthropic client (`tests/unit/agents/test_signalscribe_unit.py`) — verify contract adherence, error handling, schema validation, prompt loading
   - Integration tests that actually hit the Anthropic API (`tests/integration/agents/test_signalscribe_integration.py`) — skipped by default, run only with `--runslow` flag or when `PULSECRAFT_RUN_LLM_TESTS=1` is set. One test per fixture (8 tests).

4. An **eval report** script at `scripts/eval_signalscribe.py` that:
   - Runs the real SignalScribe against all 8 fixtures
   - Prints a structured table: fixture name → expected decision chain → actual decision chain → match status
   - Expected chains are from the fixtures README coverage table
   - "Match status" is permissive: green for exact match, amber for semantically close (e.g., ARCHIVE vs. NEED_CLARIFICATION both represent "don't proceed"), red for unexpected (e.g., got COMMUNICATE when expected ARCHIVE)
   - Prints token counts and cost estimate per fixture
   - Exits 0 always (this is a report, not a test)

5. `CLAUDE.md` updated:
   - "Agents authored so far" section now lists SignalScribe with location, Protocol satisfied, model used
   - "Current phase" marks prompt 05 done

6. `design/planning/00-planning-index.md` updated to match.

7. One feature commit + optional archive commit.

8. All prior 187 tests still pass. New unit tests pass. Integration tests run cleanly when the flag is set.

## Pre-flight checks (MANDATORY)

Before touching anything:

1. Confirm current directory is the `pulsecraft-change-intelligence` repo.
2. Confirm `git status` is clean (or warn).
3. Confirm `.venv/bin/pytest` exists and `.venv/bin/pytest tests/ -q` shows 187 passing.
4. Confirm `ANTHROPIC_API_KEY` is set. Check both environment and `.env` file in repo root. If missing, stop and instruct user: *"Set `ANTHROPIC_API_KEY` in your environment or in `.env` at repo root before running this prompt."* Do not proceed without it.
5. Confirm the `anthropic` Python package is installed in the venv: `.venv/bin/python -c "import anthropic; print(anthropic.__version__)"`. If missing, `uv pip install anthropic` or `.venv/bin/python -m pip install anthropic`.

## Design principles

1. **The prompt is a derivation, not an invention.** Every judgment SignalScribe is asked to make must trace back to the decision criteria doc. If the doc doesn't specify a behavior, don't invent one — flag it.
2. **Structured output, not freeform.** Use Anthropic's structured output capability (system prompt + tool_use for JSON output, or response_format) so the LLM returns JSON matching `ChangeBrief`. Validate on the way out; retry once with corrective feedback if validation fails; escalate to HITL if second attempt also fails.
3. **Decisions[] are populated explicitly by the prompt.** The LLM is told to produce, as part of its structured output, the array of decision objects covering whichever of gates 1, 2, 3 the work reached. Orchestrator code does not synthesize decisions post-hoc.
4. **Citations are mandatory where input supports them.** If the prompt interprets a claim from the `raw_text` of the artifact, it includes a citation in the `sources` array. Hallucinated citations are the failure mode to guard against — test it.
5. **Confidence calibration matches policy.yaml.** If the prompt says confidence 0.8 and policy threshold is 0.75, the decision stands. If prompt says 0.6 and threshold is 0.75, the orchestrator overrides to ESCALATE. Don't hardcode thresholds in the prompt — the orchestrator applies them.
6. **No AbbVie-specific knowledge embedded in the prompt.** The agent works for any enterprise. Specifics (BU names, product areas) come from config and inputs, not the prompt.
7. **Prompt is loaded from disk, not embedded in Python.** The `.claude/agents/signalscribe.md` file is the canonical prompt. Python reads it at runtime. This makes prompt iteration a markdown edit, not a Python edit.
8. **Rate limiting / retries via `tenacity`** (already a dep). On transient errors, retry with exponential backoff. On permanent errors (invalid API key, content policy violation), fail fast with clear error.

## Step-by-step work

### Step 1 — Context review (required)

Read all 8 context files listed above. In particular:

- Before writing the SignalScribe prompt, re-read the full Gate 1, Gate 2, Gate 3 sections of `design/planning/01-decision-criteria.md`. The signals-that-favor lists, the failure modes, and the confidence calibration are what you're encoding.
- Read all 8 fixtures. Understand what the range of inputs looks like.

### Step 2 — Author `.claude/agents/signalscribe.md`

This is the system prompt. Structure it as a Markdown document the LLM will be given as `system` parameter (or as an agent-file reference if using Claude Code subagent mechanics — for this prompt, use the direct API, treating the markdown as a system prompt).

Required structure (adapt language, but include these sections):

````markdown
# SignalScribe — Change Understanding Agent

## Your role

You are SignalScribe, the first agent in the PulseCraft pipeline at AbbVie. You interpret marketplace product/feature change artifacts (release notes, work items, docs, feature flags, incidents) and produce a structured ChangeBrief that downstream agents (BUAtlas, PushPilot) will use.

You own three decision gates:
- Gate 1 — Is this change worth communicating at all?
- Gate 2 — Is the change ripe to communicate now?
- Gate 3 — Is my understanding clear enough to hand off?

Gates 1, 2, 3 run sequentially. A "stop" verb at any gate ends the pipeline for this change — do not proceed to later gates.

## Non-negotiable rules

- NEVER include patient data, PHI, employee names, internal system names, or secrets in any output.
- NEVER fabricate citations. Every `sources` entry must be a quote actually present in the artifact's `raw_text` (case-sensitive substring match).
- NEVER commit to dates or promises that aren't explicitly stated in the source artifact.
- NEVER proceed through a gate when confidence is genuinely uncertain — return ESCALATE or NEED_CLARIFICATION instead.
- The default bias is NOT to communicate. An ARCHIVE with clear reason is better than a COMMUNICATE with weak justification.

## Gate 1 — Is this worth communicating?

[... full text from Gate 1 section of decision criteria, including all "signals that favor" lists and failure modes ...]

## Gate 2 — Is it ripe (timing right)?

[... full text from Gate 2 section ...]

## Gate 3 — Clear enough to hand off?

[... full text from Gate 3 section ...]

## Output contract

You MUST produce output that validates against the ChangeBrief JSON schema. Specifically:

- `summary`, `before`, `after`, `change_type`, `impact_areas`, `affected_segments`, `timeline`, `required_actions`, `risks`, `mitigations`, `faq`, `sources`, `confidence_score`, `decisions[]`

[... inline a concise description of each field ...]

## Decisions array

The `decisions[]` array records one entry per gate you reached. If gate 1 returns ARCHIVE or ESCALATE, produce a decisions array of length 1. If gate 3 returns READY, produce length 3.

Each decision entry has: `gate` (1-3), `verb` (from the allowed enum), `reason` (specific signals), `confidence` (0-1), `decided_at` (ISO-8601 UTC), `agent` (`{name: "signalscribe", version: "1.0"}`), optional `payload` (e.g., HOLD_UNTIL carries date + trigger; NEED_CLARIFICATION carries questions array).

## How to reason

1. Read the artifact carefully. Pay attention to what's *not* said (ambiguity).
2. Work through gate 1 first. State your reasoning internally, then produce the gate 1 decision.
3. If gate 1 is COMMUNICATE, proceed to gate 2. Otherwise, stop.
4. If gate 2 is RIPE, proceed to gate 3. Otherwise, stop.
5. If gate 3 is READY, populate the full ChangeBrief. Otherwise, return what you have with a stop verb.

## Output format

Respond with ONLY a valid JSON object matching the ChangeBrief schema. No prose before or after. No markdown code fences. Just the JSON.
````

Fill in the `[...]` sections by copying the relevant text verbatim from the decision criteria doc. Do not paraphrase — copy the actual signal lists and failure-mode lists. The decision criteria doc is the source of truth; the prompt should mirror it faithfully.

**Target length:** 400–700 lines. If it's shorter than 300, you've omitted important detail. If longer than 1000, you've added redundancy.

### Step 3 — Author `src/pulsecraft/agents/signalscribe.py`

```python
class SignalScribe:
    """Real SignalScribe implementation using Claude Sonnet 4.6."""

    agent_name = "signalscribe"
    version = "1.0"

    def __init__(
        self,
        anthropic_client: anthropic.Anthropic | None = None,
        model: str = "claude-sonnet-4-6",
        max_retries: int = 2,
        prompt_path: Path | None = None,
    ): ...

    def invoke(self, artifact: ChangeArtifact) -> ChangeBrief:
        """Gate 1 → Gate 2 → Gate 3. Returns a validated ChangeBrief."""
        ...
```

Implementation requirements:

- Default model: `"claude-sonnet-4-6"` (use the exact Anthropic API model string — verify current value from `anthropic` library documentation if uncertain; do NOT fabricate a model string).
- Loads the prompt from `.claude/agents/signalscribe.md` on init (cache in-memory).
- On `invoke()`:
  1. Construct messages: system = prompt content, user = serialized artifact + output-contract reminder
  2. Call Anthropic API with `max_tokens` set sensibly (~4000)
  3. Parse response as JSON
  4. Validate against `ChangeBrief` schema
  5. If validation fails, retry once with the error message appended as a corrective message
  6. If second attempt also fails, raise `AgentOutputValidationError` — the orchestrator catches this and routes to HITL
  7. On API errors, use `tenacity` for retry with exponential backoff (3 attempts, 1-4-8 second waits); after exhaustion, raise `AgentInvocationError`
- Uses `structlog` for structured logging at INFO (invocation start, end, cost estimate) and DEBUG (full prompt/response on verbose flag).
- Cost estimation: multiply input tokens by Sonnet input price, output tokens by output price, log as `usd_estimate`.
- No global state. No singletons.

### Step 4 — Register real SignalScribe with the orchestrator

Update the orchestrator CLI (`src/pulsecraft/cli/main.py` or wherever `run-change` is defined) to accept a `--real-signalscribe` flag that wires in the real agent instead of the mock. Default remains mock (keeps existing tests working).

Something like:
```python
@app.command()
def run_change(
    fixture_path: Path,
    real_signalscribe: bool = typer.Option(False, "--real-signalscribe"),
    real_buatlas: bool = False,   # placeholder; implemented in prompt 06
    real_pushpilot: bool = False, # placeholder; implemented in prompt 07
): ...
```

If `--real-signalscribe` is passed, construct a real `SignalScribe` and pass it into the orchestrator. Mocks for BUAtlas and PushPilot still (will be replaced in prompts 06, 07).

### Step 5 — Tests

In `tests/unit/agents/` (new folder):

1. `test_signalscribe_unit.py`:
   - Mocks the Anthropic client (`unittest.mock.MagicMock` or `anthropic`'s test client if available)
   - Tests: constructor loads prompt from file; `invoke` parses valid response; invoke retries on malformed response; invoke raises `AgentOutputValidationError` after two failed validations; invoke raises `AgentInvocationError` after API retry exhaustion; contract adherence (returns ChangeBrief, decisions[] populated, agent name correct)
   - Does NOT make real API calls

In `tests/integration/agents/` (new folder):

2. `test_signalscribe_integration.py`:
   - Real Anthropic API calls
   - Skipped unless `PULSECRAFT_RUN_LLM_TESTS=1` is set or `--runslow` flag passed
   - Parametrized over all 8 fixtures
   - Each test: load fixture, invoke real SignalScribe, assert returned ChangeBrief validates against schema, assert decisions[] is non-empty, assert confidence is 0-1, assert sources citations are valid substrings of raw_text (this catches hallucinated citations)
   - Does NOT assert specific decision verbs — that's the eval script's job

Configure `pytest` to skip LLM integration tests by default. In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = ["llm: tests requiring real LLM calls"]
```
Use `@pytest.mark.llm` on integration tests. Only run them when explicitly requested.

### Step 6 — Eval script

Create `scripts/eval_signalscribe.py`. A standalone script (not a test) that:

1. Loads all 8 fixtures
2. Constructs a real `SignalScribe`
3. Invokes it on each fixture
4. Produces a report to stdout in this format:

```
SignalScribe Eval Report (model: claude-sonnet-4-6, date: 2026-04-22)

Fixture                           Expected chain                    Actual chain                     Status    Cost
--------------------------------  --------------------------------  --------------------------------  --------  ------
001 clearcut_communicate          COMMUNICATE→RIPE→READY            COMMUNICATE→RIPE→READY           ✅ match   $0.04
002 pure_internal_refactor        ARCHIVE                           ARCHIVE                           ✅ match   $0.03
003 ambiguous_escalate            ESCALATE or NEED_CLARIFICATION    ESCALATE                          ✅ match   $0.05
004 early_flag_hold_until         COMMUNICATE→HOLD_UNTIL            COMMUNICATE→HOLD_UNTIL           ✅ match   $0.04
005 muddled_need_clarification    COMMUNICATE→RIPE→NEED_CLARIF      COMMUNICATE→RIPE→NEED_CLARIF     ✅ match   $0.05
006 multi_bu_affected_vs_adjacent COMMUNICATE→RIPE→READY            COMMUNICATE→RIPE→READY           ✅ match   $0.04
007 mlr_sensitive                 COMMUNICATE→RIPE→READY            COMMUNICATE→RIPE→READY           ✅ match   $0.04
008 post_hoc_already_shipped      COMMUNICATE→RIPE→READY            COMMUNICATE→RIPE→READY           ✅ match   $0.04

Total cost: $0.33
Total latency: 24s

Detailed reasoning per fixture available in audit/<date>/<change_id>.jsonl

Items to review:
 - (none)   # or list mismatches
```

Expected chains come from `fixtures/changes/README.md` (the coverage table from prompt 03). Encode them in the script as a constant dict keyed by fixture filename.

Match status logic:
- ✅ exact match (same verbs, same order)
- 🟡 semantically close (different verb but same terminal category — e.g., ESCALATE vs. NEED_CLARIFICATION both end the pipeline at gate 1/3)
- ❌ mismatch (unexpected verb, likely a bug)

Script behavior:
- Never fails; always exits 0
- Writes a copy of the report to `audit/eval/signalscribe-<timestamp>.txt` for historical comparison
- Prints actionable guidance at the bottom: which fixtures look wrong and which are worth re-prompting vs. genuinely right

Run this script at the end of your session (in the verification step). Include the output in your final report.

### Step 7 — Update CLAUDE.md and planning index

Extend `CLAUDE.md`:

In the "Agents authored so far" section:
```markdown
## Agents authored so far

### SignalScribe (prompt 05)
- **Location:** `src/pulsecraft/agents/signalscribe.py`
- **Prompt:** `.claude/agents/signalscribe.md`
- **Owns gates:** 1, 2, 3
- **Protocol:** `SignalScribeProtocol` (see `orchestrator/agent_protocol.py`)
- **Model:** `claude-sonnet-4-6` via Anthropic API
- **Tools:** none yet (gate-3 clarification tools come later)
- **Eval script:** `scripts/eval_signalscribe.py`
```

Update "Current phase":
- Add ✅ 05 — SignalScribe agent (gates 1, 2, 3)
- Next → 06 — BUAtlas agent

Update the last-updated footer.

Update `design/planning/00-planning-index.md` similarly.

### Step 8 — Verify

Run in order:

1. `.venv/bin/ruff check .` — passes
2. `.venv/bin/ruff format --check .` — passes
3. `.venv/bin/mypy src/pulsecraft/agents/` — passes
4. `.venv/bin/pytest tests/ -v -m "not llm"` — all prior tests pass, new unit tests pass. Expect ~200-210 total (187 prior + ~15-20 new unit tests).
5. `.venv/bin/pytest tests/integration/agents/ -v -m llm` — with `PULSECRAFT_RUN_LLM_TESTS=1 .venv/bin/pytest ...`; 8 integration tests pass (each fixture produces a valid ChangeBrief).
6. `.venv/bin/python scripts/eval_signalscribe.py` — produces the eval report. Include output in your final report.
7. CLI smoke test with real SignalScribe: `.venv/bin/python -m pulsecraft run-change fixtures/changes/change_001_clearcut_communicate.json --real-signalscribe` — terminates in DELIVERED with real SignalScribe (mocks for BUAtlas/PushPilot).

If the eval report shows ❌ mismatches, **do not silently iterate the prompt until green**. Document the mismatches in the final report and flag them for user review. The user decides whether to tune the prompt in a follow-up pass.

If ≥6 of 8 fixtures match (✅ or 🟡), the agent is "good enough to hand to BUAtlas" and we can proceed to prompt 06. If <6 match, stop and ask the user before committing.

### Step 9 — Commit

Assuming eval is acceptable:

```
feat(agents): add SignalScribe — first real LLM-backed agent (prompt 05)

Implements decision gates 1, 2, 3 per design/planning/01-decision-criteria.md.
Model: claude-sonnet-4-6 via Anthropic API.

Files:
- .claude/agents/signalscribe.md — canonical prompt (N lines, mirrors decision criteria)
- src/pulsecraft/agents/signalscribe.py — SignalScribe class, Protocol-compliant
- scripts/eval_signalscribe.py — fixture-based eval report (not a test)
- tests/unit/agents/test_signalscribe_unit.py — mocked-client unit tests
- tests/integration/agents/test_signalscribe_integration.py — real-API tests (@pytest.mark.llm, skipped by default)
- pyproject.toml — pytest marker 'llm' registered

Orchestrator integration: CLI accepts --real-signalscribe flag; default still mock.

Eval results (see scripts/eval_signalscribe.py):
- [summarize: N/8 ✅ match, M/8 🟡 semantically close, K/8 ❌ mismatch]
- Total cost: $X.XX; total latency: Xs
- [list any mismatches worth reviewing]

Next: prompt 06 — BUAtlas (gates 4, 5, parallel per-BU).
```

Do not push to remote unless the user asks.

## Rules for this session

- **Do not invent Anthropic API specifics.** Use the current `anthropic` Python package API. If you're uncertain about a parameter name or model string, check the installed library (`.venv/bin/python -c "import anthropic; help(anthropic.Anthropic)"`) rather than guess. If the model string `claude-sonnet-4-6` doesn't work, try `claude-sonnet-4-5` or query the user; do not fabricate.
- **Do not weaken tests to make evals pass.** If the eval shows fixture 003 returning COMMUNICATE instead of ESCALATE, the prompt is wrong — flag it, don't adjust the expected chain to match.
- **Do not refactor the orchestrator.** Protocol compliance means Signal scribe plugs in without changes. If you find yourself wanting to modify `orchestrator/engine.py`, stop — something's off with the interface.
- **Do not change the decision criteria document** to match LLM behavior. The criteria are the spec; the LLM conforms to them, not vice versa. If the criteria are wrong, that's a separate prompt we discuss first.
- **Do not commit API keys or secrets.** Double-check `.gitignore` excludes `.env`.
- **Do not add new decision verbs.** The enum is closed; any new verb would break orchestrator logic silently.
- **Budget guard.** If total cost during this session exceeds $5, stop and ask the user before continuing. Normal expectation is $1-2.

## Final report

1. **Files created/modified** — full tree with line counts.
2. **Prompt length** (`.claude/agents/signalscribe.md`): X lines.
3. **Verification results** — each step pass/fail. Total tests before/after. LLM integration tests pass/fail.
4. **Eval report** — paste the full output of `scripts/eval_signalscribe.py`. Highlight mismatches with commentary on whether they look like prompt bugs or reasonable edge cases.
5. **Observations** — anything surprising about how SignalScribe reasoned on specific fixtures. These are the seeds of prompt iteration in the future.
6. **Total API cost incurred** during this session.
7. **Commit hashes** — both commits.
8. **Next prompt** — "Ready for prompt 06: BUAtlas (gates 4, 5)."

---

## [Post-commit] Save this prompt file to the repo

After the main commit lands, ask the user: **"Save this prompt file (prompt 05) to `prompts/05-agent-signalscribe.md` as a commit archive? (yes/no)"**

If yes:
- Write the prompt content verbatim to `prompts/05-agent-signalscribe.md`.
- Commit with: `chore(prompts): archive prompt 05 (SignalScribe) in repo`.

If no: skip.
