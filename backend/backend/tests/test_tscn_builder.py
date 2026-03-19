"""Unit tests for the TscnBuilder utility class."""

from __future__ import annotations

from backend.pipelines.contract.tscn_builder import TscnBuilder


class TestTscnBuilderSerialize:
    """Tests for TscnBuilder.serialize() output format."""

    def test_empty_builder_produces_minimal_header(self):
        b = TscnBuilder()
        out = b.serialize()
        assert out.startswith("[gd_scene format=3")
        # No load_steps when nothing added
        assert "load_steps" not in out

    def test_header_load_steps_counts_resources(self):
        b = TscnBuilder()
        b.add_ext_resource("Script", "res://player.gd")
        b.add_sub_resource("RectangleShape2D", {"size": "Vector2(64, 64)"})
        out = b.serialize()
        assert "[gd_scene load_steps=2 format=3" in out


class TestTscnBuilderExtResource:
    """Tests for add_ext_resource."""

    def test_ext_resource_returns_unique_id(self):
        b = TscnBuilder()
        id1 = b.add_ext_resource("Script", "res://player.gd")
        id2 = b.add_ext_resource("PackedScene", "res://Bird.tscn")
        assert id1 != id2

    def test_ext_resource_appears_in_output(self):
        b = TscnBuilder()
        eid = b.add_ext_resource("Script", "res://player.gd")
        out = b.serialize()
        assert f'[ext_resource type="Script" path="res://player.gd" id="{eid}"]' in out


class TestTscnBuilderSubResource:
    """Tests for add_sub_resource."""

    def test_sub_resource_returns_id(self):
        b = TscnBuilder()
        sid = b.add_sub_resource("RectangleShape2D", {"size": "Vector2(64, 64)"})
        assert sid  # non-empty

    def test_sub_resource_appears_with_props(self):
        b = TscnBuilder()
        sid = b.add_sub_resource("RectangleShape2D", {"size": "Vector2(64, 64)"})
        out = b.serialize()
        assert f'[sub_resource type="RectangleShape2D" id="{sid}"]' in out
        assert 'size = Vector2(64, 64)' in out


class TestTscnBuilderNodes:
    """Tests for add_node."""

    def test_root_node_no_parent_attribute(self):
        b = TscnBuilder()
        b.add_node("Main", "Node2D", parent=None)
        out = b.serialize()
        assert '[node name="Main" type="Node2D"]' in out
        # Root node should NOT have parent=
        for line in out.splitlines():
            if 'name="Main"' in line and line.startswith("[node"):
                assert "parent=" not in line

    def test_child_node_has_parent(self):
        b = TscnBuilder()
        b.add_node("Main", "Node2D", parent=None)
        b.add_node("Player", "CharacterBody2D", parent=".")
        out = b.serialize()
        assert '[node name="Player" type="CharacterBody2D" parent="."]' in out

    def test_node_with_script_id(self):
        b = TscnBuilder()
        sid = b.add_ext_resource("Script", "res://player.gd")
        b.add_node("Player", "CharacterBody2D", parent=".", script_id=sid)
        out = b.serialize()
        assert f'script = ExtResource("{sid}")' in out

    def test_node_with_instance_id_no_type(self):
        b = TscnBuilder()
        iid = b.add_ext_resource("PackedScene", "res://Bird.tscn")
        b.add_node("Bird", None, parent=".", instance_id=iid)
        out = b.serialize()
        assert f'instance=ExtResource("{iid}")' in out
        # instance nodes must NOT have type=
        for line in out.splitlines():
            if 'name="Bird"' in line and line.startswith("[node"):
                assert "type=" not in line

    def test_node_with_unique_name(self):
        b = TscnBuilder()
        b.add_node("ScoreLabel", "Label", parent=".", unique_name=True)
        out = b.serialize()
        assert "unique_name_in_owner = true" in out

    def test_node_with_extra_props(self):
        b = TscnBuilder()
        sid = b.add_sub_resource("RectangleShape2D", {"size": "Vector2(64, 64)"})
        b.add_node("CollisionShape2D", "CollisionShape2D", parent=".", extra_props={"shape": f'SubResource("{sid}")'})
        out = b.serialize()
        assert f'shape = SubResource("{sid}")' in out


class TestTscnBuilderConnections:
    """Tests for add_connection."""

    def test_connection_appears_in_output(self):
        b = TscnBuilder()
        b.add_node("Main", "Node2D", parent=None)
        b.add_connection("died", "Bird", ".", "_on_bird_died")
        out = b.serialize()
        assert '[connection signal="died" from="Bird" to="." method="_on_bird_died"]' in out


class TestTscnBuilderSectionOrder:
    """Sections appear in correct order: header, ext_resources, sub_resources, nodes, connections."""

    def test_section_order(self):
        b = TscnBuilder()
        eid = b.add_ext_resource("Script", "res://player.gd")
        sid = b.add_sub_resource("RectangleShape2D", {"size": "Vector2(64, 64)"})
        b.add_node("Main", "Node2D", parent=None)
        b.add_connection("died", "Bird", ".", "_on_bird_died")
        out = b.serialize()

        idx_header = out.index("[gd_scene")
        idx_ext = out.index("[ext_resource")
        idx_sub = out.index("[sub_resource")
        idx_node = out.index("[node")
        idx_conn = out.index("[connection")

        assert idx_header < idx_ext < idx_sub < idx_node < idx_conn
