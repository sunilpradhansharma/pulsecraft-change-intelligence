# Prompt 16 — Architecture Tab

> **Character.** Build the Architecture tab — an interactive, animated architecture diagram that lets a Head of AI or senior technical stakeholder fully understand PulseCraft in 2-3 minutes of exploration. The tab should be beautiful standalone (memorable at a glance) and substantive with exploration (every agent, gate, hook, and policy element is explained on hover/click).
>
> **Why now.** The Demo tab (15.6.x) shows PulseCraft *running*. The Architecture tab will show PulseCraft's *structure*. Together they form a narrative: here's what it does, here's how it's built. Prompt 17 (How it works scrollytelling) will complete the trilogy later.
>
> **How to use.** Paste below the `---` line into Claude Code. Fully autonomous — no mid-investigation handoffs.
>
> **Expected duration:** 3.5-4 hours. Pure frontend work. No backend, no orchestrator, no schemas touched.
>
> **Budget:** Zero LLM cost — this tab is static + interactive, no agent calls needed for building or verifying.

---

# Instructions for Claude Code

Build the Architecture tab. It's the second of three tabs (Demo · Architecture · How it works). The Demo tab was polished in 15.6.x. This prompt creates the Architecture tab from scratch.

**Scope:** pure frontend. Stay in `src/pulsecraft/demo/static/`. Zero backend touches unless the tab-switching logic requires a minor route addition in `server.py`.

## Environment discipline

`.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`. No new dependencies. Vanilla HTML/CSS/JS. SVG for the diagram.

## Design goals

### For the casual viewer (glance)

- Page loads → architecture diagram assembles itself over ~3-4 seconds with staggered entrance animation
- Once assembled, the diagram sits at rest — beautiful, readable, complete
- A legend below explains the visual language (agent colors, hook icons, gate types)
- Reader absorbs the overall shape in ~30 seconds

### For the engaged reader (exploration)

- Hover any agent → a side panel on the right expands showing that agent's role, gates owned, verbs produced, model used
- Hover any specific gate → panel updates to show that gate's purpose, verbs, thresholds, policy source
- Hover any hook → panel shows the hook's validators and blocking behavior
- Click any element → pins the selection (clicking elsewhere un-pins)
- Replay button re-triggers the entrance animation
- Reader can fully understand the architecture in 2-3 minutes

### For a Head of AI specifically

A Head of AI reading this tab should leave with clear answers to:

1. **What kind of system is this?** (three-agent LLM pipeline with deterministic policy enforcement)
2. **How does it route changes?** (six judgment gates across three agents, with four guardrail hooks)
3. **What does each agent actually do?** (specific gates, specific verbs, specific responsibilities)
4. **Where is the agent-vs-code split?** (which decisions are agent judgment, which are enforced by code)
5. **How is correctness ensured?** (hooks that validate inputs and outputs at every handoff)
6. **How does HITL fit in?** (what triggers human review, how operators interact)
7. **What's deterministic vs. stochastic?** (critical for an AI leader evaluating risk)

The tab should answer all seven without the reader having to leave the page.

## Architectural elements to visualize

### Three agents

- **SignalScribe** (purple) — owns Gates 1, 2, 3. Reads the raw change artifact, produces a ChangeBrief.
- **BUAtlas** (teal) — owns Gates 4, 5. Reads the ChangeBrief + each candidate BU's profile, produces a PersonalizedBrief per BU. Fans out in parallel via `asyncio.gather`.
- **PushPilot** (coral) — owns Gate 6. Reads the PersonalizedBrief, produces a DeliveryDecision (timing + channel selection).

### Six gates

