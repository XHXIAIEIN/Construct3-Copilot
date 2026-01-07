#!/usr/bin/env python3
"""
Build project analysis index from Construct 3 example projects.

Extracts ACE usage patterns from 490+ official example projects to create
a knowledge base for RAG-style retrieval.

Usage:
    python scripts/build_project_analysis.py /path/to/Construct-Example-Projects

Output:
    data/project_analysis/
    ├── actions_knowledge.json      # Action usage stats + examples
    ├── conditions_knowledge.json   # Condition usage stats + examples
    ├── behaviors_knowledge.json    # Behavior patterns
    ├── plugins_knowledge.json      # Plugin patterns
    └── index.json                  # Summary statistics
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

def find_event_sheets(root: Path) -> List[Path]:
    """Find all eventSheets/*.json files."""
    return list(root.rglob("eventSheets/*.json"))

def extract_aces_from_event(event: dict, aces: dict):
    """Recursively extract ACEs from an event block."""
    # Extract conditions
    for cond in event.get("conditions", []):
        ace_id = cond.get("id", "")
        obj_class = cond.get("objectClass", "")
        params = cond.get("parameters", {})
        behavior = cond.get("behaviorType", "")

        if ace_id:
            key = f"{obj_class}:{ace_id}" if obj_class else ace_id
            if key not in aces["conditions"]:
                aces["conditions"][key] = {
                    "id": ace_id,
                    "objectClass": obj_class,
                    "behaviorType": behavior,
                    "usage_count": 0,
                    "param_examples": []
                }
            aces["conditions"][key]["usage_count"] += 1
            if params and len(aces["conditions"][key]["param_examples"]) < 3:
                aces["conditions"][key]["param_examples"].append(params)

    # Extract actions
    for action in event.get("actions", []):
        ace_id = action.get("id", "")
        obj_class = action.get("objectClass", "")
        params = action.get("parameters", {})
        behavior = action.get("behaviorType", "")

        if ace_id:
            key = f"{obj_class}:{ace_id}" if obj_class else ace_id
            if key not in aces["actions"]:
                aces["actions"][key] = {
                    "id": ace_id,
                    "objectClass": obj_class,
                    "behaviorType": behavior,
                    "usage_count": 0,
                    "param_examples": []
                }
            aces["actions"][key]["usage_count"] += 1
            if params and len(aces["actions"][key]["param_examples"]) < 3:
                aces["actions"][key]["param_examples"].append(params)

    # Recurse into children
    for child in event.get("children", []):
        extract_aces_from_event(child, aces)

def process_event_sheet(path: Path, aces: dict, project_name: str):
    """Process a single event sheet file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for event in data.get("events", []):
            extract_aces_from_event(event, aces)

    except (json.JSONDecodeError, KeyError) as e:
        print(f"  ⚠️ Error processing {path}: {e}")

def build_behavior_stats(aces: dict) -> dict:
    """Group ACEs by behavior type."""
    behaviors = defaultdict(lambda: {"conditions": [], "actions": [], "usage_count": 0})

    for key, data in aces["conditions"].items():
        if data.get("behaviorType"):
            bt = data["behaviorType"]
            behaviors[bt]["conditions"].append(data["id"])
            behaviors[bt]["usage_count"] += data["usage_count"]

    for key, data in aces["actions"].items():
        if data.get("behaviorType"):
            bt = data["behaviorType"]
            behaviors[bt]["actions"].append(data["id"])
            behaviors[bt]["usage_count"] += data["usage_count"]

    return dict(behaviors)

def build_plugin_stats(aces: dict) -> dict:
    """Group ACEs by plugin/objectClass."""
    plugins = defaultdict(lambda: {"conditions": [], "actions": [], "usage_count": 0})

    for key, data in aces["conditions"].items():
        if data.get("objectClass") and not data.get("behaviorType"):
            oc = data["objectClass"]
            plugins[oc]["conditions"].append(data["id"])
            plugins[oc]["usage_count"] += data["usage_count"]

    for key, data in aces["actions"].items():
        if data.get("objectClass") and not data.get("behaviorType"):
            oc = data["objectClass"]
            plugins[oc]["actions"].append(data["id"])
            plugins[oc]["usage_count"] += data["usage_count"]

    return dict(plugins)

def main():
    if len(sys.argv) < 2:
        print("Usage: python build_project_analysis.py /path/to/Construct-Example-Projects")
        sys.exit(1)

    example_root = Path(sys.argv[1])
    if not example_root.exists():
        print(f"❌ Path not found: {example_root}")
        sys.exit(1)

    # Find example-projects subdirectory
    projects_dir = example_root / "example-projects"
    if not projects_dir.exists():
        projects_dir = example_root

    output_dir = Path(__file__).parent.parent / "data" / "project_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Scanning: {projects_dir}")

    # Find all event sheets
    event_sheets = find_event_sheets(projects_dir)
    print(f"📄 Found {len(event_sheets)} event sheets")

    # Extract ACEs
    aces = {
        "conditions": {},
        "actions": {}
    }

    project_count = 0
    processed_projects = set()

    for i, es_path in enumerate(event_sheets):
        project_name = es_path.parent.parent.name
        if project_name not in processed_projects:
            processed_projects.add(project_name)
            project_count += 1

        process_event_sheet(es_path, aces, project_name)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(event_sheets)} files...")

    print(f"\n✅ Processed {project_count} projects")

    # Sort by usage count
    actions_sorted = dict(sorted(
        aces["actions"].items(),
        key=lambda x: x[1]["usage_count"],
        reverse=True
    ))

    conditions_sorted = dict(sorted(
        aces["conditions"].items(),
        key=lambda x: x[1]["usage_count"],
        reverse=True
    ))

    # Build grouped stats
    behaviors = build_behavior_stats(aces)
    plugins = build_plugin_stats(aces)

    # Write output files
    with open(output_dir / "actions_knowledge.json", 'w', encoding='utf-8') as f:
        json.dump(actions_sorted, f, indent=2, ensure_ascii=False)

    with open(output_dir / "conditions_knowledge.json", 'w', encoding='utf-8') as f:
        json.dump(conditions_sorted, f, indent=2, ensure_ascii=False)

    with open(output_dir / "behaviors_knowledge.json", 'w', encoding='utf-8') as f:
        json.dump(behaviors, f, indent=2, ensure_ascii=False)

    with open(output_dir / "plugins_knowledge.json", 'w', encoding='utf-8') as f:
        json.dump(plugins, f, indent=2, ensure_ascii=False)

    # Write index
    index = {
        "source": str(projects_dir),
        "project_count": project_count,
        "event_sheet_count": len(event_sheets),
        "unique_actions": len(actions_sorted),
        "unique_conditions": len(conditions_sorted),
        "total_action_usage": sum(a["usage_count"] for a in actions_sorted.values()),
        "total_condition_usage": sum(c["usage_count"] for c in conditions_sorted.values()),
        "top_10_actions": list(actions_sorted.keys())[:10],
        "top_10_conditions": list(conditions_sorted.keys())[:10]
    }

    with open(output_dir / "index.json", 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n📊 Statistics:")
    print(f"   Unique actions: {len(actions_sorted)}")
    print(f"   Unique conditions: {len(conditions_sorted)}")
    print(f"   Total action usage: {index['total_action_usage']}")
    print(f"   Total condition usage: {index['total_condition_usage']}")
    print(f"\n📁 Output: {output_dir}")
    print(f"\n🔝 Top 10 Actions:")
    for key in list(actions_sorted.keys())[:10]:
        print(f"   {key}: {actions_sorted[key]['usage_count']} uses")

if __name__ == "__main__":
    main()
