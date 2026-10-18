"""What happens to a reply's text after the model wrote it: the length rewrite, the banned phrases, the
promise of a file, and the patterns that tell a build request from a question."""
from __future__ import annotations

import html
import re
from typing import Callable

# characters of a reply by what it needs, in steps; a longer one is sent back to be shortened (2026-10-18: most
# replies in 35 characters, more only when the reply needs it, never past 350)
REPLY_MAX = 35  # an answer without steps
STEPS_MAX = 150  # an answer of numbered steps the person must do
EVENTS_MAX = 350  # an answer that writes events the person asked for; the ceiling of every reply
SENT_MAX = 100  # characters; the reply that goes out with a project file
# a step number: "1." or "2、" not inside a number such as 0.2 or r506.2
STEP = re.compile(r"(?<![\d.])([1-9])[.、．](?!\d)")
# a step that follows the end of a sentence or a colon on the same line: it starts a line of its own
INLINE_STEP = re.compile(r"(?<=[。！？；：!?;:])[ \t]*(?=[1-9][.、．](?!\d))")
ASKED_EVENTS = re.compile(r"事件|怎么写|写一下|写出来|写法|具体|步骤|example|event")
SHORTEN = (
    "Rewrite your last answer in under {n} characters for the user. Keep the conclusion, the deciding reason and "
    "the steps the user must do, in everyday words. Keep the approach, not its details. Cut walkthroughs of what the code or events already do, second "
    "options, side notes, and code names, values and line numbers the person does not have to type. Keep every "
    "condition and action name the answer uses (e.g. 设置对象速率), copied exactly, since the person finds them "
    "in the editor by that name. Same language, plain text with each numbered step on its own line, no mention "
    "of this request."
)
SHORTEN_EVENTS = (" Keep every event line (conditions, then → actions) exactly as written; shorten the words "
                  "around them.")
SHORTEN_SENT = (
    "The project file is sent with this reply. Rewrite your last answer in under {n} characters: what the "
    "example shows and what to tap or press to see it, in one or two sentences. No explanation of the "
    "mechanism, the layout, event numbers or object names. Same language, plain text, no mention of this request."
)

# a request for an example or a project file, in the words people use; the note sent with it routes the model to the
# project tools, since the prompt's own list of such requests steered it only sometimes (2026-10-06)
BUILD_ASK = re.compile(r"(?:做|制作|生成|重做|写)[^。！？\n]{0,40}(例子|示例|样例|demo|工程|项目|游戏|小游戏|原型)"
                       r"|(给我|发我|发给我|给我发|给个|来个|来一个|要个|要一个|弄个|搞个|写个)[^。，\n]{0,12}"
                       r"(例子|示例|样例|demo|工程|项目|游戏|小游戏|原型)"
                       r"|^\s*整个(例子|示例|样例|demo|工程|项目|游戏|小游戏|原型)\s*(吧|呗)?[。！!]*\s*$"
                       r"|example project|make (me )?(a|an) (example|demo|project)", re.I)
# a bare "c3p" or "工程文件" means the held project when one is held, a new one when none is
BUILD_ASK_BARE = re.compile(r"c3p|工程文件|项目文件", re.I)
# the length rule again at the question, the last thing the model reads before its tools: in the system prompt
# alone it left drafts of 200 to 500 characters, each rewritten by one more call (2026-10-18)
LENGTH_NOTE = (f"\n(Answer in at most {REPLY_MAX} characters; numbered steps the person must do may take "
               f"{STEPS_MAX}, events they asked you to write {EVENTS_MAX}.)")
BUILD_NOTE = ("\n(The person asks for an example or a project file: make it with the project tools (design_guide, "
              "check_design, new_project_from_spec) and it is sent after your reply. Words alone do not answer it.)")
# a how-to question that an example shows better than steps in words (plugin.presearch decides): the example is
# made the way a requested one is, and the reply only says what to look at in it
SHOW_NOTE = ("\n(Answer with a small example that shows this: make it with the project tools (design_guide, "
             "check_design, new_project_from_spec) and it is sent after your reply. In the reply, name the way in "
             f"one sentence and what to look at in the example, in at most {SENT_MAX} characters.)")
PROMISE = re.compile(r"(文件|c3p|工程|项目|例子)[^。！\n]*((发|传)(给|到)?你|发送|发来|发出|稍后|随后)"
                     r"|(发|传)(给|到)?你[^。！\n]*(文件|c3p|工程|例子)")

