"""
루트 conftest.py
pytest 실행 시 프로젝트 루트를 sys.path에 추가하여
`from tests.e2e.config import ...` 형식의 절대 임포트를 지원한다.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
