# Data Source Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace dead `data/` references with live reads from sibling `Construct3-RAG` repo, clean up dead scripts.

**Architecture:** Shared `_resolve.py` module discovers sibling repos via env var → sibling directory convention. `schema.py` and `output.py` adapt to RAG's native schema format (dict-based params, separate en-US/zh-CN files). Dead code moves to `.trash/`.

**Tech Stack:** Python 3.10+, no new dependencies.

---

### Task 1: Create `_resolve.py` — Sibling Repo Discovery

**Files:**
- Create: `.claude/plugins/construct3-copilot/scripts/_resolve.py`

- [ ] **Step 1: Write `_resolve.py`**

```python
#!/usr/bin/env python3
"""
Resolve paths to sibling repositories.

Lookup order:
    1. Environment variable ($C3_RAG_ROOT, $C3_CLIPBOARD_ROOT)
    2. Sibling directory convention ({copilot_repo}/../{sibling}/)
    3. RepoNotFoundError with clone suggestion
"""

import json
import os
import sys
from pathlib import Path

# Copilot repo root: _resolve.py is at scripts/_resolve.py
# scripts/ -> construct3-copilot/ -> plugins/ -> .claude/ -> repo root
_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
_COPILOT_REPO = _PLUGIN_ROOT.parent.parent.parent

_REPOS = {
    "rag": {
        "env": "C3_RAG_ROOT",
        "dirname": "Construct3-RAG",
        "url": "https://github.com/user/Construct3-RAG",
    },
    "clipboard": {
        "env": "C3_CLIPBOARD_ROOT",
        "dirname": "Construct3-Clipboard",
        "url": "https://github.com/user/Construct3-Clipboard",
    },
}


def resolve_repo(name: str) -> Path:
    """Resolve a sibling repo path. Raises SystemExit on failure."""
    cfg = _REPOS.get(name)
    if not cfg:
        _exit_error(f"Unknown repo: {name}", f"Known repos: {', '.join(_REPOS)}")

    # 1. Environment variable
    env_val = os.environ.get(cfg["env"])
    if env_val:
        p = Path(env_val)
        if p.is_dir():
            return p
        _exit_error(
            f"${cfg['env']} is set to '{env_val}' but directory does not exist",
            f"Check the path or unset ${cfg['env']} to use sibling directory convention",
        )

    # 2. Sibling directory
    sibling = _COPILOT_REPO.parent / cfg["dirname"]
    if sibling.is_dir():
        return sibling

    # 3. Not found
    _exit_error(
        f"{cfg['dirname']} not found",
        f"git clone {cfg['url']} \"{_COPILOT_REPO.parent / cfg['dirname']}\"  — or set ${cfg['env']}",
    )


def resolve_rag_root() -> Path:
    """Shorthand for resolve_repo('rag')."""
    return resolve_repo("rag")


def resolve_clipboard_root() -> Path:
    """Shorthand for resolve_repo('clipboard')."""
    return resolve_repo("clipboard")


def resolve_rag_schemas(lang: str = "en-US") -> Path:
    """Return path to c3-schemas/{lang}/ inside Construct3-RAG."""
    rag = resolve_rag_root()
    schemas = rag / "data" / "c3-schemas" / lang
    if not schemas.is_dir():
        _exit_error(
            f"Schema directory not found: {schemas}",
            "Check that Construct3-RAG/data/c3-schemas/ is populated",
        )
    return schemas


def _exit_error(message: str, suggestion: str = "") -> None:
    """Print JSON error and exit 1. Does not return."""
    payload = {"error": message}
    if suggestion:
        payload["suggestion"] = suggestion
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(1)
```

- [ ] **Step 2: Verify path calculation is correct**

Run:
```bash
cd "D:/Users/Administrator/Documents/GitHub/Construct3-Copilot"
python3 -c "
import sys; sys.path.insert(0, '.claude/plugins/construct3-copilot/scripts')
from _resolve import resolve_rag_root, resolve_rag_schemas
print('RAG root:', resolve_rag_root())
print('Schemas:', resolve_rag_schemas())
print('zh-CN:', resolve_rag_schemas('zh-CN'))
"
```

Expected: paths pointing to `D:/Users/Administrator/Documents/GitHub/Construct3-RAG` and its schema subdirs.

