# tests/test_main.py
import pytest
import subprocess
import sys
import json
from pathlib import Path

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====


def run_script(args, **kwargs):
    """Запускает maputils.py с переданными аргументами"""
    return subprocess.run(
        [sys.executable, "src/maputils.py"] + args,
        capture_output=True,
        text=True,
        timeout=10,
        **kwargs
    )


def files_are_equal(file1: Path, file2: Path) -> bool:
    """Сравнивает два файла"""
    return file1.read_bytes() == file2.read_bytes()

# ===== ТЕСТЫ =====


def test_hmap2json_conversion(example_hmap, temp_dir):
    json_file = temp_dir / "long_test.json"
    hmap_file = temp_dir / "example.hmap"

    result1 = run_script([
        "-hmap2json", str(example_hmap),
        "-o", str(json_file)
    ])
    assert result1.returncode == 0, f"hmap2json failed: {result1.stderr}"
    assert json_file.exists(), "JSON file was not created"

    result2 = run_script([
        "-json2hmap", str(json_file),
        "-o", str(hmap_file)
    ])
    assert result2.returncode == 0, f"json2hmap failed: {result2.stderr}"
    assert hmap_file.exists(), "HMap file was not created"

    assert files_are_equal(example_hmap, hmap_file), \
        f"Files differ: {example_hmap} and {hmap_file}"
