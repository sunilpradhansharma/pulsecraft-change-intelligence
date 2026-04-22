# Config Files

Versioned YAML configuration files read at runtime by the PulseCraft config loader.
All files are synthetic placeholders — real data loaded via Track A onboarding.

## Files

| File | Purpose | Owner (placeholder) |
|---|---|---|
| `bu_registry.yaml` | Product-area → BU mapping for deterministic pre-filter (recall-biased) | Track A Q7 |
| `bu_profiles.yaml` | BU-level preferences: channels, quiet hours, digest opt-in, active initiatives | Track A Q2 |
| `policy.yaml` | Confidence thresholds, restricted terms, HITL triggers, rate limits | Head of AI + InfoSec (Q6) |
| `channel_policy.yaml` | Approved channels, priority routing rules, dedupe, digest cadence | Track A Q5 |

## Schema version contract

Every file carries `schema_version: "1.0"` at the top level. A version bump requires
a corresponding update to the Pydantic model in `src/pulsecraft/schemas/` and a
migration note in the commit message. The loader will reject files whose version
does not match the model expectation.

## Loader API

```python
from pulsecraft.config import (
    get_bu_registry,     # → BURegistry
    get_bu_profile,      # (bu_id: str) → BUProfile
    get_policy,          # → Policy
    get_channel_policy,  # → ChannelPolicy
    reload_config,       # clears in-memory cache (for tests / hot-reload)
)
```

Config directory defaults to `./config`. Override with env var:

```
PULSECRAFT_CONFIG_DIR=/path/to/config python -m pulsecraft ...
```

## Placeholder names

All `head.name`, `escalation_contact.name`, and `delegate_ids` values use
`<placeholder>` syntax. These must be replaced with real display names during
Track A onboarding. The explicit placeholder pattern prevents accidental use of
synthetic values in production.