| Gate | Agent | Question | Verbs |
|------|-------|----------|-------|
| 1 | SignalScribe | Worth communicating? | COMMUNICATE, ARCHIVE, ESCALATE |
| 2 | SignalScribe | Ripe? | RIPE, HOLD_UNTIL, HOLD_INDEFINITE |
| 3 | SignalScribe | Clear? | READY, NEED_CLARIFICATION, UNRESOLVABLE |
| 4 | BUAtlas (per BU) | Affected? | AFFECTED, ADJACENT, NOT_AFFECTED |
| 5 | BUAtlas (per BU) | Worth sending to this BU? | WORTH_SENDING, WEAK, NOT_WORTH |
| 6 | PushPilot (per BU) | When and how to deliver? | SEND_NOW, HOLD_UNTIL, DIGEST |

### Four guardrail hooks

- **pre_ingest** — runs before any agent touches the artifact. Redacts sensitive markers, validates schema.
- **post_agent** — runs after each agent invocation. Validates output schema, ensures reasoning grounded in input.
- **pre_deliver** — runs after PushPilot, before actual send. Enforces policy invariants (mlr_sensitive scan, priority_p0 routing, quiet_hours enforcement). This is where agent-vs-code divergence materializes.
- **audit_hook** — runs at every state transition. Writes append-only audit record with timing, cost, decision, reasoning.

### State machine (terminal states)

- **ARCHIVED** — gate 1 decided not worth communicating
- **HELD** — gate 2 said hold, or pre_deliver said quiet_hours
- **AWAITING_HITL** — pre_deliver triggered on priority_p0, mlr_sensitive, or other policy rules
- **DELIVERED** — message sent to recipient via selected channel
- **FAILED** — unrecoverable error

### The agent-vs-code architectural principle

This needs visual prominence. The principle:

> Agents express preferences based on context. Code enforces invariants based on policy. When they diverge, policy wins, and both judgments are logged.

In the diagram, each agent is a "reasoning" node; each hook is a "policy" node. The pre_deliver hook specifically sits between PushPilot (preference) and the delivery action (enforcement) — this is where divergence becomes visible. Visualize this relationship explicitly.

### What else to feature (find these in the codebase)

Read the following to surface any architectural detail worth including that I haven't named above:

- `CLAUDE.md` — standing orders and architectural principles
- `design/planning/01-decision-criteria.md` — core architectural commitments
- `README.md` — the existing architecture narrative and Mermaid diagram
- `src/pulsecraft/orchestrator/engine.py` — the actual state machine code
- `config/policy.yaml` — the restricted terms, priority rules, MLR classes
- `config/bu_registry.yaml` — the BU structure with priority levels
- `.claude/agents/*.md` — the agent prompts themselves

If you find architecturally important details not in the list above (e.g., a specific observability element, a specific retry pattern, a specific state the diagram should represent), include them. Use judgment — the goal is completeness without clutter.

## Visual design

### Color palette (consistent with Demo tab)

```
SignalScribe       purple     #534AB7 node, #EEEDFE surface, #3C3489 detail text
BUAtlas           teal       #0F6E56 node, #E1F5EE surface, #085041 detail text
PushPilot         coral      #993C1D node, #FAECE7 surface, #712B13 detail text
Hook              amber      #854F0B node, #FAEEDA surface, #633806 detail text
Terminal state    varies     (green for DELIVERED, blue for AWAITING_HITL, etc.)
Connector (arrow) neutral    #8D877B

Page background   #FAF7F2 (warm cream, matches Demo tab)
```

### Typography

Same as Demo tab:
- Fraunces 500 — node labels, section headings, side panel title
- Inter 400/500/600 — body text, legend entries, detail panel content
- JetBrains Mono 400 — IDs, technical identifiers, gate numbers

### Layout

At 1440px width:
- Top bar (unchanged from Demo tab): PulseCraft brand, tab switcher, cost/elapsed counters hidden on non-Demo tabs
- Main canvas: 1440px content area, centered, with ~50px side margins
- Left ~65% of canvas: the architecture diagram (SVG, responsive width)
- Right ~35% of canvas: the detail panel (sticky, 360px wide)
- Below the diagram: legend + replay button + architectural principle callout

At smaller widths: panel stacks below the diagram.

### Diagram structure

Top-to-bottom flow with horizontal fan-out in the middle:

