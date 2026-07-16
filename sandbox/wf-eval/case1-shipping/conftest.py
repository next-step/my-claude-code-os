"""프로젝트 루트를 sys.path에 추가해 `from src...` import가 어디서 pytest를 실행해도 동작하게 한다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
