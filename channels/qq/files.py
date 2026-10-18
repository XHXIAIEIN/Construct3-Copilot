"""Send a local file to a QQ user or group: the open platform's chunked upload, then a msg_type 7 message.

botpy 1.2 uploads only by public URL; this PC has none, so the file goes up in parts:
upload_prepare -> PUT each part to its presigned URL -> upload_part_finish per part -> files with upload_id,
which returns file_info for the message. The upload sends no message, so a passive reply is still free.

    python -m channels.qq.files FILE --user OPENID      send FILE as an active C2C message (needs QQ_APPID, QQ_SECRET)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Awaitable, Callable

import aiohttp

log = logging.getLogger("channels.qq.files")

API = "https://api.sgroup.qq.com"
FILE = 4  # file_type: a file card the receiver downloads
MD5_10M = 10002432  # bytes hashed for md5_10m
TIMEOUT = aiohttp.ClientTimeout(total=60)

Auth = Callable[[], Awaitable[str]]  # returns the Authorization header value, "QQBot <token>"


class UploadError(RuntimeError):
    pass


def _base(scope: str, target: str) -> str:
    """scope 'c2c' or 'group'; target the user openid or the group openid."""
    return f"{API}/v2/{'users' if scope == 'c2c' else 'groups'}/{target}"


async def _post(session: aiohttp.ClientSession, auth: Auth, url: str, body: dict) -> dict:
    headers = {"Authorization": await auth()}
    async with session.post(url, json=body, headers=headers) as resp:
        data = await resp.json(content_type=None) if resp.content_length != 0 else {}
        if resp.status >= 400 or (isinstance(data, dict) and data.get("code") not in (None, 0)):
            raise UploadError(f"{url.rsplit('/', 1)[-1]}: HTTP {resp.status} {data}")
        return data or {}


PART_RETRY = 40093001  # upload_part_finish: the part is not stored yet; asking again a moment later succeeds
PART_RETRY_SECONDS = 60


async def _part_finish(session: aiohttp.ClientSession, auth: Auth, url: str, body: dict) -> None:
    loop = asyncio.get_running_loop()
    start = loop.time()
    while True:
        try:
            await _post(session, auth, url, body)
            return
        except UploadError as exc:
            if str(PART_RETRY) not in str(exc) or loop.time() - start > PART_RETRY_SECONDS:
                raise
            await asyncio.sleep(2)


async def upload(auth: Auth, scope: str, target: str, path: Path, name: str | None = None) -> str:
    """Upload path in parts and return its file_info."""
    data = path.read_bytes()
    name = name or path.name
    base = _base(scope, target)
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        prep = await _post(session, auth, f"{base}/upload_prepare", {
            "file_type": FILE,
            "file_size": str(len(data)),
            "file_name": name,
            "md5": hashlib.md5(data).hexdigest(),
            "sha1": hashlib.sha1(data).hexdigest(),
            "md5_10m": hashlib.md5(data[:MD5_10M]).hexdigest(),
        })
        upload_id, block = prep["upload_id"], int(prep["block_size"])
        # the server numbers parts from 1 although its docs say 0, so the offset comes from the part's position
        parts = sorted(prep.get("parts") or [], key=lambda p: int(p.get("index") or 0))
        log.info("upload prepared: %s bytes, block %s, part indices %s", len(data), block, [p.get("index") for p in parts])
        for position, part in enumerate(parts):
            chunk = data[position * block : (position + 1) * block]
            async with session.put(part["presigned_url"], data=chunk) as resp:
                if resp.status >= 400:
                    raise UploadError(f"PUT part {part.get('index')}: HTTP {resp.status} {(await resp.text())[:200]}")
            await _part_finish(session, auth, f"{base}/upload_part_finish", {
                "upload_id": upload_id,
                "part_index": part.get("index"),
                "block_size": str(len(chunk)),
                "md5": hashlib.md5(chunk).hexdigest(),
            })
        done = await _post(session, auth, f"{base}/files", {
            "file_type": FILE, "srv_send_msg": False, "file_name": name, "upload_id": upload_id,
        })
    log.info("uploaded %s bytes as %s parts, ttl %s", len(data), len(prep.get("parts") or []), done.get("ttl"))
    return done["file_info"]


async def send_file(auth: Auth, scope: str, target: str, path: Path, name: str | None = None,
                    msg_id: str | None = None, msg_seq: int = 1) -> dict:
    """Upload path and send it; with msg_id it is a passive reply (msg_seq numbers the replies to it)."""
    file_info = await upload(auth, scope, target, path, name)
    body: dict = {"msg_type": 7, "media": {"file_info": file_info}, "msg_seq": msg_seq}
    if msg_id:
        body["msg_id"] = msg_id
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        return await _post(session, auth, f"{_base(scope, target)}/messages", body)


async def send_text(auth: Auth, scope: str, target: str, text: str, msg_seq: int = 1) -> dict:
    """An active text message to a user or a group."""
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        return await _post(session, auth, f"{_base(scope, target)}/messages",
                           {"msg_type": 0, "content": text, "msg_seq": msg_seq})


def token_auth(token) -> Auth:
    """An Auth over botpy's Token, which fetches and renews the access token."""
    async def auth() -> str:
        await token.check_token()
        return token.get_string()
    return auth


def main() -> None:
    from botpy.robot import Token
    from ..settings import load

    settings = load()
    parser = argparse.ArgumentParser(description="send a file as an active message to a user or a group")
    to = parser.add_mutually_exclusive_group(required=True)
    to.add_argument("--user", help="the receiver's user_openid")
    to.add_argument("--group", help="the group's group_openid, as bot.log names it after group:")
    parser.add_argument("file", type=Path)
    parser.add_argument("--name", help="the file name the receiver sees (default: the file's own)")
    parser.add_argument("--text", help="a text message sent before the file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    auth = token_auth(Token(settings["QQ_APPID"], settings["QQ_SECRET"]))
    scope, target = ("group", args.group) if args.group else ("c2c", args.user)

    async def run() -> dict:
        if args.text:
            await send_text(auth, scope, target, args.text, msg_seq=1)
        return await send_file(auth, scope, target, args.file, args.name, msg_seq=2 if args.text else 1)

    result = asyncio.run(run())
    print("sent, message id", result.get("id"))


if __name__ == "__main__":
    main()
