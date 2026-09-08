#!/usr/bin/env bash
set -euo pipefail

# 이 속성의 사이클 진입점. 엔진은 어느 속성이 있는지 알지 않는다.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$OS_ROOT/engine/scripts/run_catalog_cycle.py" \
  --profile "$SCRIPT_DIR/profile.json" \
  "$@"

# 엔진이 끝나면 심사가 이어진다. 둘을 잇는 것은 호출이 아니라 산출물이다 —
# 심사는 프로필도 어댑터도 모르고, 방금 갱신된 run-summary.json만 읽는다.
# 그래서 여기서 넘기는 것도 프로필이 아니라 산출물 폴더 하나뿐이다.
RUN_ROOT="$(python3 - "$SCRIPT_DIR/profile.json" <<'PY'
import json, sys
from pathlib import Path

profile = Path(sys.argv[1]).resolve()
project_root = next(parent for parent in profile.parents if (parent / ".claude").is_dir())
print(project_root / json.loads(profile.read_text(encoding="utf-8"))["outputRoot"])
PY
)"
python3 "$OS_ROOT/review/scripts/review_run.py" --run "$RUN_ROOT"
