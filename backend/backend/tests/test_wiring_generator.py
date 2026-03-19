"""Tests for wiring generator utilities (autoload patching)."""

from __future__ import annotations

from backend.pipelines.contract.wiring_generator import (
    _patch_project_godot_autoloads,
)


# ---------------------------------------------------------------------------
# Bug B: Autoload deduplication tests
# ---------------------------------------------------------------------------

_MINIMAL_PROJECT_GODOT = """\
[application]

config/name="TestGame"

[autoload]

GameManager="*res://game_manager.gd"

[input]

move_left={}
"""


def test_gamemanager_autoload_not_duplicated():
    """Passing GameManager in autoloads list must NOT produce a duplicate entry."""
    result = _patch_project_godot_autoloads(_MINIMAL_PROJECT_GODOT, ["GameManager"])

    count = result.count('GameManager="*res://game_manager.gd"')
    assert count == 1, f"GameManager appeared {count} times, expected 1"


def test_non_gamemanager_autoloads_still_added():
    """Non-hardcoded autoloads are added alongside GameManager (no duplication)."""
    result = _patch_project_godot_autoloads(
        _MINIMAL_PROJECT_GODOT, ["GameManager", "AudioBus"]
    )

    gm_count = result.count('GameManager="*res://game_manager.gd"')
    assert gm_count == 1, f"GameManager appeared {gm_count} times, expected 1"
    assert "AudioBus" in result


def test_empty_autoloads_only_gamemanager():
    """Empty autoloads list should still produce the hardcoded GameManager entry."""
    result = _patch_project_godot_autoloads(_MINIMAL_PROJECT_GODOT, [])

    assert 'GameManager="*res://game_manager.gd"' in result
    # No other autoload entries besides GameManager
    autoload_section = result.split("[autoload]")[1].split("[")[0]
    assert autoload_section.count("=") == 1  # only GameManager line
