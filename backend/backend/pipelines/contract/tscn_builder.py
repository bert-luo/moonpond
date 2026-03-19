"""TscnBuilder — programmatic Godot 4 .tscn file generation.

Constructs valid .tscn text deterministically from Python, eliminating
the need for LLM-generated scene files and their associated hallucination
bugs (invalid ExtResource IDs, missing nodes, wrong script paths).

Usage:
    b = TscnBuilder()
    sid = b.add_ext_resource("Script", "res://player.gd")
    b.add_node("Main", "Node2D", parent=None)
    b.add_node("Player", "CharacterBody2D", parent=".", script_id=sid)
    print(b.serialize())
"""

from __future__ import annotations


class TscnBuilder:
    """Builds a Godot 4 .tscn file programmatically."""

    def __init__(self) -> None:
        self._ext_resources: list[tuple[str, str, str]] = []  # (type, path, id)
        self._sub_resources: list[tuple[str, str, dict]] = []  # (type, id, props)
        self._nodes: list[dict] = []
        self._connections: list[tuple[str, str, str, str]] = []  # (signal, from, to, method)
        self._next_id = 1

    def add_ext_resource(self, res_type: str, path: str) -> str:
        """Add an external resource and return its string ID."""
        rid = str(self._next_id)
        self._next_id += 1
        self._ext_resources.append((res_type, path, rid))
        return rid

    def add_sub_resource(self, res_type: str, props: dict | None = None) -> str:
        """Add a sub-resource and return its string ID."""
        sid = f"{res_type}_{self._next_id}"
        self._next_id += 1
        self._sub_resources.append((res_type, sid, props or {}))
        return sid

    def add_node(
        self,
        name: str,
        node_type: str | None,
        parent: str | None,
        *,
        script_id: str | None = None,
        instance_id: str | None = None,
        unique_name: bool = False,
        extra_props: dict | None = None,
    ) -> None:
        """Add a node to the scene tree.

        ``instance_id`` and ``node_type`` are mutually exclusive — an instanced
        node uses ``instance=ExtResource(...)`` instead of ``type=``.
        """
        assert not (
            instance_id and node_type
        ), "instance_id and node_type are mutually exclusive"

        self._nodes.append(
            {
                "name": name,
                "type": node_type,
                "parent": parent,
                "script_id": script_id,
                "instance_id": instance_id,
                "unique_name": unique_name,
                "extra_props": extra_props or {},
            }
        )

    def add_connection(
        self, signal: str, from_path: str, to_path: str, method: str
    ) -> None:
        """Add a signal connection."""
        self._connections.append((signal, from_path, to_path, method))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(self) -> str:
        """Produce the complete .tscn file text."""
        parts: list[str] = []

        # Header
        load_steps = len(self._ext_resources) + len(self._sub_resources)
        if load_steps:
            parts.append(f"[gd_scene load_steps={load_steps} format=3]\n")
        else:
            parts.append("[gd_scene format=3]\n")

        # ext_resource section
        for res_type, path, rid in self._ext_resources:
            parts.append(
                f'[ext_resource type="{res_type}" path="{path}" id="{rid}"]'
            )

        # sub_resource section
        for res_type, sid, props in self._sub_resources:
            parts.append("")  # blank line before section
            parts.append(f'[sub_resource type="{res_type}" id="{sid}"]')
            for k, v in props.items():
                parts.append(f"{k} = {v}")

        # node section
        for node in self._nodes:
            parts.append("")  # blank line before each node
            header = self._format_node_header(node)
            parts.append(header)
            # Properties
            if node["script_id"]:
                parts.append(f'script = ExtResource("{node["script_id"]}")')
            if node["unique_name"]:
                parts.append("unique_name_in_owner = true")
            for k, v in node["extra_props"].items():
                parts.append(f"{k} = {v}")

        # connection section
        for sig, from_path, to_path, method in self._connections:
            parts.append("")
            parts.append(
                f'[connection signal="{sig}" from="{from_path}" to="{to_path}" method="{method}"]'
            )

        return "\n".join(parts) + "\n"

    @staticmethod
    def _format_node_header(node: dict) -> str:
        """Build the [node ...] header line."""
        if node["instance_id"]:
            # Instanced node — no type=
            header = f'[node name="{node["name"]}" parent="{node["parent"]}" instance=ExtResource("{node["instance_id"]}")]'
        elif node["parent"] is None:
            # Root node — no parent=
            header = f'[node name="{node["name"]}" type="{node["type"]}"]'
        else:
            header = f'[node name="{node["name"]}" type="{node["type"]}" parent="{node["parent"]}"]'
        return header