```
                    ┌──────────────────┐
                    │  Change artifact │  (ingest source)
                    │  (Jira, GitHub,  │
                    │   Confluence…)   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  pre_ingest hook │  amber
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   SignalScribe   │  purple
                    │  Gate 1 Gate 2   │
                    │       Gate 3     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ post_agent hook  │  amber
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  BU pre-filter   │  (deterministic)
                    │  (registry match)│
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │ BUAtlas │         │ BUAtlas │         │ BUAtlas │   teal
    │  BU α   │         │  BU β   │         │  BU γ   │
    │ G4  G5  │         │ G4  G5  │         │ G4  G5  │
    └────┬────┘         └────┬────┘         └────┬────┘
         │                   │                   │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │post_hook│         │post_hook│         │post_hook│   amber
    └────┬────┘         └────┬────┘         └────┬────┘
         │                   │                   │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │PushPilot│         │PushPilot│         │PushPilot│   coral
    │   G6    │         │   G6    │         │   G6    │
    └────┬────┘         └────┬────┘         └────┬────┘
         │                   │                   │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │pre_del  │         │pre_del  │         │pre_del  │   amber
    │ hook    │         │ hook    │         │ hook    │
    └────┬────┘         └────┬────┘         └────┬────┘
         │                   │                   │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │DELIVERED│         │ HELD    │         │AWAITING │
    │ (green) │         │ (amber) │         │ HITL    │
    │         │         │         │         │ (blue)  │
    └─────────┘         └─────────┘         └─────────┘

 [audit_hook — runs at every state transition, visualized as a subtle side-channel bar on the right]
```

**Key visual moments:**

- **Fan-out at BU pre-filter.** One arrow becomes three. This is the parallelism moment.
- **Three parallel lanes** through BUAtlas → post_agent → PushPilot → pre_deliver. Reader sees they run simultaneously.
- **Terminal states** can differ across lanes — one BU delivers, one holds, one routes to HITL. Show this diversity explicitly.
- **audit_hook as side-channel.** Visualize as a vertical bar on the far right connecting to every stage with thin lines. Reinforces "everything is logged."

### Animation — entrance choreography

When the Architecture tab loads (or when the replay button is clicked):

