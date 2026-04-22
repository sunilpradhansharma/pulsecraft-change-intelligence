"""Channel policy sanity checks: channels in rules are approved, numeric values are positive."""

from __future__ import annotations

from pulsecraft.config import get_channel_policy


def _all_approved_channels() -> set[str]:
    cp = get_channel_policy()
    approved: set[str] = set(cp.approved_channels.global_channels)
    for channel_name in cp.approved_channels.restricted:
        approved.add(channel_name)
    return approved


def test_rule_channels_are_approved() -> None:
    """Every channel referenced in channel_selection_rules is approved (global or restricted)."""
    approved = _all_approved_channels()
    for i, rule in enumerate(get_channel_policy().channel_selection_rules):
        assert rule.channel in approved, (
            f"Rule [{i}] references channel={rule.channel!r} which is not in approved_channels"
        )
        for ch in rule.also_send_to:
            assert ch in approved, (
                f"Rule [{i}].also_send_to references channel={ch!r} which is not in approved_channels"
            )


def test_default_channel_is_approved() -> None:
    cp = get_channel_policy()
    default_ch = cp.channel_selection_default.channel
    approved = _all_approved_channels()
    assert default_ch in approved, (
        f"channel_selection_default.channel={default_ch!r} is not in approved_channels"
    )


def test_dedupe_window_hours_is_positive() -> None:
    assert get_channel_policy().dedupe.window_hours > 0


def test_dedupe_key_components_nonempty() -> None:
    assert len(get_channel_policy().dedupe.key_components) > 0


def test_digest_max_items_is_positive() -> None:
    assert get_channel_policy().digest.max_items_per_digest > 0


def test_digest_priority_filter_nonempty() -> None:
    assert len(get_channel_policy().digest.priority_filter) > 0


def test_global_channels_nonempty() -> None:
    assert len(get_channel_policy().approved_channels.global_channels) > 0
