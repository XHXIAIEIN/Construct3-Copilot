"""Prompts for clipboard JSON processing pipeline."""
from src.orchestrator.validator import ValidationReport


CLIPBOARD_SYSTEM = """\
You are a Construct 3 clipboard JSON expert. You analyze, validate, modify, \
and repair C3 clipboard JSON data with deep knowledge of the format's rules \
and common pitfalls.

Key rules you enforce:
- "is-c3-clipboard-data": true is mandatory
- type must be: events | object-types | layouts | world-instances | event-sheets
- Empty parameters {} must be omitted entirely (no empty objects)
- Trigger conditions (on-*) cannot appear in children (sub-events)
- Each block can have at most one trigger condition
- Variable events require a "comment" field (can be "")
- effectTypes and instanceVariables must be arrays, not objects
- behaviorId: "Solid" → "solid", "ScrollTo" → "scrollto" (V2 lowercase)
- DestroyOutsideLayout is removed — use events to detect out-of-bounds + destroy
- SIDs must be unique integers across the entire JSON

When modifying or fixing JSON:
- Output the COMPLETE clipboard JSON (not a diff or partial snippet)
- Wrap JSON output in a ```json code block
- Briefly explain what you changed and why

When analyzing JSON:
- Explain what the events/objects do in plain language
- Point out any issues or potential improvements
- Respond in the user's language
"""


def build_clipboard_prompt(
    clipboard_json: dict,
    validation_report: ValidationReport,
    rag_context: str = "",
    user_instruction: str = "",
) -> str:
    """Build the system prompt for clipboard JSON processing.

    Assembles context from validation results, RAG knowledge, the user's
    clipboard JSON, and their natural language instruction.
    """
    import json

    parts = [CLIPBOARD_SYSTEM]

    # Validation results
    if validation_report.issues:
        issues_text = "\n".join(
            f"- [{i.level.upper()}] {i.code}: {i.message} (at {i.path})"
            if i.path else f"- [{i.level.upper()}] {i.code}: {i.message}"
            for i in validation_report.issues
        )
        parts.append(
            f"\n## Validation Results\n\n"
            f"The following issues were found in the user's JSON:\n\n{issues_text}"
        )
    else:
        parts.append("\n## Validation Results\n\nNo issues found in the user's JSON.")

    # RAG context
    if rag_context:
        parts.append(
            f"\n## Reference Knowledge (from RAG)\n\n"
            f"Relevant Construct 3 documentation:\n\n{rag_context}"
        )

    # The clipboard JSON itself
    json_str = json.dumps(clipboard_json, ensure_ascii=False, indent=2)
    parts.append(f"\n## User's Clipboard JSON\n\n```json\n{json_str}\n```")

    # User instruction
    if user_instruction:
        parts.append(f"\n## User's Request\n\n{user_instruction}")
    else:
        parts.append(
            "\n## User's Request\n\n"
            "The user pasted this JSON without additional instructions. "
            "Validate it and report any issues found. If issues exist, "
            "suggest fixes. If the JSON looks good, briefly describe what it does."
        )

    return "\n".join(parts)