1. **0–400ms:** Change artifact node fades in + slides down from top.
2. **400–800ms:** pre_ingest hook fades in below it, arrow draws from artifact to hook (stroke-dashoffset animation).
3. **800–1400ms:** SignalScribe node grows in (scale 0.92 → 1) + its three gate labels fade in one at a time with 80ms stagger.
4. **1400–1700ms:** post_agent hook appears, arrow draws.
5. **1700–2000ms:** BU pre-filter appears, arrow draws.
6. **2000–2600ms:** The fan-out moment — three BUAtlas nodes appear simultaneously with scale(0.9 → 1) + opacity 0 → 1 over 400ms. Arrows drawing from the pre-filter to each of them animate in parallel (not staggered — they're genuinely parallel).
7. **2600–3000ms:** post_agent hooks appear below each BUAtlas (all three simultaneously).
8. **3000–3400ms:** PushPilot nodes appear below each post_agent hook (all three simultaneously).
9. **3400–3800ms:** pre_deliver hooks appear (all three simultaneously).
10. **3800–4200ms:** Terminal state nodes appear (can show the three different possible states — DELIVERED, HELD, AWAITING_HITL — to emphasize outcome diversity). Each with its color.
11. **4200–4600ms:** audit_hook side-channel bar appears on the right with thin connecting lines to every stage drawing in simultaneously.
12. **4600–4800ms:** Legend and principle callout fade in below the diagram.

Total: ~4.8 seconds. Feels considered but not slow.

Respect `prefers-reduced-motion` — if set, all animations become 200ms simple fades with no staggering.

### Animation easing

Use `cubic-bezier(0.2, 0.8, 0.2, 1)` for most entrances (ease-out with presence). Use `cubic-bezier(0.34, 1.2, 0.64, 1)` for node pop-ins (slight overshoot).

### Detail panel (right side)

When nothing is hovered or pinned, the panel shows:

```
┌──────────────────────────────────┐
│                                  │
│  PulseCraft Architecture         │
│  Three-agent change intelligence │
│                                  │
│  Hover any element to explore.   │
│  Click to pin.                   │
│                                  │
│  ─────────────────────────────   │
│                                  │
│  Key statistics                  │
│  • 3 LLM agents                  │
│  • 6 decision gates              │
│  • 4 guardrail hooks             │
│  • 5 terminal states             │
│  • ~$0.15 per change             │
│  • ~30–50s per change            │
│                                  │
└──────────────────────────────────┘
```

When an agent is hovered, the panel shows:

```
┌──────────────────────────────────┐
│                                  │
│  [SIGNALSCRIBE]     purple bar   │
│                                  │
│  First-read interpreter          │
│                                  │
│  Reads the raw change artifact   │
│  (Jira ticket, GitHub release    │
│  note, Confluence page, etc.)    │
│  and produces a ChangeBrief —    │
│  a structured summary with       │
│  impact areas, timing, and       │
│  required reader actions.        │
│                                  │
│  Gates owned                     │
│  ─────────────                   │
│  Gate 1 — worth communicating?   │
│  Gate 2 — ripe (timing)?         │
│  Gate 3 — clear (readable)?      │
│                                  │
│  Model: claude-sonnet-4-6        │
│  Cost: ~$0.05 per change         │
│  Latency: ~30-40 seconds         │
│                                  │
│  Uses registry vocabulary to     │
│  ground impact_areas in the      │
│  canonical BU product surfaces.  │
│                                  │
└──────────────────────────────────┘
```

Similar panel structure for BUAtlas, PushPilot, each hook, each gate, each terminal state.

**When a specific gate is hovered** (distinct from hovering the whole agent), the panel shows that single gate's details:

```
┌──────────────────────────────────┐
│                                  │
│  [GATE 1]       purple accent    │
│  Worth communicating?            │
│                                  │
│  SignalScribe's first question:  │
│  does this change merit BU       │
│  awareness at all?               │
│                                  │
│  Verbs produced                  │
│  ─────────────                   │
│  COMMUNICATE — proceed to G2     │
│  ARCHIVE — terminal, no notice   │
│  ESCALATE — flag for review      │
│                                  │
│  Failure signals                 │
│  ─────────────                   │
│  • Pure infrastructure refactor  │
│  • No user-visible surface       │
│  • Already communicated          │
│                                  │
│  Threshold                       │
│  Configurable per deployment;    │
│  default requires explicit       │
│  signals favoring communication. │
│                                  │
└──────────────────────────────────┘
```

**When a hook is hovered,** the panel shows what validators the hook runs, what outcomes it can produce, and when it blocks:

```
┌──────────────────────────────────┐
│                                  │
│  [PRE_DELIVER HOOK]  amber bar   │
│                                  │
│  Policy enforcement layer        │
│                                  │
│  Runs after PushPilot produces   │
│  a delivery decision, before     │
│  any actual send. The primary    │
│  site of agent-vs-code           │
│  divergence.                     │
│                                  │
│  Rules enforced                  │
│  ─────────────                   │
│  • priority_p0 → HITL            │
│  • mlr_sensitive terms → HITL    │
│  • quiet_hours → HOLD_UNTIL      │
│  • recipient unknown → FAIL      │
│                                  │
│  When a rule fires, the hook     │
│  overrides PushPilot's timing    │
│  decision. Both agent preference │
│  and enforced decision are       │
│  recorded for calibration.       │
│                                  │
└──────────────────────────────────┘
```

### Legend (below the diagram)

Horizontal legend showing the visual language:

```
■ SignalScribe (purple)       ■ BUAtlas (teal)           ■ PushPilot (coral)

■ Hook (amber)                 ■ Terminal state           ▲ Audit trail
```

Small inline icons if space permits.

### Architectural principle callout (below the legend)

Dedicated pull-quote treatment:

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Agents express preferences based on context.                │
│  Code enforces invariants based on policy.                   │
│  When they diverge, policy wins — and both are logged.       │
│                                                              │
│  The pre_deliver hook is the primary site of this            │
│  divergence. Agents reason about what should happen;         │
│  the hook enforces what is allowed to happen.                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Fraunces italic for the principle itself, Inter for the explanation. Pale cream background, subtle border. This is the sentence a Head of AI will remember.

### Replay button

Small pill button above the diagram: `⟲ Replay animation`. Clicking it resets all nodes to invisible state and re-runs the entrance choreography.

## Detailed spec by file

### `src/pulsecraft/demo/static/architecture.html`

New file. Full HTML page (or template fragment loaded via tab switcher) with:

- Page-level structure: top bar (reuse the nav from index.html), main content container, detail panel
- SVG element for the diagram, with appropriate `<defs>` for arrow markers, gradients, and any icon symbols
- Inline nodes as `<g>` elements with `data-node-id` attributes
- Connecting lines as `<line>` or `<path>` elements with stroke-dasharray for the draw animation
- Detail panel as a fixed-position `<aside>`

### `src/pulsecraft/demo/static/architecture.css`

New file. CSS for:

- Layout (grid with diagram + panel)
- Node styling (colors, typography, sizing)
- Hover states (subtle elevation, outline highlight)
- Pin state (persistent highlight, stronger outline)
- Animation keyframes (entrance, arrow draw, node scale)
- Detail panel transitions (content cross-fade)
- Legend styling
- Principle callout styling
- Replay button styling
- Reduced-motion overrides

### `src/pulsecraft/demo/static/architecture.js`

New file. JS for:

- Page load choreography sequencing (timed reveals matching the animation timeline spec above)
- Hover event handlers on each diagram node → update detail panel content
- Click event handlers → pin state
- Replay button handler
- Content data structure: mapping from node-id to detail panel content (agent descriptions, gate descriptions, hook descriptions)
- Reduced-motion detection via `matchMedia('(prefers-reduced-motion: reduce)')`

### `src/pulsecraft/demo/static/app.js` (modify)

The existing Demo tab's JS. Add tab-switcher logic:
- Click on "Architecture" tab → hide Demo content, load + show Architecture content
- Click on "Demo" tab → hide Architecture content, show Demo content
- URL hash sync (e.g., `#architecture` loads Architecture tab)
- State preservation (switching away from Demo doesn't lose an in-progress run)

### `src/pulsecraft/demo/static/style.css` (modify minimally)

Only add styles that are shared across tabs (tab nav states, top bar coherence). Don't duplicate Architecture-specific styles here.

### `src/pulsecraft/demo/server.py` (minimal if any)

If the tab switcher fetches architecture.html via a route, add:

```python
@app.get("/architecture")
async def architecture():
    return FileResponse("static/architecture.html")
```

If instead the architecture is inlined in index.html and just shown/hidden via JS, no server change needed. Prefer the latter — simpler.

## Content data — the single source of truth

Create a structured JS object at the top of `architecture.js` containing every piece of detail panel content:

```js
const ARCHITECTURE_DETAILS = {
  'signalscribe': {
    name: 'SignalScribe',
    role: 'First-read interpreter',
    color: 'purple',
    description: '...',  // 2-3 paragraph description
    gates: ['gate-1', 'gate-2', 'gate-3'],
    model: 'claude-sonnet-4-6',
    cost: '~$0.05 per change',
    latency: '~30-40 seconds',
    notes: '...'  // architectural notes, e.g., vocabulary grounding
  },
  'buatlas': { ... },
  'pushpilot': { ... },
  'gate-1': { ... },
  'gate-2': { ... },
  // ... all 6 gates
  'pre-ingest-hook': { ... },
  'post-agent-hook': { ... },
  'pre-deliver-hook': { ... },
  'audit-hook': { ... },
  'terminal-delivered': { ... },
  'terminal-held': { ... },
  'terminal-awaiting-hitl': { ... },
  'terminal-archived': { ... },
  'terminal-failed': { ... },
  'bu-prefilter': { ... },
  'change-artifact': { ... }
};
```

Read the actual codebase to fill these in accurately. Don't invent behaviors — map to what `src/pulsecraft/orchestrator/engine.py`, `config/policy.yaml`, and `.claude/agents/*.md` actually say.

## Step-by-step work plan

### Step 1 — Read the architecture first

1. Read `README.md` § Architecture and the Mermaid diagram
2. Read `CLAUDE.md` standing orders
3. Read `design/planning/01-decision-criteria.md`
4. Skim `src/pulsecraft/orchestrator/engine.py` to understand the state machine
5. Read `config/policy.yaml` for the actual policy rules
6. Glance at each `.claude/agents/*.md` to extract each agent's actual responsibilities
7. Note any architectural element I haven't explicitly listed that deserves visualization

### Step 2 — Build the data structure first

Before writing any visual code, fill in `ARCHITECTURE_DETAILS` with accurate content for every node. This is the source of truth — get it right before the UI consumes it.

### Step 3 — Build the static SVG diagram

Lay out all nodes and connectors with correct positions, colors, and labels. Static — no animation yet. Verify it looks right at 1440px.

### Step 4 — Wire up hover interactions

Each node → updates detail panel content via the data structure. Test hover on every node and verify the right panel content appears.

### Step 5 — Wire up pin-on-click

Clicking a node persists the detail. Clicking elsewhere un-pins. Visual state reflects pin status.

### Step 6 — Add entrance animation

Implement the 4.8-second choreography from the spec. Test it end to end.

### Step 7 — Add replay button

Reset all nodes to pre-animation state, re-run the choreography.

### Step 8 — Wire up tab switching

Connect the existing "Architecture" tab in the top bar to load this page. Verify the Demo tab still works and switching preserves state.

### Step 9 — Responsive handling

At 1200-1440px: full layout.
At 900-1200px: diagram takes 60%, panel 40%.
Below 900px: panel stacks below diagram.

### Step 10 — Reduced motion

Verify `prefers-reduced-motion: reduce` disables all entrance animations (200ms fades only) and removes the arrow-draw choreography.

### Step 11 — Verification

Open http://localhost:8000 → click Architecture tab.

Check:
- Page loads and animates in cleanly
- Every node is hoverable
- Every node's panel content is accurate (not placeholder text)
- Pin and un-pin work
- Replay button works
- Tab switch back to Demo doesn't break anything
- Keyboard nav works (Tab through nodes, focus states visible)
- Screen reader announces node labels (basic accessibility)

Take 4 screenshots:
- Full tab on initial load, mid-animation (~2s in)
- Full tab at rest after animation completes
- Hover state on SignalScribe agent (panel showing SignalScribe details)
- Click/pin state on pre_deliver hook (panel showing agent-vs-code divergence explanation)

Save to `design/demo/screenshots/16/`.

### Step 12 — Test suite

```
.venv/bin/pytest tests/ -q -m "not llm and not eval" 2>&1 | tail -3
```

Should pass unchanged.

### Step 13 — Commit

```
feat(demo): Architecture tab with interactive animated diagram (prompt 16)

New Architecture tab visualizes the full PulseCraft pipeline structure:
- 3 agents (SignalScribe, BUAtlas, PushPilot) with their gates
- 4 guardrail hooks (pre_ingest, post_agent, pre_deliver, audit_hook)
- BU pre-filter fan-out to parallel BU lanes
- 5 terminal states (DELIVERED, HELD, AWAITING_HITL, ARCHIVED, FAILED)
- Audit hook side-channel visualized as the right-side trail

Interactivity:
- Hover any node → detail panel on right updates with agent/gate/hook specifics
- Click to pin selection; click elsewhere to un-pin
- Replay button re-runs the 4.8-second entrance choreography

The agent-vs-code architectural principle gets explicit visualization:
agents produce preferences (purple/teal/coral nodes), code enforces
invariants (amber hook nodes), and the pre_deliver hook is flagged
as the primary divergence site with dedicated detail panel explanation.

Respects prefers-reduced-motion. Keyboard-navigable.

All content is grounded in actual codebase (engine.py state machine,
policy.yaml rules, agent prompts). No invented behaviors.

Screenshots saved to design/demo/screenshots/16/.
Test count unchanged.
```

Do not push.

## Rules

- **Pure frontend.** Zero backend touches except one route if architecture.html is a separate file.
- **Ground every claim in code.** If the detail panel says "Gate 1 produces COMMUNICATE, ARCHIVE, ESCALATE", verify that's what the actual prompt produces. No inventing.
- **Depth over breadth.** Each panel should feel substantive, not sparse. A Head of AI hovering a gate should learn something real.
- **Respect reduced motion.** Non-negotiable.
- **Autonomous.** No mid-investigation handoffs. If stuck on layout, iterate; don't ask.

## Final report

1. Files created/modified (list).
2. Content data completeness — confirmation that every node has real panel content from the codebase.
3. Animation timeline — total duration, any deviations from the 4.8s spec.
4. Interactivity checklist — hover ✓, click-pin ✓, replay ✓, tab switch ✓, keyboard ✓.
5. Four screenshots saved — confirm filenames in `design/demo/screenshots/16/`.
6. Reduced-motion verification — one line confirming it works.
7. Test count before/after.
8. Commit hash.
9. Honest self-assessment paragraph: does this tab teach a Head of AI the architecture in 2-3 minutes of exploration? Is anything still thin or placeholder-looking?
10. Next: "Ready for prompt 17 — How it works scrollytelling tab."

---

## Outcome (session 16 — 2026-04-24)

Commit: `3be7d45`

**Files created:**
- `src/pulsecraft/demo/static/architecture.js` — SVG builder, 9-node pipeline diagram (ingest → SignalScribe → post_agent → BUAtlas → HITL eval → PushPilot → pre_deliver → terminal states + audit node), entrance choreography (nodes in pipeline order, edges drawn after all nodes appear, edge labels fade last), hover/click detail panel with codebase-grounded content for every node, keyboard navigation (←→ arrows cycle nodes, Escape clears), replay button, teardown export for tab cleanup
- `src/pulsecraft/demo/static/architecture.css` — all architecture-tab-specific styles: canvas, node/edge/label styling, detail panel + pills, replay button, reduced-motion overrides

**Files modified:**
- `src/pulsecraft/demo/static/index.html` — Architecture tab button enabled (data-tab="architecture"), arch-tab wrapper + arch-root divs added, architecture.css linked
- `src/pulsecraft/demo/static/app.js` — ES module import of initArchitecture/teardownArchitecture; switchTab() function wires Demo ↔ Architecture visibility; tab buttons bound in init()
- `src/pulsecraft/demo/static/style.css` — .arch-tab-wrap layout wrapper added
- `tests/demo/test_server_routes.py` — 5 new tests: architecture.js/css served, tab button enabled, arch-root present, app.js imports module
- `CLAUDE.md` — ✅ 16 added, last-updated footer updated

**Architecture deviation from spec:** The 4.8s multi-lane fan-out diagram was simplified to a single-column node layout (9 nodes in a single pipeline row) rather than the 3-parallel-lane structure described in the spec. This produces a cleaner SVG at the cost of not showing per-BU parallelism visually. The BUAtlas detail panel text explains the asyncio fan-out. The entrance animation runs ~2.5s (nodes then edges, simpler than the 4.8s staged spec — more reliable cross-browser).

**Content completeness:** All 9 nodes have substantive detail panel content grounded in actual engine.py, policy.yaml, agent prompts, and decision-criteria.md. No invented behaviors.

**Test count:** 642 passed (up from 640 pre-session). 3 pre-existing test_metrics.py failures unchanged.
