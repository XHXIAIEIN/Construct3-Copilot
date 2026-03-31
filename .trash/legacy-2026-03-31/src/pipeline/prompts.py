"""
LLM prompt templates for Copilot pipeline.

All prompts are in English. User-facing localization is handled
separately in src/locale/.
"""

# =============================================================================
# System Message
# =============================================================================

SYSTEM_MESSAGE = """\
You are a Construct 3 game engine expert assistant.

Capabilities:
- Answer questions about Construct 3 features, plugins, behaviors, and workflows
- Explain Actions, Conditions, and Expressions (ACE) with parameters
- Generate event sheet clipboard JSON for pasting into the editor
- Provide scripting API guidance (JavaScript/TypeScript)

Rules:
- Base answers ONLY on provided reference materials
- Cite sources using [Source: N] format matching context block numbers
- If references don't cover the question, state clearly what is unknown
- Use precise Construct 3 terminology
- Answer in the user's language\
"""

# =============================================================================
# Q&A Prompts
# =============================================================================

QA_PROMPT = """\
Reference materials:
{context}

Question: {question}

Answer the question based on the reference materials above.
Cite sources using [Source: N] format.\
"""

STRICT_QA_PROMPT = """\
Reference materials:
{context}

Question: {question}

Iron rules:
1. Answer ONLY based on the reference materials above
2. Every factual claim MUST cite [Source: N]
3. If the references are insufficient, say "Based on available documentation, \
I cannot fully answer this question" and explain what IS covered
4. Never invent features, parameters, or behaviors not in the references
5. Use exact names from the documentation (plugin names, ACE names, parameters)

Provide a clear, structured answer with citations.\
"""

LOW_RELEVANCE_PROMPT = """\
The search returned only {result_count} results with limited relevance:
{context}

Question: {question}

Given the limited references, answer conservatively:
- Only state what the references directly support
- Clearly indicate when information is incomplete
- Suggest where the user might find more details\
"""

# =============================================================================
# Fallback Responses
# =============================================================================

NO_RESULTS_RESPONSE = """\
No relevant documentation found for this query.

Suggestions:
- Try rephrasing with specific Construct 3 terms (plugin names, behavior names)
- Check the official manual: https://www.construct.net/en/make-games/manuals/construct-3\
"""

LLM_UNAVAILABLE_RESPONSE = """\
LLM service is currently unavailable. Retrieved references:

{sources_summary}

Please try again later, or consult the sources above directly.\
"""

RAG_UNAVAILABLE_RESPONSE = """\
RAG retrieval service is currently unavailable.

Please ensure the RAG server is running:
  python scripts/serve.py  (in the Construct3-RAG project)\
"""

LOW_CONFIDENCE_WARNING = """\
Note: The following answer has limited source support. \
Please verify against official documentation.\
"""

# =============================================================================
# Query Processing
# =============================================================================

ROUTER_PROMPT = """\
Classify this Construct 3 query into one category.
Output ONLY one word: qa / code / other

Query: {query}\
"""

QUERY_REWRITE_PROMPT = """\
Rewrite this Construct 3 query into 3 alternative search queries.
Include: one in Chinese, one in English, one mixing both.
Output one query per line, no numbering.

Original: {query}\
"""

QUERY_DECOMPOSITION_PROMPT = """\
Break this complex Construct 3 question into 2-4 simpler sub-questions.
Each sub-question should be independently searchable.
Output one sub-question per line, no numbering.

Question: {query}\
"""

# =============================================================================
# Self-Reflection
# =============================================================================

SELF_REFLECTION_PROMPT = """\
Verify this answer against the provided reference materials.

References:
{context}

Question: {question}

Answer to verify:
{answer}

Check:
1. Is every claim supported by the references?
2. Are citations [Source: N] accurate?
3. Are there any fabricated features or parameters?

Output your assessment, ending with:
Reliability: [Reliable / Unreliable]\
"""

REFLECTION_VERDICT_KEY = "Reliability"
REFLECTION_UNRELIABLE = "Unreliable"
REFLECTION_RELIABLE = "Reliable"

# =============================================================================
# Event Sheet / Clipboard Generation
# =============================================================================

EVENT_GENERATION_PROMPT = """\
Generate Construct 3 event sheet JSON based on:

Similar examples:
{similar_examples}

User requirement:
{user_requirement}

Output valid clipboard JSON that can be pasted into Construct 3.\
"""

CLIPBOARD_FORMAT_REFERENCE = """\
Construct 3 clipboard JSON format reference:

Event structure:
{{"c3": true, "type": "events", "items": [...]}}

Each event has conditions and actions arrays.
Condition: {{"type": "<plugin>", "id": "<ace-id>", "params": {{...}}}}
Action: {{"type": "<plugin>", "id": "<ace-id>", "params": {{...}}}}\
"""

EVENT_JSON_GENERATION_PROMPT = """\
Generate clipboard-ready JSON for Construct 3.

Schema context:
{schema_context}

Format reference:
{format_reference}

User requirement:
{user_requirement}

Output ONLY valid JSON, no explanation.\
"""

# =============================================================================
# JavaScript Hints
# =============================================================================

JS_HINT_FOOTER = """\

Note: This can also be implemented via JavaScript/TypeScript scripting.
See the Scripting section in the Construct 3 manual for details.\
"""

JS_INCLUDE_INSTRUCTION = """\
If the task involves logic that would benefit from scripting,
also provide a JavaScript code snippet as a supplement.\
"""

# =============================================================================
# Context Formatting
# =============================================================================

CONTEXT_HEADER = "Reference materials"
CONTEXT_HEADER_STRICT = "Verified reference materials"
SOURCE_LABEL = "Source"

CLIPBOARD_CONTEXT_HEADER = """\
The following clipboard JSON format information is from the Construct 3 editor.
Use these conventions when generating event sheet JSON.\
"""

CLIPBOARD_DEFAULT_QUERY = """\
Analyze the provided clipboard content and explain its structure.\
"""

# =============================================================================
# Semantic Query Analysis
# =============================================================================

SEMANTIC_DECOMPOSE_PROMPT = """\
Analyze this Construct 3 query and output JSON:

Query: {query}

Output format:
{{
  "query_type": "concept|howto|api|comparison|troubleshoot",
  "c3_objects": ["plugin/behavior names mentioned"],
  "intents": {{
    "collection_name": weight_0_to_1
  }},
  "sub_queries": ["decomposed sub-questions if complex"],
  "confidence": 0.0_to_1.0
}}\
"""
