#!/bin/sh
# rec_timing.sh <run-dir-relative-to-iteration-1> <total_tokens> <duration_ms>
# 서브에이전트 완료 알림에만 실려 오는 값이라 그 자리에서 바로 남긴다 (SKILL.md:203).
IT=".claude/skills/spec-decompose-workspace/iteration-1"
printf '{\n  "total_tokens": %s,\n  "duration_ms": %s,\n  "total_duration_seconds": %s\n}\n' \
  "$2" "$3" "$(awk "BEGIN{printf \"%.1f\", $3/1000}")" > "$IT/$1/timing.json"
echo "recorded $1"
