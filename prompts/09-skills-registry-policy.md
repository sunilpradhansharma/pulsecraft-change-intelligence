# Prompt 09 — Registry, Policy, and Audit Skills

> **Character.** Pure refactor. Extract inline logic that lives inside `engine.py` into reusable skills under `src/pulsecraft/skills/`. Introduce one new skill for past-engagement lookups. No behavior changes — every test that passes today must still pass after.
>
> **Why this matters.** Until now the orchestrator has carried a lot of logic inline: BU candidate selection, HITL trigger evaluation, dedupe-key computation, audit writes. As we add hooks (prompt 12) and operator commands (prompt 11), those same pieces get called from multiple places. Skills make them first-class.
>
> **How to use.** Paste below the `---` line into Claude Code.
>
> **Expected duration:** 2–3 hours.
>
> **Prerequisite:** Prompts 00–08 done. 390 tests passing. CLI working with `run-change` and `ingest` subcommands.
>
> **Budget:** Zero API cost. Pure engineering.

---

# Instructions for Claude Code

You are extracting **four families of logic** from the orchestrator engine into reusable skills: BU registry lookup, policy checking, dedupe-key computation, and audit writing. Plus a new skill for past-engagement lookups that will feed BUAtlas. No LLM calls.

This is a **refactor**, not a feature. The bar is: no observable behavior change. Every existing test must still pass. New tests cover the extracted skills.

## Environment discipline

`.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/mypy`. `uv run <cmd>` acceptable.

## Context to read

1. **`src/pulsecraft/orchestrator/engine.py`** — most of the logic to be extracted lives here. Understand what's there first.
2. **`src/pulsecraft/orchestrator/audit.py`** — already a module; likely just needs re-exporting as a skill and maybe a thin wrapper.
3. **`src/pulsecraft/orchestrator/hitl.py`** — understand how policy-triggered HITL currently works.
4. **`config/bu_registry.yaml`** — the data the registry skill reads.
5. **`config/policy.yaml`** — thresholds and HITL triggers the policy skill checks.
6. **`config/channel_policy.yaml`** — where dedupe config lives.
7. **`src/pulsecraft/schemas/`** — contracts.
8. **`tests/unit/orchestrator/test_policy_enforcement.py`** — behavior the skill must continue to produce.

If anything in this prompt conflicts with the decision criteria, the decision criteria wins.

## What "done" looks like

When you finish:

1. **Four skill modules** in `src/pulsecraft/skills/`:
   - `registry.py` — `lookup_bu_candidates(change_brief, registry) -> list[BUProfile]`
   - `policy.py` — `evaluate_hitl_triggers(personalized_briefs, policy, channel_policy) -> list[HITLTrigger]`, `check_confidence_threshold(decision, policy) -> bool`, `check_restricted_terms(text, policy) -> list[RestrictedTermHit]`
   - `dedupe.py` — `compute_dedupe_key(change_id, bu_id, recipient_id, message_variant) -> str`, `has_recent_duplicate(key, audit_reader, window_hours) -> bool`
   - `audit_skill.py` — thin wrapper over `audit.AuditWriter` exposing `write_audit(record)` for use in hooks and commands (same instance reused across the process)
2. **One new skill** `src/pulsecraft/skills/past_engagement.py` — `lookup_past_engagement(bu_id, recipient_id, audit_reader) -> PastEngagement | None`. Reads recent audit records to reconstruct engagement history. Stub-safe when audit is empty.
3. **`src/pulsecraft/orchestrator/engine.py` refactored** — the inline logic now calls into these skills. No duplicate implementations.
4. **Tests**:
   - `tests/unit/skills/test_registry.py` — BU candidate selection works across multiple ChangeBrief shapes
   - `tests/unit/skills/test_policy.py` — HITL triggers fire correctly, confidence thresholds applied, restricted terms detected
   - `tests/unit/skills/test_dedupe.py` — key determinism, window behavior
   - `tests/unit/skills/test_past_engagement.py` — reads audit records, handles empty audit gracefully
5. **All 390 prior tests still pass.** This is the load-bearing guarantee — refactor must not change behavior.
6. **CLAUDE.md** Skills section updated with these four new skills.
7. **Planning index** updated.
8. One feature commit + optional archive commit.

## Design principles