# phrases the prompt bans; a reply that still holds one loses that sentence before it is sent (2026-10-06)
BANNED = re.compile(r"希望(对你)?有(所)?帮助|很高兴|好问题|简单来说|本质上|值得注意的是|祝你|"
                    r"欢迎(再|继续|随时)|有(其他|别的|什么|任何)问题(可以|随时|再|欢迎)")
# a closing offer or question: dropped while it ends the reply and another sentence remains
OFFER = re.compile(r"需要|要不要|想不想|如果(你)?(需要|想|有)|还(需要|想要|有什么)|可以(帮你|给你|为你)|我可以|"
                   r"告诉我|说一声|说一句")


def has_steps(text: str) -> bool:
    """Whether text holds numbered steps: a "1." and a "2.", on their own lines or in one line as QQ shows them."""
    return {"1", "2"} <= set(STEP.findall(text))


def step_lines(text: str) -> str:
    """The reply with each numbered step on its own line (2026-10-19: four steps of a mesh answer came in one
    line, after the prompt's own example wrote them so)."""
    return INLINE_STEP.sub("\n", text) if has_steps(text) else text


def is_build_ask(question: str, project_held: bool) -> bool:
    """Whether the question asks for an example or a project file."""
    return bool(BUILD_ASK.search(question) or (not project_held and BUILD_ASK_BARE.search(question)))


def drop_promise(text: str) -> tuple[str, bool]:
    """The reply without the sentences that promise a file, and whether one was dropped."""
    parts = re.split(r"(?<=[。！\n])", text)
    kept = [s for s in parts if not PROMISE.search(s)]
    if len(kept) < len(parts):
        return "".join(kept).strip(), True
    return text, False


def scrub(text: str) -> tuple[str, str]:
    """Return the reply without banned phrases and closing offers, and a note of what was dropped."""
    parts = [p for p in re.split(r"(?<=[。！？!?\n])", text) if p]
    # a phrase that opens a sentence ("简单来说，加计时器") goes alone; a sentence built on one goes whole
    cut = [re.sub(r"^\s*(?:" + BANNED.pattern + r")\s*[，,、：:]\s*", "", p) for p in parts]
    kept = [p for p in cut if not BANNED.search(p) and re.search(r"[\w一-鿿]", p)]
    while len(kept) > 1 and OFFER.search(kept[-1]) and not re.search(r"c3p|\.zip|文件|项目|工程", kept[-1]):
        kept.pop()
    while kept and not kept[-1].strip():
        kept.pop()
    out = "".join(kept).strip()
    return (out if out else text), ("scrubbed" if out and out != text.strip() else "")


def shorten(complete: Callable[[list[dict]], str], messages: list[dict], text: str, trace: list[str],
            asked: bool = False, sent: bool = False) -> str:
    """The reply under its length limit, rewritten by the model when it is over. complete(messages) is one
    model call that returns the content; messages is the conversation the reply closes."""
    def rewrite(before: str, ask: str) -> str:
        return html.unescape(complete([*messages, {"role": "assistant", "content": before},
                                       {"role": "user", "content": ask}]).strip())

    # A reply sent with a project only says what to try in it; the person reads the events in the file
    # (2026-10-09: a 330-character delivery explained the mechanism, the layout and the event numbers).
    if sent:
        if len(text) <= SENT_MAX:
            return text
        short = rewrite(text, SHORTEN_SENT.format(n=SENT_MAX))
        trace.append(f"shortened {len(text)} -> {len(short)} (sent)")
        return short if short and len(short) < len(text) else text
    # Events are what the person copies: an answer that writes them may be longer, and a shortening keeps them
    # (2026-10-06: a 1414-character answer of events came back as 271 characters of prose without one).
    # three or more event lines; one arrow in prose does not make an answer of events (2026-10-06)
    # and only when the person asked for events or sent a project; a how-to question gets the approach
    events = asked and sum("→" in line for line in text.splitlines()) >= 3
    limit = EVENTS_MAX if events else STEPS_MAX if has_steps(text) else REPLY_MAX
    if len(text) <= limit:
        return text
    short = rewrite(text, SHORTEN.format(n=limit) + (SHORTEN_EVENTS if events else ""))
    if short and len(short) > limit:  # a first rewrite often stops short of the limit (1017 -> 889 at 350)
        again = rewrite(short, f"Still {len(short)} characters. " + SHORTEN.format(n=limit)
                        + " Drop every detail that is not the approach or a step the person must do.")
        if again and len(again) < len(short):
            short = again
    trace.append(f"shortened {len(text)} -> {len(short)}")
    return short if short and len(short) < len(text) else text
