import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope='session')
def app():
    '''Load the application module without running the command-line entry point.'''
    spec = importlib.util.spec_from_file_location('app', ROOT / 'app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='session')
def analyzer():
    from analysis import make_analyzer
    return make_analyzer()
