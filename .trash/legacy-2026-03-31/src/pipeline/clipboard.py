# clipboard.py
"""
Construct 3 Event Sheet JSON Generator

Zero-hallucination event sheet generation with:
1. Schema-driven ACE validation
2. Structured JSON output (clipboard format)
3. Copy-paste ready for Construct 3

Clipboard format reference: docs/knowledge/clipboard-format.md

Key points:
- No sid needed (unlike project file format)
- All parameter values are strings
- objectClass corresponds to object type names in the project
- behaviorType corresponds to the behavior's name field
- variable's comment field is required (can be empty string)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .prompts import CLIPBOARD_FORMAT_REFERENCE, EVENT_JSON_GENERATION_PROMPT

# ---------------------------------------------------------------------------
# Validation error templates
# ---------------------------------------------------------------------------

VALIDATION_ERRORS: dict[str, str] = {
    "json_parse": "JSON parse error: {error}",
    "missing_clipboard_header": "Missing 'is-c3-clipboard-data': true",
    "invalid_clipboard_type": "Invalid clipboard type: {type}",
    "items_not_array": "'items' must be an array",
    "invalid_event_type": "{path}: invalid eventType: {type}",
    "comment_missing_text": "{path}: comment missing 'text' field",
    "variable_missing_name": "{path}: variable missing 'name'",
    "invalid_var_type": "{path}: invalid variable type: {type}",
    "variable_suggest_initial": "{path}: variable should set 'initialValue'",
    "variable_suggest_comment": "{path}: variable should add 'comment' field (can be empty string)",
    "group_missing_title": "{path}: group missing 'title'",
    "function_missing_name": "{path}: function-block missing 'functionName'",
    "invalid_return_type": "{path}: invalid return type: {type}",
    "condition_missing_id": "{path}: condition missing 'id'",
    "condition_missing_object": "{path}: condition missing 'objectClass'",
    "invalid_comparison": "{path}: invalid comparison operator: {value}",
    "action_comment_missing_text": "{path}: action comment missing 'text'",
    "action_missing_id": "{path}: action missing 'id'",
    "action_missing_object": "{path}: action missing 'objectClass'",
    "no_json_extracted": "Could not extract valid JSON from response",
    "no_schema": "(no related schema)",
}

PLUGIN_KIND_LABELS: dict[str, str] = {
    "plugin": "Plugin",
    "behavior": "Behavior",
}

ACE_SECTION_LABELS_SHORT: dict[str, str] = {
    "conditions": "Condition",
    "actions": "Action",
    "expressions": "Expression",
    "properties": "Property",
}

# ============================================================
# Schema Loader & Cache
# ============================================================


@dataclass
class ACEParam:
    """ACE parameter definition"""

    id: str
    type: str
    name_zh: str
    name_en: str
    initial_value: Optional[str] = None
    items: Optional[List[str]] = None  # for combo type


@dataclass
class ACEDefinition:
    """Action/Condition/Expression definition"""

    id: str
    name_zh: str
    name_en: str
    description_zh: str
    description_en: str
    params: List[ACEParam] = field(default_factory=list)
    is_trigger: bool = False
    category: Optional[str] = None


@dataclass
class PluginSchema:
    """Plugin or Behavior schema"""

    id: str
    original_id: str
    name_zh: str
    name_en: str
    conditions: Dict[str, ACEDefinition] = field(default_factory=dict)
    actions: Dict[str, ACEDefinition] = field(default_factory=dict)
    expressions: Dict[str, ACEDefinition] = field(default_factory=dict)


class SchemaLoader:
    """Load and cache Construct 3 ACE schemas"""

    def __init__(self, schema_dir: str = None):
        if schema_dir is None:
            from src.config import DATA_DIR
            schema_dir = DATA_DIR / "schemas"
        self.schema_dir = Path(schema_dir)
        self._plugin_cache: Dict[str, PluginSchema] = {}
        self._behavior_cache: Dict[str, PluginSchema] = {}
        self._all_plugins_loaded = False
        self._all_behaviors_loaded = False
        self._keyword_index: Dict[str, Tuple[str, str]] = {}
        self._keyword_index_built = False

    def _parse_params(self, params_data: List[Dict]) -> List[ACEParam]:
        result = []
        for p in params_data:
            param = ACEParam(
                id=p.get("id", ""),
                type=p.get("type", "any"),
                name_zh=p.get("name_zh", ""),
                name_en=p.get("name_en", ""),
                initial_value=p.get("initialValue"),
                items=p.get("items"),
            )
            result.append(param)
        return result

    def _parse_ace_list(self, ace_list: List[Dict]) -> Dict[str, ACEDefinition]:
        result = {}
        for item in ace_list:
            ace = ACEDefinition(
                id=item.get("id", ""),
                name_zh=item.get("name_zh", ""),
                name_en=item.get("name_en", ""),
                description_zh=item.get("description_zh", ""),
                description_en=item.get("description_en", ""),
                params=self._parse_params(item.get("params", [])),
                is_trigger=item.get("isTrigger", False),
                category=item.get("category"),
            )
            result[ace.id] = ace
        return result

    def _load_schema_file(self, filepath: Path) -> Optional[PluginSchema]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PluginSchema(
                id=data.get("id", ""),
                original_id=data.get("originalId", ""),
                name_zh=data.get("name_zh", ""),
                name_en=data.get("name_en", ""),
                conditions=self._parse_ace_list(data.get("conditions", [])),
                actions=self._parse_ace_list(data.get("actions", [])),
                expressions=self._parse_ace_list(data.get("expressions", [])),
            )
        except Exception as e:
            print(f"Error loading schema {filepath}: {e}")
            return None

    def load_plugin(self, plugin_id: str) -> Optional[PluginSchema]:
        plugin_id = plugin_id.lower()
        if plugin_id in self._plugin_cache:
            return self._plugin_cache[plugin_id]
        filepath = self.schema_dir / "plugins" / f"{plugin_id}.json"
        if filepath.exists():
            schema = self._load_schema_file(filepath)
            if schema:
                self._plugin_cache[plugin_id] = schema
                return schema
        return None

    def load_behavior(self, behavior_id: str) -> Optional[PluginSchema]:
        behavior_id = behavior_id.lower()
        if behavior_id in self._behavior_cache:
            return self._behavior_cache[behavior_id]
        filepath = self.schema_dir / "behaviors" / f"{behavior_id}.json"
        if filepath.exists():
            schema = self._load_schema_file(filepath)
            if schema:
                self._behavior_cache[behavior_id] = schema
                return schema
        return None

    def load_all_plugins(self) -> Dict[str, PluginSchema]:
        if self._all_plugins_loaded:
            return self._plugin_cache
        plugins_dir = self.schema_dir / "plugins"
        if plugins_dir.exists():
            for f in plugins_dir.glob("*.json"):
                if f.name != "index.json":
                    self.load_plugin(f.stem)
        self._all_plugins_loaded = True
        return self._plugin_cache

    def load_all_behaviors(self) -> Dict[str, PluginSchema]:
        if self._all_behaviors_loaded:
            return self._behavior_cache
        behaviors_dir = self.schema_dir / "behaviors"
        if behaviors_dir.exists():
            for f in behaviors_dir.glob("*.json"):
                if f.name != "index.json":
                    self.load_behavior(f.stem)
        self._all_behaviors_loaded = True
        return self._behavior_cache

    def build_keyword_index(self) -> Dict[str, Tuple[str, str]]:
        if self._keyword_index_built:
            return self._keyword_index
        self.load_all_plugins()
        self.load_all_behaviors()
        for schema_id, schema in self._plugin_cache.items():
            if schema.name_zh:
                self._keyword_index[schema.name_zh.lower()] = (schema_id, "plugin")
            if schema.name_en:
                self._keyword_index[schema.name_en.lower()] = (schema_id, "plugin")
            self._keyword_index[schema_id.lower()] = (schema_id, "plugin")
        for schema_id, schema in self._behavior_cache.items():
            if schema.name_zh:
                self._keyword_index[schema.name_zh.lower()] = (schema_id, "behavior")
            if schema.name_en:
                self._keyword_index[schema.name_en.lower()] = (schema_id, "behavior")
            self._keyword_index[schema_id.lower()] = (schema_id, "behavior")
        self._keyword_index_built = True
        return self._keyword_index

    def find_schema_by_keyword(self, keyword: str) -> Optional[Tuple[str, str]]:
        self.build_keyword_index()
        keyword_lower = keyword.lower()
        if keyword_lower in self._keyword_index:
            return self._keyword_index[keyword_lower]
        for k, v in self._keyword_index.items():
            if keyword_lower in k or k in keyword_lower:
                return v
        return None

    def search_ace(self, query: str, ace_type: str = "all") -> List[Tuple[str, str, ACEDefinition]]:
        self.load_all_plugins()
        self.load_all_behaviors()
        query_lower = query.lower()
        results = []
        for plugin_id, schema in {**self._plugin_cache, **self._behavior_cache}.items():
            if ace_type in ("all", "condition"):
                for ace in schema.conditions.values():
                    if query_lower in ace.id or query_lower in ace.name_zh or query_lower in ace.name_en.lower():
                        results.append((plugin_id, "condition", ace))
            if ace_type in ("all", "action"):
                for ace in schema.actions.values():
                    if query_lower in ace.id or query_lower in ace.name_zh or query_lower in ace.name_en.lower():
                        results.append((plugin_id, "action", ace))
            if ace_type in ("all", "expression"):
                for ace in schema.expressions.values():
                    if query_lower in ace.id or query_lower in ace.name_zh or query_lower in ace.name_en.lower():
                        results.append((plugin_id, "expression", ace))
        return results


# ============================================================
# Clipboard JSON Validator
# ============================================================


class ClipboardValidator:
    """Validate Construct 3 clipboard JSON format"""

    VALID_CLIPBOARD_TYPES = {
        "events", "conditions", "actions",
        "object-types", "world-instances",
        "layouts", "event-sheets", "timelines", "flowcharts",
    }
    VALID_EVENT_TYPES = {"comment", "variable", "group", "block", "function-block"}
    VALID_VAR_TYPES = {"number", "string", "boolean"}
    VALID_FUNCTION_RETURN_TYPES = {"none", "number", "string", "any"}
    COMPARISON_OPERATORS = {0, 1, 2, 3, 4, 5}

    def __init__(self, schema_loader: SchemaLoader):
        self.schema = schema_loader
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, json_str: str) -> Tuple[bool, List[str], List[str]]:
        self.errors = []
        self.warnings = []
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            self.errors.append(VALIDATION_ERRORS["json_parse"].format(error=e))
            return False, self.errors, self.warnings

        if not data.get("is-c3-clipboard-data"):
            self.errors.append(VALIDATION_ERRORS["missing_clipboard_header"])
        clip_type = data.get("type")
        if clip_type not in self.VALID_CLIPBOARD_TYPES:
            self.errors.append(VALIDATION_ERRORS["invalid_clipboard_type"].format(type=clip_type))
        items = data.get("items", [])
        if not isinstance(items, list):
            self.errors.append(VALIDATION_ERRORS["items_not_array"])
            return False, self.errors, self.warnings

        if clip_type == "events":
            for i, item in enumerate(items):
                self._validate_event(item, f"items[{i}]")
        elif clip_type == "conditions":
            for i, item in enumerate(items):
                self._validate_condition(item, f"items[{i}]")
        elif clip_type == "actions":
            for i, item in enumerate(items):
                self._validate_action(item, f"items[{i}]")
        elif clip_type == "object-types":
            for i, item in enumerate(items):
                self._validate_object_type(item, f"items[{i}]")
        elif clip_type == "event-sheets":
            for i, item in enumerate(items):
                if "name" not in item:
                    self.errors.append(f"items[{i}]: missing 'name' field")
                if "events" not in item:
                    self.warnings.append(f"items[{i}]: missing 'events' field (should be array)")

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_event(self, event: Dict, path: str):
        event_type = event.get("eventType")
        if event_type not in self.VALID_EVENT_TYPES:
            self.errors.append(VALIDATION_ERRORS["invalid_event_type"].format(path=path, type=event_type))
            return
        if event_type == "comment":
            if "text" not in event:
                self.errors.append(VALIDATION_ERRORS["comment_missing_text"].format(path=path))
        elif event_type == "variable":
            self._validate_variable(event, path)
        elif event_type == "group":
            self._validate_group(event, path)
        elif event_type == "block":
            self._validate_block(event, path)
        elif event_type == "function-block":
            self._validate_function_block(event, path)

    def _validate_variable(self, var: Dict, path: str):
        if "name" not in var:
            self.errors.append(VALIDATION_ERRORS["variable_missing_name"].format(path=path))
        if var.get("type") not in self.VALID_VAR_TYPES:
            self.errors.append(VALIDATION_ERRORS["invalid_var_type"].format(path=path, type=var.get("type")))
        if "initialValue" not in var:
            self.warnings.append(VALIDATION_ERRORS["variable_suggest_initial"].format(path=path))
        if "comment" not in var:
            self.warnings.append(VALIDATION_ERRORS["variable_suggest_comment"].format(path=path))

    def _validate_group(self, group: Dict, path: str):
        if "title" not in group:
            self.errors.append(VALIDATION_ERRORS["group_missing_title"].format(path=path))
        for i, child in enumerate(group.get("children", [])):
            self._validate_event(child, f"{path}.children[{i}]")

    def _validate_block(self, block: Dict, path: str):
        for i, cond in enumerate(block.get("conditions", [])):
            self._validate_condition(cond, f"{path}.conditions[{i}]")
        for i, action in enumerate(block.get("actions", [])):
            self._validate_action(action, f"{path}.actions[{i}]")
        for i, child in enumerate(block.get("children", [])):
            self._validate_event(child, f"{path}.children[{i}]")

    def _validate_function_block(self, func: Dict, path: str):
        if "functionName" not in func:
            self.errors.append(VALIDATION_ERRORS["function_missing_name"].format(path=path))
        ret_type = func.get("functionReturnType", "none")
        if ret_type not in self.VALID_FUNCTION_RETURN_TYPES:
            self.errors.append(VALIDATION_ERRORS["invalid_return_type"].format(path=path, type=ret_type))
        self._validate_block(func, path)

    def _validate_condition(self, cond: Dict, path: str):
        if "id" not in cond and "callFunction" not in cond:
            self.errors.append(VALIDATION_ERRORS["condition_missing_id"].format(path=path))
            return
        if "objectClass" not in cond and "callFunction" not in cond:
            self.errors.append(VALIDATION_ERRORS["condition_missing_object"].format(path=path))
        params = cond.get("parameters", {})
        if "comparison" in params:
            if params["comparison"] not in self.COMPARISON_OPERATORS:
                self.errors.append(VALIDATION_ERRORS["invalid_comparison"].format(path=path, value=params["comparison"]))

    def _validate_action(self, action: Dict, path: str):
        if action.get("type") == "comment":
            if "text" not in action:
                self.errors.append(VALIDATION_ERRORS["action_comment_missing_text"].format(path=path))
            return
        if "callFunction" in action:
            return
        if "id" not in action:
            self.errors.append(VALIDATION_ERRORS["action_missing_id"].format(path=path))
            return
        if "objectClass" not in action:
            self.errors.append(VALIDATION_ERRORS["action_missing_object"].format(path=path))

    def _validate_object_type(self, obj: Dict, path: str):
        if "name" not in obj:
            self.errors.append(f"{path}: missing 'name' field")
        if "plugin-id" not in obj:
            self.errors.append(f"{path}: missing 'plugin-id' field")
        has_singleton = "singleglobal-inst" in obj
        has_nonworld = "nonworld-inst" in obj
        has_animations = "animations" in obj
        variant_count = sum([has_singleton, has_nonworld, has_animations])
        if variant_count == 0:
            self.warnings.append(f"{path}: no variant key ('singleglobal-inst', 'nonworld-inst', or 'animations')")
        elif variant_count > 1:
            self.errors.append(f"{path}: multiple variant keys present; only one allowed")


# ============================================================
# Object Type Builder
# ============================================================


class ObjectTypeBuilder:
    """Build Construct 3 object-types clipboard JSON."""

    SINGLETON_PLUGIN_IDS: Set[str] = {
        "Keyboard", "Mouse", "Touch", "Gamepad",
        "Audio", "Browser", "AJAX", "XHR2",
        "LocalStorage", "SessionStorage",
        "Multiplayer", "AdvancedRandom", "Date",
        "Cryptography", "CSV", "Internationalization",
        "PlatformInfo", "ShareDialog", "SpeechSynthesis",
        "SpeechRecognition", "NodeWebkit", "FileSystem",
        "FileChooser", "Clipboard", "MIDI",
        "Geolocation", "Bluetooth",
    }

    NONWORLD_PLUGIN_IDS: Set[str] = {
        "Arr", "Dictionary", "BinaryData",
        "JSON", "XML", "Function",
    }

    _BLANK_ANIMATION: Dict[str, Any] = {
        "items": [{
            "frames": [{
                "width": 32, "height": 32,
                "originX": 0.5, "originY": 0.5,
                "originalSource": "",
                "exportFormat": "lossless",
                "exportQuality": 0.8,
                "fileType": "image/png",
                "imageDataIndex": 0,
                "useCollisionPoly": True,
                "duration": 1,
                "tag": "",
            }],
            "name": "Animation 1",
            "isLooping": False,
            "isPingPong": False,
            "repeatCount": 1,
            "repeatTo": 0,
            "speed": 5,
        }],
        "subfolders": [],
        "name": "Animations",
    }

    def build(self, name: str, plugin_id: str, *, behaviors=None, effects=None,
              instance_vars=None, is_global: bool = False) -> Dict[str, Any]:
        item: Dict[str, Any] = {"name": name, "plugin-id": plugin_id}
        if plugin_id in self.SINGLETON_PLUGIN_IDS:
            item["singleglobal-inst"] = {"type": plugin_id, "properties": {}, "tags": ""}
        elif plugin_id in self.NONWORLD_PLUGIN_IDS:
            item["isGlobal"] = is_global
            item["editorNewInstanceIsReplica"] = True
            item["instanceVariables"] = instance_vars or []
            item["nonworld-inst"] = {"type": plugin_id, "properties": {}, "tags": "", "instanceVariables": {}}
        else:
            item["isGlobal"] = is_global
            item["editorNewInstanceIsReplica"] = True
            item["instanceVariables"] = instance_vars or []
            item["behaviorTypes"] = behaviors or []
            item["effectTypes"] = effects or []
            item["animations"] = self._BLANK_ANIMATION
        return item

    def build_clipboard(self, objects: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"is-c3-clipboard-data": True, "type": "object-types", "families": [], "items": objects, "folders": []}

    def build_from_spec(self, specs: List[Dict[str, Any]], schema_loader: Optional[SchemaLoader] = None) -> Dict[str, Any]:
        items = []
        for spec in specs:
            plugin_name = spec.get("plugin", "Sprite")
            plugin_id = self._resolve_plugin_id(plugin_name, schema_loader)
            behaviors = self._resolve_behaviors(spec.get("behaviors", []), schema_loader)
            effects = [{"id": e.lower(), "name": e} for e in spec.get("effects", [])]
            item = self.build(
                spec.get("name", "Object"), plugin_id,
                behaviors=behaviors, effects=effects,
                instance_vars=spec.get("instance_vars", []),
                is_global=spec.get("is_global", False),
            )
            items.append(item)
        return self.build_clipboard(items)

    def _resolve_plugin_id(self, plugin_name: str, schema_loader: Optional[SchemaLoader]) -> str:
        if schema_loader:
            result = schema_loader.find_schema_by_keyword(plugin_name)
            if result:
                schema_id, _ = result
                schema = schema_loader.load_plugin(schema_id)
                if schema and schema.original_id:
                    return schema.original_id
        return plugin_name

    def _resolve_behaviors(self, names: List[str], schema_loader: Optional[SchemaLoader]) -> List[Dict[str, str]]:
        result = []
        for name in names:
            behavior_id = self._find_behavior_original_id(name, schema_loader)
            result.append({"behaviorId": behavior_id, "name": name})
        return result

    def _find_behavior_original_id(self, name: str, schema_loader: Optional[SchemaLoader]) -> str:
        if not schema_loader:
            return name
        schema_loader.build_keyword_index()
        name_norm = re.sub(r"[\s_-]", "", name).lower()
        for keyword, (schema_id, kind) in schema_loader._keyword_index.items():
            if kind != "behavior":
                continue
            if keyword.replace(" ", "") == name_norm:
                schema = schema_loader.load_behavior(schema_id)
                if schema and schema.original_id:
                    return schema.original_id
        found = schema_loader.find_schema_by_keyword(name)
        if found:
            schema_id, kind = found
            if kind == "behavior":
                schema = schema_loader.load_behavior(schema_id)
                if schema and schema.original_id:
                    return schema.original_id
        return name


# ============================================================
# JSON Extractor
# ============================================================


def extract_json_from_response(response: str) -> Optional[str]:
    """Extract JSON from LLM response (handles code blocks and raw JSON)."""
    code_block_pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
    matches = re.findall(code_block_pattern, response)
    if matches:
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

    start_marker = '{"is-c3-clipboard-data"'
    start_idx = response.find(start_marker)
    if start_idx != -1:
        depth = 0
        in_string = False
        escape_next = False
        for i, char in enumerate(response[start_idx:], start_idx):
            if escape_next:
                escape_next = False
                continue
            if char == "\\" and in_string:
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = response[start_idx:i + 1]
                        try:
                            json.loads(json_str)
                            return json_str
                        except json.JSONDecodeError:
                            break
    return None


# ============================================================
# Event Generator
# ============================================================


class EventGenerator:
    """Generate Construct 3 event sheet JSON"""

    def __init__(self, schema_dir: str = None):
        self.schema_loader = SchemaLoader(schema_dir)
        self.validator = ClipboardValidator(self.schema_loader)

    def get_relevant_schema(self, requirement: str) -> str:
        keywords = self._extract_keywords(requirement)
        relevant_schemas: Set[Tuple[str, str]] = {("system", "plugin")}
        for keyword in keywords:
            result = self.schema_loader.find_schema_by_keyword(keyword)
            if result:
                relevant_schemas.add(result)

        schema_text = []
        for schema_id, schema_type in relevant_schemas:
            if schema_type == "plugin":
                schema = self.schema_loader.load_plugin(schema_id)
                type_label = PLUGIN_KIND_LABELS["plugin"]
            else:
                schema = self.schema_loader.load_behavior(schema_id)
                type_label = PLUGIN_KIND_LABELS["behavior"]
            if schema:
                schema_text.append(self._format_schema_for_prompt(schema, type_label))

        return "\n\n".join(schema_text) if schema_text else VALIDATION_ERRORS["no_schema"]

    def _extract_keywords(self, text: str) -> List[str]:
        keywords = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", text)
        return [k for k in keywords if len(k) > 1]

    def _format_schema_for_prompt(self, schema: PluginSchema, schema_type: str) -> str:
        lines = [f"### {schema_type}: {schema.name_zh} ({schema.name_en})"]
        if schema.conditions:
            lines.append(f"\n**{ACE_SECTION_LABELS_SHORT.get('conditions', 'Conditions')} (Conditions):**")
            for cond_id, cond in list(schema.conditions.items())[:10]:
                params_str = ", ".join([f"{p.id}: {p.type}" for p in cond.params])
                lines.append(f"- `{cond_id}`: {cond.name_zh} ({params_str})")
        if schema.actions:
            lines.append(f"\n**{ACE_SECTION_LABELS_SHORT.get('actions', 'Actions')} (Actions):**")
            for act_id, act in list(schema.actions.items())[:15]:
                params_str = ", ".join([f"{p.id}: {p.type}" for p in act.params])
                lines.append(f"- `{act_id}`: {act.name_zh} ({params_str})")
        return "\n".join(lines)

    def build_prompt(self, requirement: str) -> str:
        schema_context = self.get_relevant_schema(requirement)
        return EVENT_JSON_GENERATION_PROMPT.format(
            schema_context=schema_context,
            format_reference=CLIPBOARD_FORMAT_REFERENCE,
            user_requirement=requirement,
        )

    def validate_output(self, json_str: str) -> Tuple[bool, List[str], List[str]]:
        return self.validator.validate(json_str)

    def process_response(self, llm_response: str) -> Dict[str, Any]:
        json_str = extract_json_from_response(llm_response)
        if not json_str:
            return {"success": False, "json": None, "errors": [VALIDATION_ERRORS["no_json_extracted"]], "warnings": []}
        is_valid, errors, warnings = self.validate_output(json_str)
        try:
            parsed = json.loads(json_str)
            formatted_json = json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            formatted_json = json_str
        return {"success": is_valid, "json": formatted_json, "errors": errors, "warnings": warnings}


# ============================================================
# Convenience functions
# ============================================================


def generate_event_prompt(requirement: str, schema_dir: str = None) -> str:
    generator = EventGenerator(schema_dir)
    return generator.build_prompt(requirement)


def validate_clipboard_json(json_str: str, schema_dir: str = None) -> Tuple[bool, List[str], List[str]]:
    loader = SchemaLoader(schema_dir)
    validator = ClipboardValidator(loader)
    return validator.validate(json_str)


def build_object_types(specs: List[Dict[str, Any]], schema_dir: str = None) -> Dict[str, Any]:
    loader = SchemaLoader(schema_dir)
    builder = ObjectTypeBuilder()
    return builder.build_from_spec(specs, schema_loader=loader)
