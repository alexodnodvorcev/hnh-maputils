import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir():
    """Путь к папке с фикстурами"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def example_hmap(fixtures_dir):
    """Путь к example.hmap"""
    return fixtures_dir / "example.hmap"


@pytest.fixture
def temp_dir(tmp_path):
    """Временная папка для выходных файлов (автоматически очищается)"""
    return tmp_path


@pytest.fixture
def run_script():
    """Фикстура для запуска скрипта"""
    def _run_script(args, **kwargs):
        return subprocess.run(
            [sys.executable, "src/maputils.py"] + args,
            capture_output=True,
            text=True,
            timeout=10,
            **kwargs
        )
    return _run_script
