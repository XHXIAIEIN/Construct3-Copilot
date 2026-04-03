#!/usr/bin/env python3
"""Query ACE schema definitions from Construct3-RAG repo.

Usage:
    python schema.py search {keyword}          # Search all schemas
    python schema.py plugin {name} [ace-id]    # List/get plugin ACEs
    python schema.py behavior {name} [ace-id]  # List/get behavior ACEs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import _resolve from parent directory
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _resolve import resolve_rag_schemas  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SKIP_FILES = {"index.json", "_common.json"}


def _ace_label(ace: dict) -> str:
    """Get display label from ACE, handling both list-name and translated-name."""
    return ace.get("list-name") or ace.get("translated-name") or ace.get("id", "?")


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------
def _schema_dirs(lang: str = "en-US") -> list[tuple[str, Path]]:
    """Return [(schema_type, dir_path)] for plugins and behaviors."""
    root = resolve_rag_schemas(lang)
    result = []
    for kind in ("plugins", "behaviors"):
        d = root / kind
        if d.is_dir():
            result.append((kind, d))
    return result


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_zh_schema(en_path: Path) -> dict | None:
    """Load the zh-CN counterpart of an en-US schema file.

    Returns None if the file does not exist.
    """
    # en_path: .../en-US/plugins/sprite.json  →  .../zh-CN/plugins/sprite.json
    parts = en_path.parts
    try:
        idx = parts.index("en-US")
    except ValueError:
        return None
    zh_path = Path(*parts[:idx]) / "zh-CN" / Path(*parts[idx + 1 :])
    if zh_path.is_file():
        return _load_json(zh_path)
    return None


def _build_zh_ace_map(zh_schema: dict | None) -> dict[str, dict]:
    """Build {ace_id: ace_entry} from zh-CN schema for quick lookup."""
    if zh_schema is None:
        return {}
    mapping: dict[str, dict] = {}
    for ace_type in ("conditions", "actions", "expressions"):
        for ace in zh_schema.get(ace_type, []):
            mapping[ace["id"]] = ace
    return mapping


def load_schema(schema_type: str, name: str) -> tuple[dict, Path]:
    """Load an en-US schema by type and name. Returns (schema, file_path).

    schema_type: 'plugin' or 'behavior' (singular).
    """
    plural = schema_type + "s"
    root = resolve_rag_schemas("en-US")
    schema_dir = root / plural

    if not schema_dir.is_dir():
        print(f"Schema directory not found: {schema_dir}")
        sys.exit(1)

    # Exact match
    path = schema_dir / f"{name.lower()}.json"
    if not path.exists() or path.name in _SKIP_FILES:
        # Fuzzy match
        path = None  # type: ignore[assignment]
        for f in sorted(schema_dir.glob("*.json")):
            if f.name in _SKIP_FILES:
                continue
            if name.lower() in f.stem.lower():
                path = f
                break

    if path is None or not path.exists():
        available = sorted(
            f.stem
            for f in schema_dir.glob("*.json")
            if f.name not in _SKIP_FILES
        )
        print(f"Not found: {name}")
        print(f"  Available: {', '.join(available[:15])}")
        if len(available) > 15:
            print(f"  ... and {len(available) - 15} more")
        sys.exit(1)

    return _load_json(path), path


# ---------------------------------------------------------------------------
# list_aces: Show all ACEs with bilingual labels
# ---------------------------------------------------------------------------
def list_aces(schema: dict, en_path: Path) -> None:
    zh_schema = _load_zh_schema(en_path)
    zh_map = _build_zh_ace_map(zh_schema)

    en_name = schema.get("name", schema.get("id", "?"))
    zh_name = zh_schema.get("name", "") if zh_schema else ""
    header = f"{zh_name} / {en_name}" if zh_name else en_name
    print(f"\n## {header}\n")

    for ace_type in ("conditions", "actions", "expressions"):
        aces = schema.get(ace_type, [])
        if not aces:
            continue
        print(f"### {ace_type.title()} ({len(aces)})\n")
        for ace in aces:
            en_label = _ace_label(ace)
            zh_ace = zh_map.get(ace["id"])
            zh_label = _ace_label(zh_ace) if zh_ace else ""
            label = f"{zh_label} / {en_label}" if zh_label else en_label

            params = ace.get("params", {})
            if isinstance(params, dict):
                param_keys = ", ".join(params.keys())
            else:
                param_keys = ""
            print(f"  `{ace['id']}` - {label} ({param_keys or '-'})")
        print()


# ---------------------------------------------------------------------------
# get_ace: Show ACE details with params table
# ---------------------------------------------------------------------------
def get_ace(schema: dict, ace_id: str, en_path: Path) -> bool:
    zh_schema = _load_zh_schema(en_path)
    zh_map = _build_zh_ace_map(zh_schema)

    for ace_type in ("conditions", "actions", "expressions"):
        for ace in schema.get(ace_type, []):
            if ace_id.lower() not in ace.get("id", "").lower():
                continue

            zh_ace = zh_map.get(ace["id"], {})
            en_label = _ace_label(ace)
            zh_label = _ace_label(zh_ace) if zh_ace else ""
            label = f"{zh_label} / {en_label}" if zh_label else en_label

            print(f"\n### {ace_type[:-1]}: `{ace['id']}` — {label}\n")
            if ace.get("description"):
                print(f"{ace['description']}\n")
            if ace.get("scriptName"):
                print(f"Script: `{ace['scriptName']}`")
            if ace.get("returnType"):
                print(f"Returns: `{ace['returnType']}`")

            params = ace.get("params", {})
            if isinstance(params, dict) and params:
                print("\n| Param | Type | Name | Items |")
                print("|-------|------|------|-------|")
                for pid, pdef in params.items():
                    ptype = pdef.get("type", "any")
                    pname = pdef.get("name", "-")
                    items = pdef.get("items", {})
                    if isinstance(items, dict) and items:
                        items_str = ", ".join(items.keys())
                    else:
                        items_str = "-"
                    print(f"| `{pid}` | {ptype} | {pname} | {items_str} |")
            else:
                print("\n(no parameters)")

            print()
            return True

    print(f"ACE not found: {ace_id}")
    return False


# ---------------------------------------------------------------------------
# search_all: Search by id, en list-name, zh list-name
# ---------------------------------------------------------------------------
def search_all(query: str) -> None:
    q = query.lower()
    print(f"\nSearching: `{query}`\n")

    hits = 0
    for kind, schema_dir in _schema_dirs("en-US"):
        for fpath in sorted(schema_dir.glob("*.json")):
            if fpath.name in _SKIP_FILES:
                continue
            schema = _load_json(fpath)
            zh_schema = _load_zh_schema(fpath)
            zh_map = _build_zh_ace_map(zh_schema)

            for ace_type in ("conditions", "actions", "expressions"):
                for ace in schema.get(ace_type, []):
                    ace_id = ace.get("id", "")
                    en_label = _ace_label(ace)
                    en_list = ace.get("list-name", "")
                    en_trans = ace.get("translated-name", "")
                    zh_ace = zh_map.get(ace_id)
                    zh_label = _ace_label(zh_ace) if zh_ace else ""

                    if (
                        q in ace_id.lower()
                        or q in en_list.lower()
                        or q in en_trans.lower()
                        or q in zh_label.lower()
                    ):
                        label = (
                            f"{zh_label} / {en_label}" if zh_label else en_label
                        )
                        params = ace.get("params", {})
                        if isinstance(params, dict):
                            param_keys = ", ".join(params.keys())
                        else:
                            param_keys = ""
                        # kind is plural e.g. "plugins" → "plugin"
                        print(
                            f"  [{kind[:-1]}:{fpath.stem}] "
                            f"`{ace_id}` - {label} ({param_keys or '-'})"
                        )
                        hits += 1

    if hits == 0:
        print("  (no results)")
    else:
        print(f"\n  {hits} result(s)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "search":
        search_all(sys.argv[2])
    elif cmd in ("plugin", "behavior"):
        schema, fpath = load_schema(cmd, sys.argv[2])
        if len(sys.argv) > 3:
            get_ace(schema, sys.argv[3], fpath)
        else:
            list_aces(schema, fpath)
    else:
        print(__doc__)
        sys.exit(1)
