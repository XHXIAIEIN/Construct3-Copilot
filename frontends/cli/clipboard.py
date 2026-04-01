"""Clipboard integration — copy JSON to system clipboard with file fallback."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyperclip


def save_json(data: dict, output_dir: Optional[Path] = None) -> str:
    if output_dir is None:
        output_dir = Path("tmp")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"cli-output-{timestamp}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def copy_json(data: dict, fallback_dir: Optional[Path] = None) -> bool:
    text = json.dumps(data, ensure_ascii=False)
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        path = save_json(data, output_dir=fallback_dir)
        print(f"  剪贴板不可用，已保存到 {path}")
        return False
