"""Messages that only say got it after the bot's reply, which the channel drops without a model call (channels/core/ack.py)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from channels.core import ack, answers, chat

PLAIN = "会。改成 lerp(a,b,1-0.01^dt) 就不受影响。"  # a reply of 2026-10-19 that asks and offers nothing
# 2026-10-16 22:43: after this reply "1" meant "do it" and the bot built the game again
INVITE = "没做出来。玩法说简单点，再让我做一次。"
CHOICE = "有两种做法：1. 用网格变形把上边两点往里收。2. 用 3D 平面加透视。"


class AcknowledgesTests(unittest.TestCase):
    def test_got_it_after_a_plain_reply(self):
        for message in ("哦哦哦", "哦哦", "嗯嗯", "ojbk", "喔了", "o了", "ooo", "谢谢", "1", "111", "好的谢谢大佬",
                        "👍", "OK！", "ＯＫ", "收到~", "懂了懂了", "明白了，我试试", "感谢感谢🙏🏻", "666", "❤️"):
            with self.subTest(message=message):
                self.assertTrue(ack.acknowledges(message, PLAIN))

    def test_anything_more_is_answered(self):
        for message in ("哦？", "嗯?", "不懂", "还是不行", "好的，那怎么加音效", "在吗", "", "  ", "啊", "了", "真的",
                        "我去", "你好", "您好", "对吧", "是嘛", "那这样呢", "2", "😭"):
            with self.subTest(message=message):
                self.assertFalse(ack.acknowledges(message, PLAIN))

    def test_a_question_or_offer_is_answered_whatever_comes_back(self):
        for reply in (INVITE, "你要横版还是竖版？", "需要我把音效也加上吗"):
            for message in ("1", "好", "嗯嗯", "可以", "谢谢", "哦哦"):
                with self.subTest(reply=reply, message=message):
                    self.assertFalse(ack.acknowledges(message, reply))

    def test_after_a_choice_one_picks_and_the_rest_still_says_got_it(self):
        self.assertFalse(ack.acknowledges("1", CHOICE))
        self.assertFalse(ack.acknowledges("1了", CHOICE))
        for message in ("哦哦", "谢谢", "明白了"):
            with self.subTest(message=message):
                self.assertTrue(ack.acknowledges(message, CHOICE))

    def test_the_first_message_of_a_chat(self):
        self.assertTrue(ack.acknowledges("谢谢", ""))
        self.assertFalse(ack.acknowledges("做个贪吃蛇", ""))

    def test_every_word_of_the_config_means_what_its_list_says(self):
        rules = ack.load()
        self.assertTrue(rules["pick"] <= rules["acknowledge"])
        self.assertFalse(rules["acknowledge"] & rules["filler"])
        for word in rules["acknowledge"]:
            with self.subTest(acknowledge=word):
                self.assertTrue(ack.acknowledges(word, PLAIN, rules))
        for word in rules["filler"]:
            with self.subTest(filler=word):
                self.assertFalse(ack.acknowledges(word, PLAIN, rules))

    def test_an_unreadable_config_answers_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "ack.json"
            broken.write_text("{", encoding="utf-8")
            with patch.object(ack, "RULES", broken), self.assertLogs("channels.core.ack", "WARNING"):
                self.assertFalse(ack.acknowledges("哦哦", PLAIN))

    def test_an_edit_counts_from_the_next_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules = Path(tmp) / "ack.json"
            words = json.loads(ack.RULES.read_text(encoding="utf-8"))
            with patch.object(ack, "RULES", rules):
                rules.write_text(json.dumps(words), encoding="utf-8")
                self.assertFalse(ack.acknowledges("嗯呐", PLAIN))
                words["acknowledge"].append("嗯呐")
                rules.write_text(json.dumps(words), encoding="utf-8")
                self.assertTrue(ack.acknowledges("嗯呐", PLAIN))


class ChatAcknowledgedTests(unittest.IsolatedAsyncioTestCase):
    async def answered(self, chats, key, question, notify=None):
        """Ask and record the reply as sent whole, which puts it in the history."""
        turn = await chats.ask(key, question, group=False, attachments=[], notify=notify)
        chats.record(turn, chat="private", session=key, files_in=[], sent=set(), parts=[turn.text], parts_sent=1)

    async def test_got_it_is_not_counted_and_reads_the_chat_last_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            application = Mock()
            application.handle.return_value = {"text": PLAIN}
            chats = chat.Chats(application, data_dir=Path(tmp), channel="qq", daily_limit=1)
            await self.answered(chats, "c2c:a", "lerp 每帧用会受帧率影响吗？")
            with self.assertLogs("channels.core.chat", "INFO") as logged:
                self.assertTrue(chats.acknowledged("c2c:a", "哦哦", chat="private"))
            self.assertIn("c2c:a ack: 哦哦", logged.output[-1])
            self.assertFalse(chats.acknowledged("c2c:a", "哦哦", chat="private", attachments=[object()]))
            self.assertEqual(len(chats.recent("c2c:a")), 2)
            self.assertIsNone(chats.admit("c2c:a", "那 dt 是什么"))  # the day's one question is still there

            application.handle.return_value = {"text": INVITE}
            await self.answered(chats, "c2c:b", "做个贪吃蛇")
            self.assertFalse(chats.acknowledged("c2c:b", "1", chat="private"))
            self.assertTrue(chats.acknowledged("c2c:a", "1", chat="private"))  # another chat's reply does not count
            self.assertTrue(chats.acknowledged("group:G:M", "谢谢", chat="group"))  # a chat with no reply yet

            # each message given no answer is in skipped.jsonl with the sentence the rule read, and only those
            skipped = answers.read_skipped(Path(tmp), "qq")
            self.assertEqual([(s["chat"], s["session"], s["skipped"], s["message"], s["after"]) for s in skipped],
                             [("private", "c2c:a", "ack", "哦哦", "改成 lerp(a,b,1-0.01^dt) 就不受影响。"),
                              ("private", "c2c:a", "ack", "1", "改成 lerp(a,b,1-0.01^dt) 就不受影响。"),
                              ("group", "group:G:M", "ack", "谢谢", "")])
            self.assertRegex(skipped[0]["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*Z$")
            self.assertFalse({"arrived", "waited"} & set(skipped[0]))  # no arrival taken, no wait measured

    async def test_a_message_is_judged_against_the_bot_message_it_came_after(self):
        """While the chat's answer is being made and sent, a message follows that answer's busy note, and nothing
        before the note: the question being answered already answered the reply before it. Once record has put the
        reply in the history, a message follows the reply."""
        note = "在做了，要两三分钟，做好发你。"
        with tempfile.TemporaryDirectory() as tmp:
            arrivals = {}

            def handle(request):
                if request["text"] == "跳跃怎么做":
                    return {"text": "用 Platform 行为。要我做一个示例吗？"}
                arrivals["before the note"] = chats.arrive("c2c:a")
                request["notify"](note)
                arrivals["after the note"] = chats.arrive("c2c:a")
                return {"text": INVITE}

            application = Mock()
            application.handle.side_effect = handle
            chats = chat.Chats(application, data_dir=Path(tmp), channel="qq")
            await self.answered(chats, "c2c:a", "跳跃怎么做")
            notes = []
            turn = await chats.ask("c2c:a", "要，做个贪吃蛇", group=False, attachments=[], notify=notes.append)
            self.assertEqual(notes, [note])
            # the reply is being sent and not in the history yet, so a message now still follows the note
            self.assertEqual(chats.arrive("c2c:a").seen, note)
            chats.record(turn, chat="private", session="c2c:a", files_in=[], sent=set(), parts=[turn.text],
                         parts_sent=1)
            self.assertEqual({name: a.seen for name, a in arrivals.items()},
                             {"before the note": "", "after the note": note})
            for arrival in arrivals.values():
                self.assertTrue(chats.acknowledged("c2c:a", "好的", chat="private", arrival=arrival))
            self.assertFalse(chats.acknowledged("c2c:a", "好的", chat="private", arrival=chats.arrive("c2c:a")))
            self.assertFalse(chats.acknowledged("c2c:a", "好的", chat="private"))
            self.assertEqual([(s["after"], s["waited"]) for s in answers.read_skipped(Path(tmp), "qq")],
                             [("", 0), (note, 0)])


if __name__ == "__main__":
    unittest.main()