1. **No behavior change.** The test suite is the contract. If a test fails after refactor, something changed. Fix the refactor, not the test.
2. **Skills are pure-ish functions.** `lookup_bu_candidates(change_brief, registry)` — no hidden state, no globals. Config passed as argument (or loaded explicitly at the top of the call chain, not inside the skill).
3. **Skills don't own their inputs.** `lookup_bu_candidates` doesn't call `get_bu_registry()` internally — it takes the registry as a parameter. Same for policy, same for audit. The orchestrator loads config once and passes into skills. This makes skills test-friendly and reusable.
4. **Skills can be composed.** `evaluate_hitl_triggers` might call `check_restricted_terms` internally. That's fine — skills calling skills is the point.
5. **No new dependencies.** Use what's already in pyproject.toml.
6. **Audit reads use the existing AuditWriter.read_chain** (from prompt 04). Don't reimplement.
7. **Don't add features via refactor.** If you notice a missing check or a better HITL rule, flag it in the final report rather than adding it here. Behavior neutrality is the invariant.

## Step-by-step work

### Step 1 — Pre-flight

1. `git status` clean. Latest commit is prompt 08's feature + archive.
2. `.venv/bin/pytest tests/ -q -m "not llm"` shows 390 passing.
3. Read the 8 context files. Specifically locate inside `engine.py`:
   - The BU candidate-selection logic (likely a function or inline block that consults `bu_registry` with `change_brief.impact_areas`)
   - The HITL trigger evaluation (where it decides to transition to `AWAITING_HITL`)
   - Dedupe key computation (likely in the PushPilot handoff path)
   - Audit writes (already uses `AuditWriter` — just need to expose the skill wrapper)
   - Restricted-term checks (likely inline in policy evaluation)
   - Confidence-threshold checks (likely in policy evaluation)

Make a short list: filename + line range + what it does. This is your extraction plan.

### Step 2 — Author `src/pulsecraft/skills/registry.py`

```python
from pulsecraft.schemas.change_brief import ChangeBrief
from pulsecraft.schemas.bu_profile import BUProfile
from pulsecraft.schemas.bu_registry import BURegistry  # if it exists; else use the yaml-backed type

def lookup_bu_candidates(
    change_brief: ChangeBrief,
    registry: BURegistry,
    *,
    recall_biased: bool = True,
) -> list[BUProfile]:
    """Return BU profiles whose owned_product_areas or keywords intersect change_brief.impact_areas.

    Recall-biased: when in doubt, include. BUAtlas (gate 4) applies precision.
    """
    ...
```

Implementation:
- For each BU in the registry, check whether any of its `owned_product_areas` or `keywords` appears in `change_brief.impact_areas` (normalization: lowercase + substring match for keywords; exact match for owned_product_areas).
- Return matching BUs as a list of `BUProfile` objects (look up the profile by `bu_id` — the registry and profiles are separate files).
- If no matches → return empty list.
- Preserve any behavior the current orchestrator has. If the current matching is case-sensitive exact, keep it case-sensitive exact.

### Step 3 — Author `src/pulsecraft/skills/policy.py`

Multiple functions; one file:

```python
def check_confidence_threshold(
    decision: Decision,
    policy: Policy,
) -> bool:
    """True if decision's confidence meets the policy threshold for its gate+verb combination.
    False if below threshold (caller may route to HITL).
    """
    ...

def check_restricted_terms(
    text: str,
    policy: Policy,
) -> list[RestrictedTermHit]:
    """Scan text for any phrase from policy.restricted_terms. Return list of hits
    (category + term + character position).
    Categories: commitments_and_dates, scientific_communication, sensitive_data_markers.
    """
    ...

def evaluate_hitl_triggers(
    personalized_briefs: list[PersonalizedBrief],
    policy: Policy,
    channel_policy: ChannelPolicy,
) -> list[HITLTrigger]:
    """Aggregate HITL triggers across all briefs. Returns empty list if no triggers.

    Triggers checked:
    - Any gate escalate in decisions[]
    - gate_3 NEED_CLARIFICATION or UNRESOLVABLE
    - Confidence below threshold on any decision
    - Priority P0
    - Draft contains commitment/date (check against policy.restricted_terms.commitments_and_dates)
    - Restricted term hit on scientific_communication (MLR)
    - Restricted term hit on sensitive_data_markers (hard-block)
    - Second WEAK on gate 5
    """
    ...
```

Define `RestrictedTermHit` and `HITLTrigger` as small Pydantic models in `src/pulsecraft/schemas/` if they don't exist yet. Keep them minimal.

### Step 4 — Author `src/pulsecraft/skills/dedupe.py`