- [ ] **Step 3: Commit**

```bash
git add .claude/plugins/construct3-copilot/scripts/_resolve.py
git commit -m "feat: add _resolve.py for sibling repo discovery"
```

---

### Task 2: Rewrite `schema.py` — Read RAG Format

**Files:**
- Modify: `.claude/plugins/construct3-copilot/scripts/query/schema.py`

- [ ] **Step 1: Rewrite `schema.py` to use `_resolve.py` and RAG format**

```python
#!/usr/bin/env python3
"""
Query ACE schema definitions from Construct3-RAG data.

Reads from Construct3-RAG/data/c3-schemas/ (en-US primary, zh-CN on demand).

Usage:
    python schema.py plugin sprite              # List Sprite ACEs
    python schema.py plugin sprite set-animation # Get specific ACE
    python schema.py behavior platform          # List Platform ACEs
    python schema.py search create-object       # Search all schemas
"""

import json
import sys
from pathlib import Path

# Add scripts/ to path for _resolve import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _resolve import resolve_rag_schemas


def _schemas_dir(lang: str = "en-US") -> Path:
    return resolve_rag_schemas(lang)


def _load_zh_schema(schema_type: str, name: str) -> dict | None:
    """Load zh-CN counterpart for Chinese names. Returns None on failure."""
    try:
        zh_dir = _schemas_dir("zh-CN")
    except SystemExit:
        return None
    path = zh_dir / f"{schema_type}s" / f"{name.lower()}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_zh_index(zh_schema: dict | None) -> dict:
    """Build {ace_id: {list-name, display-text, description}} from zh-CN schema."""
    if not zh_schema:
        return {}
    index = {}
    for ace_type in ["conditions", "actions", "expressions"]:
        for ace in zh_schema.get(ace_type, []):
            index[ace.get("id", "")] = ace
    return index


def _param_keys(params) -> list[str]:
    """Extract param IDs from RAG format (dict) or return empty list."""
    if isinstance(params, dict):
        return list(params.keys())
    return []


def _param_display(params) -> str:
    """Format params for one-line display."""
    keys = _param_keys(params)
    return ", ".join(keys) if keys else "-"


def load_schema(schema_type: str, name: str) -> dict:
    schemas = _schemas_dir() / f"{schema_type}s"
    path = schemas / f"{name.lower()}.json"
    if not path.exists():
        # Fuzzy match
        for f in schemas.glob("*.json"):
            if name.lower() in f.stem.lower():
                path = f
                break
    if not path.exists():
        available = [f.stem for f in schemas.glob("*.json") if f.stem != "index" and f.stem != "_common"]
        print(f"❌ Not found: {name}\n   Available: {', '.join(available[:15])}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_aces(schema: dict, zh_index: dict):
    name = schema.get("name", schema.get("id", "?"))
    zh_name = zh_index.get("__plugin_name__", "")
    header = f"{name}" + (f" ({zh_name})" if zh_name else "")
    print(f"\n📦 {header}\n")

    for ace_type in ["conditions", "actions", "expressions"]:
        aces = schema.get(ace_type, [])
        if aces:
            print(f"## {ace_type.title()} ({len(aces)})\n")
            for ace in aces:
                ace_id = ace.get("id", "?")
                params = _param_display(ace.get("params", {}))
                zh_ace = zh_index.get(ace_id, {})
                zh_label = zh_ace.get("list-name", "")
                en_label = ace.get("list-name", "")
                label = f"{zh_label} / {en_label}" if zh_label else en_label
                print(f"  `{ace_id}` - {label} ({params})")
            print()


def get_ace(schema: dict, ace_id: str, zh_index: dict):
    for ace_type in ["conditions", "actions", "expressions"]:
        for ace in schema.get(ace_type, []):
            if ace_id.lower() in ace.get("id", "").lower():
                zh_ace = zh_index.get(ace.get("id", ""), {})
                zh_label = zh_ace.get("list-name", "")
                en_label = ace.get("list-name", "")
                label = f"{zh_label} / {en_label}" if zh_label else en_label
                print(f"\n### {ace_type[:-1]}: `{ace['id']}` — {label}\n")
                print(f"  {ace.get('description', '')}")
                if zh_ace.get("description"):
                    print(f"  {zh_ace['description']}")
                print()

                params = ace.get("params", {})
                if isinstance(params, dict) and params:
                    print("| Parameter | Type | Values |")
                    print("|-----------|------|--------|")
                    for pid, pinfo in params.items():
                        ptype = pinfo.get("type", "any")
                        items = pinfo.get("items", {})
                        if isinstance(items, dict) and items:
                            vals = ", ".join(items.keys())
                        else:
                            vals = "-"
                        print(f"| `{pid}` | {ptype} | {vals} |")
                else:
                    print("(no parameters)")
                return True
    print(f"❌ ACE not found: {ace_id}")
    return False


def search_all(query: str):
    print(f"\n🔍 Searching: `{query}`\n")
    schemas = _schemas_dir()
    zh_schemas = {}
    try:
        zh_dir = _schemas_dir("zh-CN")
    except SystemExit:
        zh_dir = None

    for schema_type in ["plugins", "behaviors"]:
        schema_dir = schemas / schema_type
        if not schema_dir.exists():
            continue
        for f in schema_dir.glob("*.json"):
            if f.stem in ("index", "_common"):
                continue
            with open(f, "r", encoding="utf-8") as file:
                schema = json.load(file)
            # Load zh counterpart for search matching
            zh_index = {}
            if zh_dir:
                zh_path = zh_dir / schema_type / f.name
                if zh_path.exists():
                    with open(zh_path, "r", encoding="utf-8") as zf:
                        zh_schema = json.load(zf)
                    zh_index = _build_zh_index(zh_schema)

            for ace_type in ["conditions", "actions"]:
                for ace in schema.get(ace_type, []):
                    ace_id = ace.get("id", "")
                    en_name = ace.get("list-name", "")
                    zh_ace = zh_index.get(ace_id, {})
                    zh_name = zh_ace.get("list-name", "")
                    if (
                        query.lower() in ace_id.lower()
                        or query.lower() in en_name.lower()
                        or query.lower() in zh_name.lower()
                    ):
                        params = _param_display(ace.get("params", {}))
                        label = f"{zh_name} / {en_name}" if zh_name else en_name
                        print(f"  [{schema_type[:-1]}:{f.stem}] `{ace_id}` - {label} ({params})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "search":
        search_all(sys.argv[2])
    elif cmd in ["plugin", "behavior"]:
        schema = load_schema(cmd, sys.argv[2])
        zh_schema = _load_zh_schema(cmd, sys.argv[2])
        zh_index = _build_zh_index(zh_schema)
        # Also store plugin-level zh name
        if zh_schema:
            zh_index["__plugin_name__"] = zh_schema.get("name", "")
        if len(sys.argv) > 3:
            get_ace(schema, sys.argv[3], zh_index)
        else:
            list_aces(schema, zh_index)
    else:
        print(__doc__)
```

