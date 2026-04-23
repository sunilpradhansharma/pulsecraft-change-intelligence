# Synthetic Change Fixtures

Used for dev and eval. No real data. All content is synthetic — no real enterprise system names, product names, or personnel.

| Fixture | Scenario | Decision pattern target |
|---|---|---|
| 001 | Clear-cut communicate | COMMUNICATE → RIPE → READY → AFFECTED (bu_alpha) / NOT_AFFECTED (others) → WORTH_SENDING → SEND_NOW |
| 002 | Pure internal refactor | ARCHIVE (gate 1) |
| 003 | Ambiguous scope | ESCALATE (gate 1) or NEED_CLARIFICATION (gate 3) |
| 004 | Early flag, no ramp schedule | COMMUNICATE → HOLD_UNTIL (gate 2: too early for 2% internal) |
| 005 | Muddled release note | COMMUNICATE → RIPE → NEED_CLARIFICATION (gate 3: scope unclear) |
| 006 | Multi-BU: affected vs adjacent | AFFECTED for bu_zeta (owns reporting_dashboard); ADJACENT for bu_delta (incidental use) |
| 007 | MLR-sensitive content | Triggers MLR review flag via restricted terms ("safety profile", "efficacy") → HITL |
| 008 | Post-hoc already shipped | COMMUNICATE → RIPE → READY → AFFECTED (bu_epsilon) → WORTH_SENDING → DIGEST (P2 awareness) |

These scenarios cover the decision-verb space. The eval harness (prompt 14)
encodes expected outcomes as assertions; these fixtures are the inputs.

## Source type coverage

| Source type | Fixtures | v1 status |
|---|---|---|
| release_note | 001, 003, 006, 007 | covered |
| jira_work_item | 002, 008 | covered |
| ado_work_item | 005 | covered |
| feature_flag | 004 | covered |
| doc | — | out-of-scope for v1 fixture set |
| incident | — | out-of-scope for v1 fixture set |

`doc` and `incident` are explicitly deferred — no scenarios in the v1 eval set require them.
Candidate scenarios for a future prompt: incident post-mortem requiring retrospective BU notification;
internal wiki doc flagging a regulatory process change.
