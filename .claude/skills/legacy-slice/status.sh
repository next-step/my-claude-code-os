#!/usr/bin/env bash
# Environment status for the legacy-slice orchestrator.
# Reads .claude/config/workspace.json and probes each moving part, so Phase 0 does not
# have to guess what is up. Every probe is read-only and fails soft.
#
# Nothing here names a surface, a port, or a directory: those come from the config, so
# this file stays publishable and works for a workspace whose surfaces are named
# something else entirely.
#
# Python decides *what* to report and formats the labels; bash only runs curl and
# docker. The two talk over TSV so a path containing a space cannot shift a field.
set -uo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CFG="$ROOT/.claude/config/workspace.json"

if [ ! -f "$CFG" ]; then
  echo "workspace.json 없음 — .claude/config/workspace.example.json 을 복사해 채우세요"
  exit 0
fi

# curl prints 000 when it cannot connect; report that as DOWN rather than a status code.
probe() {
  local code
  [ -z "$1" ] && { echo "주소 없음"; return; }
  code=$(curl -s -o /dev/null -m 2 -w "%{http_code}" "$1" 2>/dev/null)
  if [ -z "$code" ] || [ "$code" = "000" ]; then echo "DOWN"; else echo "$code"; fi
}

while IFS=$'\t' read -r kind a b; do
  case "$kind" in
    LINE)   printf '%s\n' "$a" ;;
    PROBE)  printf '%s = %s\n' "$a" "$(probe "$b")" ;;
    JAVA)
      if [ -z "$b" ]; then
        printf '%s javaHome 미설정 — gradle 이 기본 JDK 로 돌아 실패할 수 있음\n' "$a"
      elif [ ! -x "$b/bin/java" ]; then
        printf '%s javaHome 경로에 JDK 없음\n' "$a"
      else
        printf '%s%s\n' "$a" "$("$b/bin/java" -version 2>&1 | head -1 | sed 's/.*version //; s/"//g')"
      fi ;;
    DOCKER)
      if command -v docker >/dev/null 2>&1 && [ -d "$b" ]; then
        up=$(cd "$b" && docker compose ps --services --status running 2>/dev/null | tr '\n' ' ')
        printf '%s%s\n' "$a" "${up:-(기동 중인 서비스 없음)}"
      else
        printf '%s compose 디렉토리 확인 불가\n' "$a"
      fi ;;
  esac
done < <(python3 - "$CFG" <<'PY'
import json, os, re, sys

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
legacy, backend = cfg.get("legacy") or {}, cfg.get("backend") or {}
docs, e2e = cfg.get("docs") or {}, cfg.get("e2e") or {}
out = []
def line(t):        out.append(f"LINE\t{t}\t")
def probe(lbl, url): out.append(f"PROBE\t{lbl}\t{url or ''}")

# ── backend modules ────────────────────────────────────────────────────────
first = True
for name in ("proxy", "fixity"):
    mod = backend.get(name) or {}
    port = mod.get("port")
    head = "backend  : " if first else "           "
    first = False
    if not port:
        line(f"{head}{name:<7} 포트 미설정")
    else:
        probe(f"{head}{name:<7} :{port}", f"http://localhost:{port}/actuator/health")
if first:
    line("backend  : 모듈 설정 없음")
# 빌드가 기본 JDK 로 돌면 버전 번호 한 줄만 남기고 죽는다. Phase 0 에서 보이게 한다.
out.append(f"JAVA\t           gradle JDK  \t{backend.get('javaHome') or ''}")

# ── legacy surfaces — whatever they are named ──────────────────────────────
surfaces = legacy.get("surfaces") or {}
first = True
for name, s in surfaces.items():
    head = "legacy   : " if first else "           "
    first = False
    probe(f"{head}{name:<7}", (s or {}).get("localBaseUrl"))
if first:
    line("legacy   : 표면 설정 없음")

# ── docker ─────────────────────────────────────────────────────────────────
out.append(f"DOCKER\tdocker   : \t{(legacy.get('docker') or {}).get('composeDir') or ''}")

# ── slices — the highest-numbered artifact is the phase reached ────────────
PHASE = {
    "00": "원장 있음        (Phase 1~2)",
    "01": "설계 있음        (Phase 3 끝 · 게이트 1)",
    "02": "스왑 있음        (Phase 5 끝)",
    "03": "감사 있음        (Phase 7 끝)",
    "04": "문서 있음        (Phase 8 · 완료)",
}
root, sub = docs.get("root"), docs.get("slicesDir") or "slices"
sdir = os.path.join(root, sub) if root else None
if not sdir or not os.path.isdir(sdir):
    line(f"슬라이스 : 디렉토리 없음 ({sdir or '경로 미설정'})")
else:
    names = sorted(n for n in os.listdir(sdir) if os.path.isdir(os.path.join(sdir, n)))
    if not names:
        line("슬라이스 : (없음)")
    for i, n in enumerate(names):
        nums = sorted(m.group(1) for f in os.listdir(os.path.join(sdir, n))
                      if (m := re.match(r"(\d\d)-", f)))
        head = "슬라이스 : " if i == 0 else "           "
        state = PHASE.get(nums[-1], "?") if nums else "빈 디렉토리      (Phase 0)"
        line(f"{head}{n:<24} {state}")

line(f"e2e      : {e2e.get('root') or '경로 미설정'}")
print("\n".join(out))
PY
)