```python
def compute_dedupe_key(
    change_id: str,
    bu_id: str,
    recipient_id: str,
    message_variant_id: str,
) -> str:
    """Deterministic hash of the four inputs. Stable across replays. Returns hex string."""
    ...

def has_recent_duplicate(
    dedupe_key: str,
    audit_reader: AuditReader,
    window_hours: int,
) -> bool:
    """True if a delivery_attempt audit record with the same dedupe_key occurred in the last `window_hours`."""
    ...
```

`AuditReader` is a protocol / wrapper around `AuditWriter.read_chain`. If one doesn't exist, define it minimally in `audit.py` and re-export through `audit_skill.py`.

### Step 5 — Author `src/pulsecraft/skills/audit_skill.py`

Thin wrapper:

```python
"""Public skill API for audit writes. Use this in hooks and commands
rather than instantiating AuditWriter directly."""

from pulsecraft.orchestrator.audit import AuditWriter, AuditRecord

# Shared instance, constructed by the orchestrator and injected.
# Skills should receive the writer as a parameter, not reach for a global.
```

Re-exports the types and writer class. The skills that need to write audit take an `AuditWriter` parameter — they don't create their own. This keeps the no-global-state invariant.

### Step 6 — Author `src/pulsecraft/skills/past_engagement.py`

```python
def lookup_past_engagement(
    bu_id: str,
    recipient_id: str,
    audit_reader: AuditReader,
    *,
    lookback_days: int = 90,
) -> PastEngagement | None:
    """Reconstruct past engagement from audit records.

    Returns PastEngagement with:
    - notification_count_last_7d: int
    - notification_count_last_30d: int
    - last_sent_at: datetime | None
    - useful_feedback_ratio: float | None (if feedback events exist)

    Returns None if no engagement records exist for this (bu_id, recipient_id) pair.
    """
    ...
```

`PastEngagement` should already exist in schemas from prompt 04 (I asked Claude Code to add it minimally). If it doesn't or is too sparse, extend it conservatively. Flag any additions in the final report.

### Step 7 — Refactor `src/pulsecraft/orchestrator/engine.py`

Now the careful part. For each extracted piece of logic in `engine.py`:

1. Replace the inline implementation with a call to the new skill.
2. Pass config (registry, policy, channel_policy) as parameters to the skill.
3. Keep the orchestrator responsible for: sequencing, state transitions, audit-record construction, error handling. *The skill returns data; the orchestrator acts on it.*
4. Do not collapse orchestrator-level concerns into skills. If the orchestrator was writing an audit record after a policy check, keep that audit write in the orchestrator (it's the orchestrator's role to audit state transitions).

After each extraction, run `.venv/bin/pytest tests/ -q -m "not llm"` immediately. If any test fails, the refactor changed behavior — revert that piece, understand why, retry.

Do extractions in this order (smallest to biggest risk):

1. **Dedupe key computation** — probably just a helper function; low risk
2. **Restricted-term checks** — pure function, easy to extract
3. **Confidence threshold checks** — pure function
4. **BU candidate selection** — moderate risk; touches the impact_areas → registry matching we fixed in 07.7
5. **HITL trigger evaluation** — highest risk; aggregates multiple checks

After each of the five, verify tests still pass before moving to the next.

### Step 8 — Write tests for the new skills

Unit tests for each new skill module. Each test file covers:

- **`test_registry.py`**: empty impact_areas → empty list; single-term match → correct BU; multi-term spanning multiple BUs → all match; no match → empty list.
- **`test_policy.py`**: confidence above threshold → true; below → false; restricted-term hit across each of the three categories; HITL trigger firing for each type (escalate, need_clarification, p0, commitment, mlr, sensitive_data, weak_twice); no triggers → empty list.
- **`test_dedupe.py`**: same inputs produce same hash; different inputs produce different hashes; recent duplicate detected in window; older duplicate not detected.
- **`test_past_engagement.py`**: empty audit → None; some records → counts correct; lookback_days respected.

Aim for ~30-40 new unit tests across these four files.

### Step 9 — Verify no behavior change

1. `.venv/bin/ruff check .` passes
2. `.venv/bin/ruff format --check .` passes
3. `.venv/bin/mypy src/pulsecraft/` passes
4. `.venv/bin/pytest tests/ -v -m "not llm"` → **all 390 prior tests pass, plus the ~30-40 new skill tests**. If any prior test fails, the refactor broke something — stop, diagnose, do not commit.
5. Re-run the CLI smoke test: `.venv/bin/pulsecraft run-change fixtures/changes/change_001_clearcut_communicate.json` → terminates correctly
6. Re-run with real agents: `.venv/bin/pulsecraft run-change fixtures/changes/change_001_clearcut_communicate.json --real-signalscribe --real-buatlas --real-pushpilot` — should produce the same behavior as before prompt 09 (AWAITING_HITL as we verified in 07.7). One run is enough; just confirming no regression.