- [ ] **Step 2: Test schema.py with RAG data**

Run:
```bash
cd "D:/Users/Administrator/Documents/GitHub/Construct3-Copilot"
python3 .claude/plugins/construct3-copilot/scripts/query/schema.py search sprite
python3 .claude/plugins/construct3-copilot/scripts/query/schema.py plugin sprite set-animation
python3 .claude/plugins/construct3-copilot/scripts/query/schema.py behavior platform
```

Expected: ACE listings with English + Chinese labels, params as dict keys.

- [ ] **Step 3: Commit**

```bash
git add .claude/plugins/construct3-copilot/scripts/query/schema.py
git commit -m "refactor: schema.py reads from Construct3-RAG sibling repo"
```

---

### Task 3: Update `output.py` — Layer 3 Schema Path

**Files:**
- Modify: `.claude/plugins/construct3-copilot/scripts/validate/output.py` (lines 432-513)

- [ ] **Step 1: Update `SchemaInfo` to handle RAG dict-params format**

Replace the `SchemaInfo` class (lines 432-442):

```python
class SchemaInfo:
    def __init__(self, name: str, schema: dict):
        self.name = name
        self.schema = schema
        self._ace_index = {
            "conditions": {a.get("id"): a for a in schema.get("conditions", [])},
            "actions": {a.get("id"): a for a in schema.get("actions", [])},
        }

    def get_ace(self, ace_type: str, ace_id: str):
        return self._ace_index.get(ace_type, {}).get(ace_id)
```

