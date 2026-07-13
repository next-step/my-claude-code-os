---
name: skill-stats
description: 스킬 호출 통계를 표로 보여주는 스킬. "스킬 통계", "스킬 얼마나 썼어", "스킬 사용 현황", "/skill-stats" 요청 시 사용. .claude/skill_calls.log를 파싱해서 스킬별 호출 횟수, 비율, 최근/첫 호출 시간을 테이블로 출력.
metadata:
  author: baeg-yunseo
  version: "1.2.0"
---

# Skill Stats

`.claude/skill_calls.log`를 읽어 스킬 사용 통계를 테이블로 출력합니다.

---

## 실행 방법

아래 Python 스크립트를 Bash 도구로 실행합니다:

```bash
python3 << 'EOF'
import os
from collections import defaultdict
from datetime import datetime

LOG_PATH = os.path.join(os.getcwd(), ".claude", "skill_calls.log")
PROJECT_SKILLS_DIR = os.path.join(os.getcwd(), ".claude", "skills")
USER_SKILLS_DIR = os.path.expanduser("~/.claude/skills")

if not os.path.exists(LOG_PATH):
    print("아직 기록된 스킬 호출이 없습니다. 스킬을 사용하면 자동으로 기록됩니다.")
    exit()

def skill_type(name):
    # 네임스페이스(콜론 포함) 스킬은 플러그인(내장)
    if ":" in name:
        return "내장"
    if os.path.isdir(os.path.join(PROJECT_SKILLS_DIR, name)):
        return "커스텀"
    if os.path.isdir(os.path.join(USER_SKILLS_DIR, name)):
        return "커스텀"
    return "내장"

counts = defaultdict(int)
first_seen = {}
last_seen = {}

with open(LOG_PATH) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 3)
        if len(parts) < 3:
            continue
        ts_str = f"{parts[0]} {parts[1]}"
        skill = parts[2]
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        counts[skill] += 1
        if skill not in first_seen or ts < first_seen[skill]:
            first_seen[skill] = ts
        if skill not in last_seen or ts > last_seen[skill]:
            last_seen[skill] = ts

total = sum(counts.values())
rows = sorted(counts.items(), key=lambda x: -x[1])

print(f"\n총 스킬 호출: {total}회\n")
print(f"{'스킬':<30} {'구분':<6} {'호출':>6} {'비율':>7}  {'최근 호출':<16}  {'첫 호출'}")
print("-" * 88)
for skill, cnt in rows:
    pct = cnt / total * 100
    last = last_seen[skill].strftime("%Y-%m-%d %H:%M")
    first = first_seen[skill].strftime("%Y-%m-%d %H:%M")
    kind = skill_type(skill)
    print(f"{skill:<30} {kind:<6} {cnt:>6} {pct:>6.1f}%  {last:<16}  {first}")
print("-" * 88)
EOF
```

---

## 출력 예시

```
총 스킬 호출: 12회

스킬                            구분    호출    비율  최근 호출           첫 호출
----------------------------------------------------------------------------------------
smart-commit                   커스텀      5   41.7%  2026-06-25 20:34  2026-06-20 09:15
update-config                  내장        3   25.0%  2026-06-25 20:26  2026-06-22 14:30
review                         내장        2   16.7%  2026-06-24 11:20  2026-06-23 10:00
skill-stats                    커스텀      2   16.7%  2026-06-25 20:45  2026-06-25 20:40
----------------------------------------------------------------------------------------
```

## 구분 기준

| 구분 | 조건 |
|------|------|
| 커스텀 | `.claude/skills/<name>/` 또는 `~/.claude/skills/<name>/` 디렉토리가 존재 |
| 내장 | 위 경로에 없거나, `namespace:skill` 형태의 플러그인 스킬 |

---

## 주의사항

- 로그 파일이 없으면 안내 메시지를 출력하고 종료
- `PostToolUse` 훅이 `.claude/settings.json`에 설정되어 있어야 기록됨
