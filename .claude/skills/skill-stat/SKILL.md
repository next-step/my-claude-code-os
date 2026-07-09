---
name: skill-stat
description: 지금까지 호출된 skill들의 사용 통계(호출 횟수, 마지막 호출 시각)를 보여준다. 사용자가 "skill 통계", "스킬 사용 통계", "skill-stat", "어떤 스킬을 많이 썼는지" 등을 물을 때 사용.
---

# Skill Usage Stats

The `.claude/hooks/skill-usage-log.sh` PreToolUse hook appends one line to
`.claude/skill-usage.log` every time a skill is invoked. This skill aggregates that
log and reports it as stats. **All output shown to the user must be in English.**

Data format — one tab-separated line per invocation, append-only:

```
2026-07-09T07:22:40Z	skill-stat
2026-07-09T07:22:41Z	commit
2026-07-09T07:22:42Z	orchestrate
```

> Counting happens at read time, not write time. There is no JSON state file to
> keep consistent, and the raw call history stays available.
> **`jq` is not installed in this environment** — never reach for it here.

## Procedure

1. **Aggregate the log** — run this as a single Bash command.

   ```bash
   LOG="$CLAUDE_PROJECT_DIR/.claude/skill-usage.log"
   if [ ! -s "$LOG" ]; then
     echo "No skill invocations recorded yet."
   else
     echo "Total invocations: $(wc -l < "$LOG" | tr -d ' ')"
     echo
     awk -F'\t' '{c[$2]++; last[$2]=$1} END {for (s in c) printf "%d\t%s\t%s\n", c[s], s, last[s]}' "$LOG" \
       | sort -rn -k1,1 \
       | awk -F'\t' 'BEGIN {printf "%-5s %-22s %6s  %s\n", "Rank", "Skill", "Count", "Last called"
                            printf "%-5s %-22s %6s  %s\n", "----", "----------------------", "-----", "--------------------"}
                     {printf "%-5d %-22s %6d  %s\n", NR, $2, $1, $3}'
   fi
   ```

2. **Report it in a human-readable way (in English)** — based on the output, show the user:
   - Total cumulative invocations
   - Per-skill count and last-called time, sorted by count (descending)
   - A one-line summary of the top 1–3 most-used skills

3. **When there is no data** — the file is missing or empty, so the hook has never
   recorded anything. Tell the user "No invocations recorded yet." If the hook was
   only just registered, note that `settings.json` is read at session start, so a
   **new session** is required before the first line appears.

## Notes

- Log file: `.claude/skill-usage.log` (git-ignored — local usage data)
- Written by: `.claude/hooks/skill-usage-log.sh` (PreToolUse / matcher `Skill`)
- If the hook ever fails to parse a payload it leaves a trace in `.claude/skill-usage.err`.
  If stats look wrong, check that file first.
- This `skill-stat` skill is itself invoked via the Skill tool, so it is counted too.
  The hook runs *before* the tool, so the current invocation is already in the log
  by the time you read it.
- To reset the stats: `rm -f "$CLAUDE_PROJECT_DIR/.claude/skill-usage.log"`