No change needed — `SchemaInfo` indexes by ACE `id`, which is the same in both formats. The `get_ace` return value is the raw ACE dict, and `validate_params` is the consumer.

- [ ] **Step 2: Update `SchemaIndex.__init__` and `_load_schemas` to use `_resolve.py`**

Replace `SchemaIndex` (lines 445-513):

```python
class SchemaIndex:
    def __init__(self):
        self.schemas_dir = None
        self.plugin_map = {}
        self.behavior_map = {}
        self._available = False
        self._load_schemas()

    @property
    def available(self) -> bool:
        return self._available

    def _normalize(self, name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def _load_schemas(self):
        try:
            # Import _resolve from scripts/
            scripts_dir = Path(__file__).resolve().parent.parent
            import importlib.util
            spec = importlib.util.spec_from_file_location("_resolve", scripts_dir / "_resolve.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.schemas_dir = mod.resolve_rag_schemas("en-US")
        except (SystemExit, Exception):
            # RAG not available — layer 3 will be skipped
            return

        self._available = True
        plugins_dir = self.schemas_dir / "plugins"
        behaviors_dir = self.schemas_dir / "behaviors"
        if plugins_dir.exists():
            for path in plugins_dir.glob("*.json"):
                if path.stem in ("index", "_common"):
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                info = SchemaInfo(schema.get("name", path.stem), schema)
                for key in self._schema_keys(schema, path.stem):
                    self.plugin_map[key] = info
        if behaviors_dir.exists():
            for path in behaviors_dir.glob("*.json"):
                if path.stem in ("index", "_common"):
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                info = SchemaInfo(schema.get("name", path.stem), schema)
                for key in self._schema_keys(schema, path.stem):
                    self.behavior_map[key] = info

    def _schema_keys(self, schema: dict, stem: str):
        keys = {stem}
        for key in [schema.get("id"), schema.get("name")]:
            if key:
                keys.add(key)
        return {self._normalize(k) for k in keys if k}

    def find_schema(self, item: dict):
        behavior_type = item.get("behaviorType")
        if behavior_type:
            return self.behavior_map.get(self._normalize(behavior_type))
        obj_class = item.get("objectClass")
        if not obj_class:
            return None
        return self.plugin_map.get(self._normalize(obj_class))

    def validate_params(self, ace: dict, params: dict, prefix: str):
        warnings = []
        schema_params = ace.get("params", {})
        # RAG format: params is a dict {param_id: {type, name, desc, items?}}
        if isinstance(schema_params, dict):
            schema_ids = set(schema_params.keys())
        else:
            # Shouldn't happen with RAG format, but defensive
            schema_ids = {p.get("id") for p in schema_params if p.get("id")}
        for pid in schema_ids:
            if pid not in params:
                warnings.append(f"{prefix}: missing parameter '{pid}'")
        for pid in params.keys():
            if pid not in schema_ids:
                warnings.append(f"{prefix}: unknown parameter '{pid}'")
        # Validate enum values
        if isinstance(schema_params, dict):
            for pid, pinfo in schema_params.items():
                items = pinfo.get("items", {})
                if not isinstance(items, dict) or not items or pid not in params:
                    continue
                value = params.get(pid)
                if isinstance(value, str):
                    normalized = value.strip('"')
                    if normalized in items:
                        continue
                    if not re.search(r"[()+\\-*/&.]", value):
                        warnings.append(f"{prefix}.{pid}: value '{value}' not in {list(items.keys())}")
        return warnings
```

- [ ] **Step 3: Add skip warning when RAG unavailable**

Find the `_validate_layer3` call site in `output.py`. Where `SchemaIndex` is instantiated, add a check:

In the validator's `run` method or wherever layer 3 is invoked, the `SchemaIndex` already handles missing gracefully via `plugins_dir.exists()` — but now we should print a warning. Find where `SchemaIndex()` is called and wrap:

```python
schema_index = SchemaIndex()
if not schema_index.available:
    warnings.append("⚠ Schema cross-check skipped: Construct3-RAG not found")
```

