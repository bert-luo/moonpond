"""Unit tests for SceneAssembler and parse_onready_unique_refs."""

from __future__ import annotations

from backend.pipelines.contract.models import GameContract, NodeContract
from backend.pipelines.contract.scene_assembler import (
    SceneAssembler,
    parse_onready_unique_refs,
)


# ---------------------------------------------------------------------------
# parse_onready_unique_refs tests
# ---------------------------------------------------------------------------


class TestParseOnreadyUniqueRefs:
    """Tests for the @onready %Name regex parser."""

    def test_typed_onready(self):
        src = '@onready var score_label: Label = %ScoreLabel'
        refs = parse_onready_unique_refs(src)
        assert len(refs) == 1
        assert refs[0] == {"var_name": "score_label", "node_type": "Label", "unique_name": "ScoreLabel"}

    def test_untyped_onready(self):
        src = '@onready var bird = %Bird'
        refs = parse_onready_unique_refs(src)
        assert len(refs) == 1
        assert refs[0] == {"var_name": "bird", "node_type": None, "unique_name": "Bird"}

    def test_no_onready_returns_empty(self):
        src = 'var speed: float = 100.0\nfunc _ready():\n\tpass'
        refs = parse_onready_unique_refs(src)
        assert refs == []

    def test_ignores_dollar_path_onready(self):
        src = '@onready var child = $Child/Node'
        refs = parse_onready_unique_refs(src)
        assert refs == []

    def test_multiple_refs(self):
        src = (
            '@onready var top: StaticBody2D = %PipeTop\n'
            '@onready var bottom: StaticBody2D = %PipeBottom\n'
            '@onready var gap = %GapArea\n'
        )
        refs = parse_onready_unique_refs(src)
        assert len(refs) == 3
        names = [r["unique_name"] for r in refs]
        assert names == ["PipeTop", "PipeBottom", "GapArea"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_space_blaster_contract() -> GameContract:
    """A realistic contract modeled on Space Blaster test data."""
    return GameContract(
        title="Space Blaster",
        control_scheme="keyboard",
        main_scene="Main.tscn",
        nodes=[
            NodeContract(
                script_path="main.gd",
                scene_path="Main.tscn",
                node_type="Node2D",
                description="Main scene script",
                methods=["_ready()"],
                spawn_mode="static",
            ),
            NodeContract(
                script_path="player.gd",
                scene_path=None,
                node_type="CharacterBody2D",
                description="Player ship",
                methods=["shoot()", "take_damage(amount: int)"],
                signals=["died"],
                groups=["player"],
                dependencies=[],
                spawn_mode="static",
            ),
            NodeContract(
                script_path="hud.gd",
                scene_path="HUD.tscn",
                node_type="CanvasLayer",
                description="HUD overlay",
                methods=["update_score(value: int)"],
                spawn_mode="static",
            ),
            NodeContract(
                script_path="enemy.gd",
                scene_path="Enemy.tscn",
                node_type="Area2D",
                description="Enemy ship",
                methods=["die()"],
                signals=["destroyed"],
                spawn_mode="dynamic",
            ),
        ],
    )


def _make_node_files() -> dict[str, str]:
    """Simulated .gd file contents keyed by script_path."""
    return {
        "main.gd": (
            'extends Node2D\n'
            '\n'
            '@onready var player: CharacterBody2D = %Player\n'
            '@onready var hud = %HUD\n'
            '\n'
            'func _ready():\n'
            '\tpass\n'
        ),
        "player.gd": (
            'extends CharacterBody2D\n'
            '\n'
            'signal died\n'
            '\n'
            'func _ready():\n'
            '\tpass\n'
        ),
        "hud.gd": (
            'extends CanvasLayer\n'
            '\n'
            '@onready var score_label: Label = %ScoreLabel\n'
            '@onready var health_bar: ProgressBar = %HealthBar\n'
            '\n'
            'func update_score(value: int):\n'
            '\t$ScoreLabel.text = str(value)\n'
        ),
        "enemy.gd": (
            'extends Area2D\n'
            '\n'
            'signal destroyed\n'
            '\n'
            'func die():\n'
            '\temit_signal("destroyed")\n'
            '\tqueue_free()\n'
        ),
    }


# ---------------------------------------------------------------------------
# SceneAssembler tests
# ---------------------------------------------------------------------------


class TestSceneAssemblerMainTscn:
    """Tests for Main.tscn generation."""

    def test_returns_dict_with_main_tscn(self):
        contract = _make_space_blaster_contract()
        files = _make_node_files()
        result = SceneAssembler.assemble(contract, files)
        assert isinstance(result, dict)
        assert "Main.tscn" in result

    def test_main_has_root_node(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        assert '[node name="Main" type="Node2D"]' in main
        # Root has no parent= attribute
        for line in main.splitlines():
            if 'name="Main"' in line and line.startswith("[node"):
                assert "parent=" not in line

    def test_main_has_ext_resources_for_scripts(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        # main.gd script attached to root
        assert 'path="res://main.gd"' in main
        # player.gd as inline node script
        assert 'path="res://player.gd"' in main

    def test_main_uses_instance_for_scene_path_nodes(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        # HUD has scene_path=HUD.tscn, should be instanced
        assert 'path="res://HUD.tscn"' in main
        assert 'name="HUD"' in main
        # Instance node should use instance=ExtResource, not type=
        for line in main.splitlines():
            if 'name="HUD"' in line and line.startswith("[node"):
                assert "instance=ExtResource" in line
                assert "type=" not in line

    def test_main_skips_dynamic_nodes(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        # Enemy is dynamic — should not appear in Main.tscn
        assert 'name="Enemy"' not in main

    def test_all_scripted_nodes_have_unique_name(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        # Player is inline with script — should have unique_name_in_owner
        assert "unique_name_in_owner = true" in main

    def test_no_connection_entries(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        assert "[connection" not in main

    def test_inline_node_for_no_scene_path(self):
        """Nodes with scene_path=None (and not main script) are added inline with type and script."""
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        # Player has scene_path=None → inline node with type
        for line in main.splitlines():
            if 'name="Player"' in line and line.startswith("[node"):
                assert 'type="CharacterBody2D"' in line
                assert 'parent="."' in line

    def test_main_does_not_parse_onready_from_main_gd(self):
        """Main.tscn should NOT add child nodes for @onready refs in main.gd."""
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        main = result["Main.tscn"]
        # main.gd has @onready %Player and %HUD, but those are sibling instances
        # not children to create — they already appear as top-level nodes
        # There should be no nested parsing of main.gd creating extra children
        lines = [l for l in main.splitlines() if l.startswith("[node")]
        # Expect: Main (root), Player (inline), HUD (instance) = 3 node lines
        assert len(lines) == 3


class TestSceneAssemblerSubScenes:
    """Tests for sub-scene .tscn generation."""

    def test_sub_scene_created_for_hud(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        assert "HUD.tscn" in result

    def test_sub_scene_root_node(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        hud = result["HUD.tscn"]
        assert '[node name="HUD" type="CanvasLayer"]' in hud

    def test_sub_scene_has_onready_children(self):
        """Sub-scene should include child nodes for each @onready %Name ref."""
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        hud = result["HUD.tscn"]
        assert 'name="ScoreLabel"' in hud
        assert 'name="HealthBar"' in hud

    def test_sub_scene_children_have_correct_types(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        hud = result["HUD.tscn"]
        for line in hud.splitlines():
            if 'name="ScoreLabel"' in line:
                assert 'type="Label"' in line
            if 'name="HealthBar"' in line:
                assert 'type="ProgressBar"' in line

    def test_sub_scene_children_have_unique_name(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        hud = result["HUD.tscn"]
        # Each child from @onready should have unique_name_in_owner
        assert hud.count("unique_name_in_owner = true") >= 2  # ScoreLabel + HealthBar

    def test_sub_scene_not_created_for_dynamic_nodes(self):
        """Dynamic nodes (enemy) should not get sub-scene files."""
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        assert "Enemy.tscn" not in result

    def test_physics_body_gets_collision_shape(self):
        """Physics body sub-scenes should auto-add CollisionShape2D."""
        contract = GameContract(
            title="Test",
            control_scheme="keyboard",
            nodes=[
                NodeContract(
                    script_path="bird.gd",
                    scene_path="Bird.tscn",
                    node_type="CharacterBody2D",
                    description="A bird",
                    spawn_mode="static",
                ),
            ],
        )
        files = {"bird.gd": "extends CharacterBody2D\nfunc _ready():\n\tpass\n"}
        result = SceneAssembler.assemble(contract, files)
        bird = result["Bird.tscn"]
        assert 'name="CollisionShape2D"' in bird
        assert "RectangleShape2D" in bird
        assert "Vector2(64, 64)" in bird

    def test_sub_scene_has_script_ext_resource(self):
        result = SceneAssembler.assemble(_make_space_blaster_contract(), _make_node_files())
        hud = result["HUD.tscn"]
        assert 'path="res://hud.gd"' in hud
        assert 'script = ExtResource(' in hud