**Do not commit if any prior test fails.**

### Step 10 — Update CLAUDE.md

In **"Skills authored so far"**, append:

```markdown
### Registry / policy / audit skills (prompt 09)
Location: `src/pulsecraft/skills/`

| Skill | Purpose | Inputs |
|---|---|---|
| lookup_bu_candidates | BU pre-filter: intersect ChangeBrief.impact_areas with registry | ChangeBrief, BURegistry |
| check_confidence_threshold | Compare a Decision's confidence against policy threshold | Decision, Policy |
| check_restricted_terms | Scan text for commitment/MLR/sensitive-data phrases | str, Policy |
| evaluate_hitl_triggers | Aggregate all HITL triggers across PersonalizedBriefs | list[PersonalizedBrief], Policy, ChannelPolicy |
| compute_dedupe_key | Deterministic hash for (change, BU, recipient, variant) | 4 strings |
| has_recent_duplicate | Audit-log lookup for recent deliveries with same key | dedupe_key, AuditReader, window |
| write_audit | Skill wrapper over AuditWriter (for use in hooks) | AuditRecord, AuditWriter |
| lookup_past_engagement | Reconstruct PastEngagement from audit history | bu_id, recipient_id, AuditReader |

Called from: orchestrator (engine.py), hooks (prompt 12), operator commands (prompt 11).
```

Update **"Current phase"** — add `✅ 09 — Registry, policy, audit skills`. Next → `⏳ 10 — Delivery skills`.

Update last-updated footer.

### Step 11 — Update planning index

Add row to workflow table:
```
| 09 | prompts/09-skills-registry-policy.md | Registry, policy, audit skills — extracted from engine.py | ✅ Done |
```

Add entry to Completed Artifacts referring to the new skills directory.

### Step 12 — Commit

```
refactor(skills): extract registry, policy, dedupe, audit skills from engine.py — prompt 09

New skills (src/pulsecraft/skills/):
- registry.py — lookup_bu_candidates (BU pre-filter)
- policy.py — check_confidence_threshold, check_restricted_terms, evaluate_hitl_triggers
- dedupe.py — compute_dedupe_key, has_recent_duplicate
- audit_skill.py — thin wrapper over AuditWriter for use in hooks
- past_engagement.py — lookup_past_engagement (reads audit history)

Refactor: inline logic in src/pulsecraft/orchestrator/engine.py now calls these
skills. Zero behavior changes. All 390 prior tests pass. ~30-40 new unit tests
added for the skills themselves.

Design: skills are pure-ish functions; config passed as parameter, no hidden
state. Composable (skills call skills). Callable from orchestrator, hooks
(prompt 12), and operator commands (prompt 11).

No LLM calls in this prompt. Zero API cost.

Next: prompt 10 — delivery skills (render + channel adapters).
```

Do not push to remote unless user asks.

## Rules for this session

- **No behavior change.** If a prior test fails, something broke. Fix it.
- **No new dependencies.** Use what's in pyproject.toml.
- **No adding checks during refactor.** If you notice a missing HITL trigger, flag it in the final report. Do not add it here.
- **Skills take config as parameter.** No global `get_policy()` inside skills.
- **Skills can call skills.** Composition is fine.
- **Do not inline more than is already inlined.** The refactor reduces inline code; it doesn't move more code inline.
- **If engine.py resists refactoring cleanly** (e.g., logic is too entangled to extract without behavior change), stop and ask. Better to leave one piece inline than to break tests silently.

## Final report

1. **Files created/modified** — full tree with line counts. Highlight the `engine.py` diff size — it should shrink meaningfully.
2. **Verification results** — each step pass/fail. Explicitly confirm 390 prior tests still pass.
3. **Extraction order** — the sequence you extracted in. Any extractions that required revert-and-retry should be flagged.
4. **Test count before/after** (390 → ~420-430 expected).
5. **Any observations** — behavior quirks you noticed that were worth preserving, small bugs you *noticed* but didn't fix (for future follow-up).
6. **Commit hashes** — two.
7. **Next:** "Ready for prompt 10: delivery skills."

---

## [Post-commit] Save this prompt file to the repo

After the main commit lands: **"Save prompt 09 to `prompts/09-skills-registry-policy.md`? (yes/no)"**

If yes: write verbatim, commit with `chore(prompts): archive prompt 09 (registry/policy/audit skills) in repo`.

If no: skip.