(Exact location depends on how the validator calls layer 3 — adapt to the existing control flow.)

- [ ] **Step 4: Test output.py with RAG schemas**

Run:
```bash
cd "D:/Users/Administrator/Documents/GitHub/Construct3-Copilot"
echo '{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"block","conditions":[{"id":"on-start-of-layout","type":"system","objectClass":"System"}],"actions":[{"id":"set-animation","type":"act","objectClass":"Sprite","parameters":{"animation":"\"Run\"","from":"\"beginning\""}}]}]}' | python3 .claude/plugins/construct3-copilot/scripts/validate/output.py
```

Expected: Validation runs all 3 layers. Layer 3 should find Sprite schema and validate `set-animation` params.

- [ ] **Step 5: Commit**

```bash
git add .claude/plugins/construct3-copilot/scripts/validate/output.py
git commit -m "refactor: output.py layer 3 reads schemas from Construct3-RAG"
```

---

### Task 4: Update `health.py` — Check RAG Repo

**Files:**
- Modify: `.claude/plugins/construct3-copilot/scripts/infra/health.py`

- [ ] **Step 1: Replace `check_local_data()` with RAG repo check**

Replace the `check_local_data` function (lines 41-62):

```python
def check_local_data() -> dict:
    """Check that Construct3-RAG sibling repo and schema data are accessible."""
    try:
        scripts_dir = Path(__file__).resolve().parent.parent
        import importlib.util
        spec = importlib.util.spec_from_file_location("_resolve", scripts_dir / "_resolve.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        schemas_dir = mod.resolve_rag_schemas("en-US")
    except (SystemExit, Exception):
        return {
            "source": "Construct3-RAG",
            "available": False,
            "plugins": 0,
        }

    plugins_dir = schemas_dir / "plugins"
    if plugins_dir.exists():
        plugin_count = len([f for f in plugins_dir.glob("*.json") if f.stem not in ("index", "_common")])
        available = plugin_count > 0
    else:
        plugin_count = 0
        available = False

    return {
        "source": "Construct3-RAG",
        "schemas_dir": str(schemas_dir),
        "available": available,
        "plugins": plugin_count,
    }
```

- [ ] **Step 2: Test health.py**

Run:
```bash
cd "D:/Users/Administrator/Documents/GitHub/Construct3-Copilot"
python3 .claude/plugins/construct3-copilot/scripts/infra/health.py --brief
python3 .claude/plugins/construct3-copilot/scripts/infra/health.py
```

Expected brief: `RAG:- Clipboard:- Local:+` (RAG/Clipboard services not running, but schema data found).

- [ ] **Step 3: Commit**

```bash
git add .claude/plugins/construct3-copilot/scripts/infra/health.py
git commit -m "refactor: health.py checks Construct3-RAG repo instead of local data/"
```

---

### Task 5: Move Dead Code to `.trash/`

**Files:**
- Move: `data/schemas/`, `data/project_analysis/`
- Move: `scripts/query/examples.py`, `scripts/generate/clipboard.py`
- Move: `scripts/infra/paste.py`, `scripts/infra/bridge.py`

- [ ] **Step 1: Create `.trash/` target directory and move files**

```bash
cd "D:/Users/Administrator/Documents/GitHub/Construct3-Copilot"
mkdir -p .trash/data-source-redesign-2026-04-04

# Dead data
mv data/schemas .trash/data-source-redesign-2026-04-04/schemas
mv data/project_analysis .trash/data-source-redesign-2026-04-04/project_analysis

# Dead scripts
mv .claude/plugins/construct3-copilot/scripts/query/examples.py .trash/data-source-redesign-2026-04-04/examples.py
mv .claude/plugins/construct3-copilot/scripts/generate/clipboard.py .trash/data-source-redesign-2026-04-04/clipboard.py
mv .claude/plugins/construct3-copilot/scripts/infra/paste.py .trash/data-source-redesign-2026-04-04/paste.py
mv .claude/plugins/construct3-copilot/scripts/infra/bridge.py .trash/data-source-redesign-2026-04-04/bridge.py
```

- [ ] **Step 2: Remove empty `data/` if nothing remains**

