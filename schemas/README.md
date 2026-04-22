# schemas/

JSON Schema files (draft 2020-12) that define the **wire-format contracts** at every agent boundary in PulseCraft. Each schema has a matching Pydantic v2 model in `src/pulsecraft/schemas/`.

---

## The decisions[] invariant

Every schema that is the **output of an agent** (ChangeBrief, PersonalizedBrief, DeliveryPlan) carries a `decisions[]` array. This array is the first-class decision trail — it lets `/explain <change-id>` reconstruct the full chain of gate decisions for any change event, without hitting external systems.

Each entry in `decisions[]` references `decision.schema.json` via `$ref` and carries:
- `gate` (1-6), `verb` (enum — the specific decision), `reason` (why), `confidence` (0.0-1.0)
- `decided_at` (ISO-8601 UTC), `agent` (name + version), `payload` (verb-specific extra data)

---

## Contract table

| Schema | Producer | Consumer | Pydantic model |
|---|---|---|---|
| `change_artifact.schema.json` | Ingest adapters | SignalScribe | `src/pulsecraft/schemas/change_artifact.py` |
| `change_brief.schema.json` | SignalScribe | Orchestrator → BUAtlas | `src/pulsecraft/schemas/change_brief.py` |
| `personalized_brief.schema.json` | BUAtlas (per BU, parallel) | Orchestrator → PushPilot / HITL | `src/pulsecraft/schemas/personalized_brief.py` |
| `delivery_plan.schema.json` | PushPilot + code | Delivery adapters | `src/pulsecraft/schemas/delivery_plan.py` |
| `bu_profile.schema.json` | BU registry config | BUAtlas (read-only) | `src/pulsecraft/schemas/bu_profile.py` |
| `audit_record.schema.json` | Every hook + agent | Audit log | `src/pulsecraft/schemas/audit_record.py` |
| `decision.schema.json` | Referenced by the three agent schemas above | N/A — sub-schema only | `src/pulsecraft/schemas/decision.py` |

---

## Schema summaries

### `change_artifact.schema.json`
Normalized change artifact — the ingest adapter's output. Same shape regardless of source (release note, Jira/ADO work item, doc, feature flag, incident). All content has been redacted of PII, PHI, and secrets by the ingest hook before this schema is populated. Does not carry `decisions[]` — no agent has processed it yet.

### `change_brief.schema.json`
SignalScribe's structured interpretation. Carries `decisions[]` from gates 1-3:
- Gate 1 — COMMUNICATE / ARCHIVE / ESCALATE
- Gate 2 — RIPE / HOLD_UNTIL / HOLD_INDEFINITE
- Gate 3 — READY / NEED_CLARIFICATION / UNRESOLVABLE

Contains: summary, before/after state, change_type, impact_areas, affected_segments, timeline, actions, risks, mitigations, FAQ, source citations, confidence score.

### `personalized_brief.schema.json`
BUAtlas's per-BU output. One instance per candidate BU per change event (produced in parallel). Carries `decisions[]` from gates 4-5:
- Gate 4 — AFFECTED / ADJACENT / NOT_AFFECTED
- Gate 5 — WORTH_SENDING / WEAK / NOT_WORTH

Contains: relevance verdict, priority, why_relevant, recommended_actions, assumptions, message_variants (push/teams/email), message_quality self-assessment.

### `delivery_plan.schema.json`
PushPilot's gate 6 output plus deterministic delivery metadata. Carries `decisions[]` from gate 6:
- Gate 6 — SEND_NOW / HOLD_UNTIL / DIGEST / ESCALATE

Contains: delivery decision, channel, scheduled_time, reason, dedupe_key, policy_check result, retry_policy. Dedupe key is SHA-256 of `(change_id + bu_id + recipient_id + message_variant_id)` — stable across replays.

### `bu_profile.schema.json`
BU configuration. Read-only input to BUAtlas. No PII by contract — all `name` values are display names only. Contains: BU identity, head/delegate info, owned product areas, delivery preferences, quiet hours, active initiatives, escalation contact.

### `audit_record.schema.json`
Append-only log entry for every auditable event. No PII anywhere — `output_summary` is a structured summary, never a raw LLM response. Contains: event_type, actor, action, input_hash (SHA-256, never raw input), output_summary, optional inline decision, optional metrics, outcome.

### `decision.schema.json`
Sub-schema for a single gate decision. Referenced via `$ref` from ChangeBrief, PersonalizedBrief, and DeliveryPlan. Defines the complete set of decision verbs (COMMUNICATE, ARCHIVE, ESCALATE, RIPE, HOLD_UNTIL, HOLD_INDEFINITE, READY, NEED_CLARIFICATION, UNRESOLVABLE, AFFECTED, ADJACENT, NOT_AFFECTED, WORTH_SENDING, WEAK, NOT_WORTH, SEND_NOW, DIGEST) and the `payload` extension point for verb-specific data.

---

## Nullability convention

Optional fields that are absent when not applicable use `"type": ["X", "null"]` in the JSON schema and `X | None = None` in the Pydantic model. Required fields that can legitimately be null use `oneOf: [{type: "null"}, ...]`. Fields are included as `null` in the wire format (rather than being omitted) to preserve forward-compatibility.

---

## Regenerating validation tests after schema changes

When a schema changes:

1. Update the JSON schema file in `schemas/`.
2. Update the matching Pydantic model in `src/pulsecraft/schemas/`.
3. Update the minimal-valid fixture in `tests/fixtures/schemas/minimal_valid/` if the change adds or removes required fields.
4. Run: `pytest tests/unit/schemas/ -v` — all 4 test modules must pass.
5. Run: `python -c "import json, jsonschema; [jsonschema.Draft202012Validator.check_schema(json.loads(open(f).read())) for f in ['schemas/change_artifact.schema.json', ...]]; print('ok')"` to validate the schema itself.
6. If `DecisionVerb` enum changes, `test_schema_enums.py` will catch drift between Python and JSON.
7. If gate-to-verb mapping changes, update the hardcoded mapping in `test_decision_verb_per_gate.py` and the decision criteria doc simultaneously.
