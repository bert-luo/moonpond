# godot-gdscript-toolkit: Parser Research

**Repo**: https://github.com/Scony/godot-gdscript-toolkit
**Package**: `pip install "gdtoolkit==4.*"` (for Godot 4.x)
**License**: MIT | ~1.5k stars
**Latest**: v4.5.0 (Oct 2025)

---

## What It Is

A Python toolkit for GDScript providing four tools:

| Tool | CLI | Purpose |
|------|-----|---------|
| Parser | `gdparse` | Parse GDScript into a Lark parse tree |
| Linter | `gdlint` | Style/convention checking |
| Formatter | `gdformat` | Auto-formatting (like Black) |
| Metrics | `gdradon` | Cyclomatic complexity |

Built on [Lark](https://github.com/lark-parser/lark) (LALR(1) parser). The grammar lives in `gdtoolkit/parser/gdscript.lark`.

---

## Q1: Can It Check Code Validity?

### Yes — syntax-level only

The parser will raise `lark.exceptions.UnexpectedToken` / `UnexpectedInput` on syntactically invalid GDScript. This is reliable for catching:

- Missing colons, unclosed brackets, bad indentation
- Invalid keyword usage, malformed expressions
- Any construct that doesn't match the GDScript grammar

```python
from gdtoolkit.parser import parser

try:
    tree = parser.parse(gdscript_code)
    # syntactically valid
except Exception as e:
    # syntax error — e contains line/column info
    print(f"Parse error: {e}")
```

The linter adds convention checks on top (naming, complexity, style), but these are cosmetic, not correctness.

### No — it cannot catch semantic errors

**Not detected:**
- Type errors (`var x: int = "hello"` parses fine)
- Undefined variable/function/class references
- Wrong method signatures or argument counts
- Invalid Godot API calls (e.g., calling a method that doesn't exist on Node2D)
- Missing files referenced by `preload()`/`load()`
- Signal signature mismatches

The toolkit has **zero knowledge of Godot's built-in API**. It's a pure syntax tool — it knows GDScript grammar but not what Godot provides.

### Verdict for validity checking

**Useful as a fast pre-check** — catches obvious syntax broken-ness before sending to Godot. But it won't catch the majority of real bugs (wrong method names, wrong types, missing dependencies). For full validation, you still need `godot --headless --check-only` or equivalent.

**Recommended use**: Run as a cheap first-pass filter. If parse fails, skip the expensive Godot validation entirely and feed the error back to the LLM for correction.

---

## Q2: Can It Track Inter-file Dependencies?

### No — strictly single-file

The parser processes one file/string at a time. There is:

- **No `extends` resolution** — `extends "res://path/to/base.gd"` is parsed as a string literal, not resolved
- **No `preload()`/`load()` path resolution** — paths are opaque strings
- **No `class_name` cross-referencing** — class names are parsed but not linked to other files
- **No project-level analysis** — no concept of a Godot project, `res://` root, or file system
- **No signal connection tracking** across files

### What we'd need to build ourselves

To get dependency tracking, we could use the parser as a **foundation** and build on top:

```python
from gdtoolkit.parser import parser

def extract_dependencies(gd_code: str) -> dict:
    tree = parser.parse(gd_code, gather_metadata=True)
    deps = {
        "extends": [],       # extends "res://..." or extends ClassName
        "preloads": [],      # preload("res://...")
        "loads": [],         # load("res://...")
        "class_names_used": [],  # references to other class_names
    }
    # Walk tree looking for:
    # - "extends" nodes → extract path or class name
    # - function calls where name is "preload" or "load" → extract string arg
    # - type annotations and expressions referencing PascalCase names
    _walk_tree(tree, deps)
    return deps
```

The key grammar nodes to look for:

| Dependency type | Grammar node / pattern |
|----------------|----------------------|
| `extends` | Top-level `extends` statement, child is string or dotted name |
| `preload()` | `getattr` call where function name is `preload`, first arg is string |
| `load()` | Same pattern with `load` |
| `class_name` refs | Type annotations, `is` checks, static method calls on PascalCase names |
| Scene refs | `$NodePath` or `%UniqueName` — these reference scene tree, not files |

**Feasibility**: Extracting `extends` and `preload`/`load` paths is straightforward — they're string literals in predictable tree positions. Tracking `class_name` references is harder because you need to distinguish local classes from cross-file references, which requires a project-wide index.

### Verdict for dependency tracking

**Not built-in, but buildable.** The parse tree gives us enough structure to extract `extends`, `preload()`, and `load()` references with moderate effort. Full `class_name` resolution requires a two-pass approach (index all class_names first, then resolve references). This is a weekend project, not a mountain.

---

## Programmatic API

### Parsing

```python
from gdtoolkit.parser import parser

# Returns lark.Tree (concrete syntax tree)
tree = parser.parse(code_string)

# With line/column metadata (slower)
tree = parser.parse(code_string, gather_metadata=True)
```

### Tree navigation (Lark API)

```python
# tree.data → rule name ("start", "func_def", "class_def", etc.)
# tree.children → list of Tree | Token
# tree.find_data("func_def") → iterator of all func_def subtrees
# tree.pretty() → formatted string dump

for func in tree.find_data("func_def"):
    func_name = func.children[0]  # Token with function name
    print(f"Found function: {func_name}")
```

### Higher-level AST wrapper

```python
from gdtoolkit.common.ast import AbstractSyntaxTree

ast = AbstractSyntaxTree(tree)
for cls in ast.classes:       # includes synthetic global scope
    for func in cls.functions:
        print(f"{cls.name}.{func.name}")
```

Exposes: `Class`, `Function`, `Statement`, `Parameter`, `Annotation` objects. Incomplete (has TODOs) but usable for basic traversal.

### Linting

```python
from gdtoolkit.linter import lint_code, DEFAULT_CONFIG

problems = lint_code(tree, config=DEFAULT_CONFIG)
for p in problems:
    print(f"Line {p.line}: [{p.name}] {p.description}")
```

---

## Godot 4.x Support

Version 4.x of the toolkit supports all modern GDScript syntax:

- `@export`, `@onready`, `@tool` annotations
- Typed variables and return types
- `await` expressions
- `match` with guards
- Lambda expressions (including multi-line)
- Typed dictionaries (4.3.2+)
- `@abstract` functions (4.5.0)
- Variadic functions (4.5.0)
- Raw strings, node paths, signal node references

Install with `pip install "gdtoolkit==4.*"` — the major version tracks Godot's major version.

---

## Known Limitations

1. **Produces CST, not AST** — the Lark tree is verbose/deeply nested. The `common/ast.py` wrapper helps but is incomplete.
2. **Formatter can lose data** — README warns to use with VCS. Known issues with comment displacement, indentation corruption.
3. **28 open issues** — parser can't handle some valid GDScript edge cases.
4. **No LSP** — despite being a "toolkit", there's no language server.
5. **Grammar may lag behind Godot** — new syntax features take time to be added.

---

## Recommendations for Moonpond Pipeline

### Use for: fast syntax validation (pre-check)

```
LLM generates .gd → gdtoolkit parse → syntax OK?
  → yes: proceed to Godot validation
  → no: feed parse error back to LLM for correction (cheap retry)
```

This avoids expensive Godot headless launches for obviously broken code.

### Use for: dependency extraction (build it ourselves)

Write a thin wrapper (~100 lines) that walks the parse tree to extract:
- `extends` targets (file paths or class names)
- `preload()`/`load()` paths
- `class_name` declarations

This gives us a dependency graph across generated files, enabling:
- Topological ordering of file generation
- Detection of circular dependencies
- Validation that referenced files actually exist in the project

### Don't use for: semantic validation

The toolkit cannot replace Godot's own validation. It doesn't know the engine API, can't type-check, and can't verify runtime behavior. Always follow up with `godot --headless` for real validation.

### Don't use for: the linter/formatter

The linter's naming conventions and style rules aren't useful for LLM-generated code where correctness matters more than style. The formatter has known data-loss bugs. Skip both.