```bash
# Check if data/ has anything left
ls data/
# If empty (only index.json or nothing useful), remove it
rm -rf data/
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: move dead data and scripts to .trash/"
```

---

### Task 6: Update SKILL.md and CLAUDE.md References

**Files:**
- Modify: `.claude/plugins/construct3-copilot/skills/search/SKILL.md`
- Modify: `.claude/plugins/construct3-copilot/skills/create/SKILL.md`
- Modify: `.claude/plugins/construct3-copilot/CLAUDE.md`

- [ ] **Step 1: Update search SKILL.md — remove `examples.py` references**

In `skills/search/SKILL.md`, remove lines 44-47 (the examples.py commands):

```markdown
# Real-world usage patterns
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py action {ace_id}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py condition {ace_id}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py top actions 20
```

Also update the description (line 2-3) to remove "real-world usage patterns from 403 official example projects" reference.

- [ ] **Step 2: Update create SKILL.md — remove `examples.py` and `clipboard.py` references**

In `skills/create/SKILL.md`, remove line 77 (the examples.py command):

```markdown
# 2. Usage patterns
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/query/examples.py action {ace_id}
```

Also remove the clipboard.py generate reference if present (currently `clipboard_service.py` is used instead, which stays).

- [ ] **Step 3: Update CLAUDE.md workflow — remove examples.py step**

In `CLAUDE.md`, the Mandatory Workflow section references `examples.py` indirectly via "When RAG is online: also run..." — verify and remove any stale references. The workflow steps should be:

```
0. DISCOVER: scripts/infra/health.py --brief
1. QUERY: scripts/query/schema.py (mandatory)
   - When RAG service online: also run scripts/query/rag.py search
2. GENERATE: Author JSON directly, or use clipboard_service.py when online
3. VALIDATE: scripts/validate/output.py
4. FIX: On failure, fix and re-validate
```

- [ ] **Step 4: Commit**

```bash
git add .claude/plugins/construct3-copilot/skills/search/SKILL.md
git add .claude/plugins/construct3-copilot/skills/create/SKILL.md
git add .claude/plugins/construct3-copilot/CLAUDE.md
git commit -m "docs: remove dead script references from skills and CLAUDE.md"
```

---

### Task 7: End-to-End Verification

- [ ] **Step 1: Run health check**

```bash
cd "D:/Users/Administrator/Documents/GitHub/Construct3-Copilot"
python3 .claude/plugins/construct3-copilot/scripts/infra/health.py
```

Expected: `local_data.source` = "Construct3-RAG", `local_data.available` = true, `local_data.plugins` > 0.

- [ ] **Step 2: Run schema search**

```bash
python3 .claude/plugins/construct3-copilot/scripts/query/schema.py search "collision"
python3 .claude/plugins/construct3-copilot/scripts/query/schema.py plugin sprite
python3 .claude/plugins/construct3-copilot/scripts/query/schema.py behavior platform set-max-speed
```

Expected: Results with bilingual labels and dict-format params.

- [ ] **Step 3: Run validation with schema cross-check**

```bash
echo '{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"block","conditions":[{"id":"on-start-of-layout","type":"system","objectClass":"System"}],"actions":[{"id":"set-animation","type":"act","objectClass":"Sprite","parameters":{"animation":"\"Idle\"","from":"\"beginning\""}}]}]}' | python3 .claude/plugins/construct3-copilot/scripts/validate/output.py
```

Expected: PASSED with 3 layers, no schema warnings.

- [ ] **Step 4: Verify no references to dead paths remain**

```bash
grep -r "data/schemas" .claude/plugins/construct3-copilot/ --include="*.py" --include="*.md"
grep -r "data/project_analysis" .claude/plugins/construct3-copilot/ --include="*.py" --include="*.md"
grep -r "examples\.py" .claude/plugins/construct3-copilot/ --include="*.md"
grep -r "clipboard\.py" .claude/plugins/construct3-copilot/skills/ --include="*.md"
grep -r "paste\.py\|bridge\.py" .claude/plugins/construct3-copilot/ --include="*.md"
```

Expected: No matches (all dead references cleaned up).

- [ ] **Step 5: Commit verification pass (if any fixes needed)**

```bash
git add -A
git commit -m "fix: clean up remaining dead references"
```
