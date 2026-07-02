---
name: skill-stat
description: 지금까지 호출된 skill들의 사용 통계(호출 횟수, 마지막 호출 시각)를 보여준다. 사용자가 "skill 통계", "스킬 사용 통계", "skill-stat", "어떤 스킬을 많이 썼는지" 등을 물을 때 사용.
---

# Skill Usage Stats

The `~/.claude/hooks/skill-usage-log.sh` PreToolUse hook accumulates a record in
`~/.claude/skill-stats.json` every time a skill is invoked. This skill reads that
data and reports it as stats. **All output shown to the user must be in English.**

Data format:
```json
{
  "commit":     { "count": 3, "last": "2026-06-25T11:23:11Z" },
  "skill-stat": { "count": 1, "last": "2026-06-25T11:25:02Z" }
}
```

## Procedure

1. **Read the stats data** — run the command below to get a table sorted by call count (descending).

   ```bash
   STATS="$HOME/.claude/skill-stats.json"
   if [ ! -s "$STATS" ] || [ "$(jq 'length' "$STATS" 2>/dev/null)" = "0" ]; then
     echo "No skill invocations recorded yet."
   else
     jq -r '
       to_entries
       | sort_by(-.value.count)
       | (map(.value.count) | add) as $total
       | "Total invocations: \($total)\n",
         "Rank  Skill                 Count  Last called",
         "----  --------------------  -----  --------------------",
         (to_entries[] |
           "\(.key + 1 | tostring | (" " * (4 - length)) + .)  "
           + (.value.key | . + (" " * (20 - (.|length))))[0:20] + "  "
           + (.value.value.count | tostring | (" " * (5 - length)) + .) + "  "
           + (.value.value.last // "-"))
     ' "$STATS"
   fi
   ```

   > Use the sorted output above as-is. If the alignment/formatting is fiddly, a simpler form is fine too: `jq -r 'to_entries | sort_by(-.value.count)[] | "\(.key): \(.value.count) calls (last \(.value.last))"' "$STATS"`.

2. **Report it in a human-readable way (in English)** — based on the output, show the user:
   - Total cumulative invocations
   - Per-skill count and last-called time, sorted by count (descending)
   - A one-line summary of the top 1–3 most-used skills

3. **When there is no data** — if the file is missing or empty, the hook has never recorded anything yet.
   Tell the user "No invocations recorded yet," and if the hook was just registered, note that opening `/hooks` once or restarting may be required.

## Notes

- Stats file location: `~/.claude/skill-stats.json`
- Recorded by: `~/.claude/hooks/skill-usage-log.sh` (PreToolUse / matcher `Skill`)
- This `skill-stat` skill itself is invoked via the Skill tool, so it is also counted in the stats.
- To reset the stats, run `printf '{}\n' > ~/.claude/skill-stats.json`.
