"""Tests for clipboard module — copy + file fallback."""
import json
import pytest
from unittest.mock import patch
from pathlib import Path

from frontends.cli.clipboard import copy_json, save_json


class TestSaveJson:
    def test_save_creates_file(self, tmp_path):
        data = {"c3type": "events", "items": []}
        path = save_json(data, output_dir=tmp_path)
        assert Path(path).exists()
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_filename_pattern(self, tmp_path):
        data = {"key": "value"}
        path = save_json(data, output_dir=tmp_path)
        assert "cli-output-" in Path(path).name
        assert path.endswith(".json")


class TestCopyJson:
    @patch("frontends.cli.clipboard.pyperclip")
    def test_copy_success(self, mock_pyperclip):
        data = {"c3type": "events"}
        result = copy_json(data)
        assert result is True
        mock_pyperclip.copy.assert_called_once()
        copied_text = mock_pyperclip.copy.call_args[0][0]
        assert json.loads(copied_text) == data

    @patch("frontends.cli.clipboard.pyperclip")
    def test_copy_fallback_on_error(self, mock_pyperclip, tmp_path):
        mock_pyperclip.copy.side_effect = Exception("No clipboard")
        data = {"c3type": "events"}
        result = copy_json(data, fallback_dir=tmp_path)
        assert result is False
        files = list(tmp_path.glob("cli-output-*.json"))
        assert len(files) == 1
