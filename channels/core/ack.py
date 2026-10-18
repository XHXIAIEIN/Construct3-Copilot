"""Whether a message only says got it, understood or thanks after the bot's reply ("哦哦", "o了", "谢谢"), so it needs
no answer and no model call. The words and the signals are in ack.json beside this file, read on every call, so an
edit there counts from the next message on."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path

log = logging.getLogger("channels.core.ack")

RULES = Path(__file__).with_name("ack.json")
SENTENCE = re.compile(r"(?<=[。！!？?\n])")


def plain(text: str) -> str:
    """text as the words are matched: full-width as half-width, lower case, without spaces, punctuation, symbols
    such as "~" and the marks that change an emoji's look. "?" stays, so "哦？" is no got it."""
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(c for c in text
                   if c == "?" or not unicodedata.category(c).startswith(("P", "Z", "C", "M", "Sm", "Sk")))


LISTS = ("acknowledge", "filler", "invite", "choice", "pick")


def load(path: Path | None = None) -> dict[str, set[str]] | None:
    """The word lists of ack.json, each word as plain() leaves it; None when the file cannot be read."""
    path = path or RULES
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
        return {name: {plain(word) for word in rules[name]} - {""} for name in LISTS}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("%s unreadable, every message is answered: %s", path, exc)
        return None


def cuts_into(text: str, words: set[str], needed: set[str]) -> bool:
    """Whether text is a run of words with at least one of them from needed."""
    # reach[i]: None while text[:i] is no run of words, else whether one of them was needed
    reach: list[bool | None] = [None] * (len(text) + 1)
    reach[0] = False
    for i in range(len(text)):
        if reach[i] is None:
            continue
        for word in words:
            if text.startswith(word, i):
                reach[i + len(word)] = bool(reach[i + len(word)]) or reach[i] or word in needed
    return reach[-1] is True


def last_sentence(reply: str) -> str:
    parts = [p for p in SENTENCE.split(reply.strip()) if p.strip()]
    return parts[-1] if parts else ""


def acknowledges(message: str, last_reply: str = "", rules: dict[str, set[str]] | None = None) -> bool:
    """Whether message only says got it after last_reply, the bot's reply before it: the whole message is a run of
    acknowledge and filler words with at least one acknowledge word, and the reply's last sentence holds no invite
    (a question or an offer, which a "好" or a "1" answers). When the reply lays out a choice anywhere, the pick
    words choose and are no acknowledgement: "1" after two ways is the first way."""
    rules = rules or load()
    if not rules:
        return False
    if any(signal in plain(last_sentence(last_reply)) for signal in rules["invite"]):
        return False
    known = rules["acknowledge"]
    if any(signal in plain(last_reply) for signal in rules["choice"]):
        known = known - rules["pick"]
    return cuts_into(plain(message), known | rules["filler"], known)
