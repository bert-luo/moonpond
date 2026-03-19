"""Input map expansion — converts simplified key names to Godot Object() format.

The agentic pipeline's LLM generates project.godot with a simplified [input]
section (e.g. ``move_left=arrow_left``).  This module expands those lines into
the full ``Object(InputEventKey, ...)`` serialization that Godot 4 expects.
"""

from __future__ import annotations

import re

# Maps human-readable key names to Godot 4 physical_keycode values.
# Values confirmed from godot/templates/base_2d/project.godot.
KEY_MAP: dict[str, int] = {
    # Arrow keys
    "arrow_left": 4194319,
    "arrow_right": 4194321,
    "arrow_up": 4194320,
    "arrow_down": 4194322,
    # Common keys
    "space": 32,
    "enter": 4194309,
    "escape": 4194305,
    "shift": 4194325,
    "ctrl": 4194326,
    "tab": 4194308,
    "backspace": 4194310,
    # Letters (lowercase ASCII values)
    "a": 65, "b": 66, "c": 67, "d": 68, "e": 69,
    "f": 70, "g": 71, "h": 72, "i": 73, "j": 74,
    "k": 75, "l": 76, "m": 77, "n": 78, "o": 79,
    "p": 80, "q": 81, "r": 82, "s": 83, "t": 84,
    "u": 85, "v": 86, "w": 87, "x": 88, "y": 89,
    "z": 90,
    # Digits
    "0": 48, "1": 49, "2": 50, "3": 51, "4": 52,
    "5": 53, "6": 54, "7": 55, "8": 56, "9": 57,
    # F-keys
    "f1": 4194332, "f2": 4194333, "f3": 4194334,
    "f4": 4194335, "f5": 4194336, "f6": 4194337,
    "f7": 4194338, "f8": 4194339, "f9": 4194340,
    "f10": 4194341, "f11": 4194342, "f12": 4194343,
}

_EVENT_TEMPLATE = (
    '{action}={{\n'
    '"deadzone": 0.5,\n'
    '"events": [Object(InputEventKey,"resource_local_to_scene":false,'
    '"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,'
    '"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,'
    '"pressed":false,"keycode":0,"physical_keycode":{keycode},'
    '"key_label":0,"unicode":0,"echo":false,"script":null)]\n'
    '}}'
)

# Regex to isolate the [input] section body.
# Same lookahead pattern as wiring_generator.py.
_INPUT_SECTION_RE = re.compile(
    r"(\[input\]\s*\n)((?:.*\n)*?)(?=\[|\Z)"
)

# Matches a simplified action line: action_name=key_name (no braces, no Object)
_SIMPLE_ACTION_RE = re.compile(r"^(\w+)=(\w+)\s*$")


def expand_input_map(project_godot_content: str) -> str:
    """Expand simplified [input] actions to full Godot Object() format.

    Lines like ``move_left=arrow_left`` become the full
    ``Object(InputEventKey, ...)`` block.  Lines already in full format
    (containing ``Object(`` or ``{``) are passed through unchanged.
    Lines with unknown key names are left unchanged.

    All other sections ([rendering], [display], etc.) are preserved verbatim.
    """
    match = _INPUT_SECTION_RE.search(project_godot_content)
    if not match:
        return project_godot_content

    header = match.group(1)  # "[input]\n"
    body = match.group(2)    # everything between [input] and next section

    # Process lines in the input section body
    lines = body.split("\n")
    expanded_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            expanded_lines.append(line)
            i += 1
            continue

        # Already-expanded: line contains Object( or starts a dict block with {
        if "Object(" in line or (line.strip().endswith("={") or "={" in line):
            # Pass through the entire block until we hit a closing }
            expanded_lines.append(line)
            i += 1
            # If it's a multi-line block (has {), consume until closing }
            if "{" in line and "}" not in line:
                while i < len(lines):
                    expanded_lines.append(lines[i])
                    if "}" in lines[i]:
                        i += 1
                        break
                    i += 1
            continue

        # Try simplified format: action_name=key_name
        m = _SIMPLE_ACTION_RE.match(line)
        if m:
            action, key_name = m.group(1), m.group(2)
            keycode = KEY_MAP.get(key_name)
            if keycode is not None:
                expanded_lines.append(
                    _EVENT_TEMPLATE.format(action=action, keycode=keycode)
                )
                i += 1
                continue
            # Unknown key — leave line unchanged
            expanded_lines.append(line)
            i += 1
            continue

        # Anything else — passthrough
        expanded_lines.append(line)
        i += 1

    new_body = "\n".join(expanded_lines)
    # Replace original section body
    return project_godot_content[:match.start()] + header + new_body + project_godot_content[match.end():]
