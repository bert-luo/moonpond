"""Unit tests for expand_input_map utility."""

from __future__ import annotations

import pytest

from backend.pipelines.agentic.input_map import KEY_MAP, _EVENT_TEMPLATE, expand_input_map


# ---------------------------------------------------------------------------
# KEY_MAP sanity
# ---------------------------------------------------------------------------


def test_key_map_has_arrow_keys():
    assert KEY_MAP["arrow_left"] == 4194319
    assert KEY_MAP["arrow_right"] == 4194321
    assert KEY_MAP["arrow_up"] == 4194320
    assert KEY_MAP["arrow_down"] == 4194322


def test_key_map_has_common_keys():
    assert KEY_MAP["space"] == 32
    assert KEY_MAP["enter"] == 4194309
    assert KEY_MAP["escape"] == 4194305


def test_key_map_has_letters():
    assert KEY_MAP["a"] == 65
    assert KEY_MAP["z"] == 90


def test_key_map_has_digits():
    assert KEY_MAP["0"] == 48
    assert KEY_MAP["9"] == 57


def test_key_map_has_f_keys():
    assert KEY_MAP["f1"] == 4194332
    assert KEY_MAP["f12"] == 4194343


# ---------------------------------------------------------------------------
# Basic expansion
# ---------------------------------------------------------------------------


def test_expand_simple_action():
    content = (
        "[input]\n"
        "move_left=arrow_left\n"
    )
    result = expand_input_map(content)
    assert "Object(InputEventKey" in result
    assert "physical_keycode\":4194319" in result
    assert "move_left=" in result


def test_expand_two_actions():
    content = (
        "[input]\n"
        "move_left=arrow_left\n"
        "move_right=arrow_right\n"
    )
    result = expand_input_map(content)
    assert "physical_keycode\":4194319" in result
    assert "physical_keycode\":4194321" in result


# ---------------------------------------------------------------------------
# Passthrough
# ---------------------------------------------------------------------------


def test_passthrough_already_expanded():
    """Lines already containing Object( are left unchanged."""
    original_line = (
        'move_left={\n'
        '"deadzone": 0.5,\n'
        '"events": [Object(InputEventKey,"resource_local_to_scene":false,'
        '"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,'
        '"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,'
        '"pressed":false,"keycode":0,"physical_keycode":4194319,'
        '"key_label":0,"unicode":0,"echo":false,"script":null)]\n'
        '}\n'
    )
    content = "[input]\n" + original_line
    result = expand_input_map(content)
    # The original Object() line should be present unchanged
    assert 'Object(InputEventKey,"resource_local_to_scene":false' in result


def test_passthrough_brace_line():
    """Lines with { (dict start) are treated as already-expanded."""
    content = (
        "[input]\n"
        "jump={\n"
        '"deadzone": 0.5,\n'
        '"events": [Object(InputEventKey,"physical_keycode":32)]\n'
        "}\n"
    )
    result = expand_input_map(content)
    # Should not double-expand
    assert result.count("Object(") == 1


# ---------------------------------------------------------------------------
# Unknown keys
# ---------------------------------------------------------------------------


def test_unknown_key_left_unchanged():
    """Unknown key names leave the line unchanged — no crash, no data loss."""
    content = "[input]\nmyaction=unknown_key_xyz\n"
    result = expand_input_map(content)
    assert "myaction=unknown_key_xyz" in result


# ---------------------------------------------------------------------------
# Full project.godot round-trip
# ---------------------------------------------------------------------------

FULL_PROJECT_GODOT = """\
config_version=5

[application]

config/name="TestGame"
run/main_scene="res://Main.tscn"

[autoload]

GameManager="*res://game_manager.gd"

[input]

move_left=arrow_left
move_right=arrow_right
jump=space

[rendering]

renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"

[display]

window/size/viewport_width=1152
window/size/viewport_height=648
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"
"""


def test_full_round_trip_preserves_rendering():
    result = expand_input_map(FULL_PROJECT_GODOT)
    assert 'renderer/rendering_method="gl_compatibility"' in result


def test_full_round_trip_preserves_display():
    result = expand_input_map(FULL_PROJECT_GODOT)
    assert "window/size/viewport_width=1152" in result
    assert "window/size/viewport_height=648" in result


def test_full_round_trip_preserves_application():
    result = expand_input_map(FULL_PROJECT_GODOT)
    assert 'config/name="TestGame"' in result
    assert 'run/main_scene="res://Main.tscn"' in result


def test_full_round_trip_preserves_autoload():
    result = expand_input_map(FULL_PROJECT_GODOT)
    assert 'GameManager="*res://game_manager.gd"' in result


def test_full_round_trip_expands_input():
    result = expand_input_map(FULL_PROJECT_GODOT)
    assert "Object(InputEventKey" in result
    assert "physical_keycode\":4194319" in result  # arrow_left
    assert "physical_keycode\":4194321" in result  # arrow_right
    assert "physical_keycode\":32" in result        # space


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


def test_empty_input_section():
    content = "[input]\n\n[rendering]\nfoo=bar\n"
    result = expand_input_map(content)
    assert "[rendering]" in result
    assert "foo=bar" in result


def test_no_input_section():
    content = "[rendering]\nfoo=bar\n"
    result = expand_input_map(content)
    assert result == content


def test_mixed_format():
    """Some lines simplified, some already expanded — both handled correctly."""
    content = (
        "[input]\n"
        "move_left=arrow_left\n"
        'jump={\n'
        '"deadzone": 0.5,\n'
        '"events": [Object(InputEventKey,"physical_keycode":32)]\n'
        '}\n'
        "shoot=z\n"
    )
    result = expand_input_map(content)
    # move_left and shoot should be expanded
    assert "physical_keycode\":4194319" in result  # arrow_left
    assert "physical_keycode\":90" in result        # z
    # jump should keep existing Object (only 1 extra from passthrough)
    # total Object( count: 1 from passthrough + 2 from expansion = 3
    assert result.count("Object(InputEventKey") == 3
