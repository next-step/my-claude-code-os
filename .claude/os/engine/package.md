# engine

속성이 무엇인지 모른 채 사이클을 돌리는 공통 코어. 속성이 늘어도 이 패키지는 바뀌지 않는다.

## 소유

| 종류 | 파일 |
|---|---|
| 계약 | `contracts/customization-boundary.md` · `contracts/policy-layer.md` · `contracts/declared-leaks.json` |
| 목표 | `goal.md` — 프로세스 전체가 무엇을 성공으로 보는가 |
| 오케스트레이터 | `scripts/run_catalog_cycle.py` |
| 프로필 해석 | `scripts/catalog_profile.py` |
| 심판 | `scripts/arbitrate.py` |
| 정책 인덱스 | `scripts/build_policy_index.py` |
| 진행률 | `scripts/build_review_progress.py` |
| 판정 원장 | `scripts/record_review_decision.py` |
| 리포트 | `scripts/render_catalog_report.py` |
| 보고서 형태 점검 | `scripts/check_report_shape.py` — 훅이 부른다. 진입점 링크는 `.claude/hooks/check-report-shape.py` |
| 뼈대 | `templates/goal.md` · `templates/policy.md` · `templates/precedent.md` |
| 테스트 | `tests/` — 계약 회귀와 패키지 경계 |
| 스킬 | `skills/` — `catalog-data-os` · `catalog-policy-golden-audit` · `catalog-review-decision` · `catalog-audit-report` |
| 에이전트 | `agents/catalog-golden-adjudicator.md` — 큐의 한 건이 정책 공백인가 GT 오류인가 실행 오류인가 |
| 진입점 링크 | `.claude/skills/<이름>` · `.claude/agents/engine/<이름>.md` → 여기. 실체는 이 패키지가 소유한다 |

## 규칙

- **속성 이름을 코드에 쓰지 않는다.** 기본 프로필도 `attributes/*/profile.json`을 찾아서 정하고,
  둘 이상이면 `--profile`을 요구한다. 하드코딩된 기본값은 그 자체로 도메인 누수다.
- **프로젝트 루트는 폴더 깊이로 세지 않는다.** `.claude`를 가진 상위 폴더를 찾는다.
  깊이를 세면 패키지를 옮길 때마다 인덱스가 조용히 틀린다.
- **만든 것은 `run-summary.json`의 `artifacts`에 선언한다.** 하류가 경로를 관습으로 추측하기
  시작하면 그것은 계약이 아니다. 선언되지 않은 산출물은 심사에서 `SKIPPED`로 남는다.
- 도메인 어휘가 불가피하게 남으면 `contracts/declared-leaks.json`에 이유와 후속 조치를 적는다.
- **보고서 형태 점검은 어떤 run이든 같은 계약으로 본다.** 기준선은 언제나 `run-summary.json`이다.
  점검이 속성별 예외를 갖기 시작하면 그것은 이미 엔진이 아니다.

## 실행 순서

```
import 어댑터 → audit 어댑터 → arbitrate → build_policy_index → build_review_progress → render_catalog_report
```

앞의 셋은 속성이 제공하고, 뒤의 셋은 엔진이 제공한다.

## 보고서 형태 점검

`PostToolUse` 훅이 보고서가 갱신된 직후 자동으로 돈다. 네 가지를 본다 — 선언한 산출물이
실제로 있는가, 큐 건수와 요약 숫자가 같은가, 보고서의 `N건`·`N%`가 요약에서 나올 수 있는
값인가, HTML이 이번 요약의 신호를 담고 있는가.

세 번째가 핵심이다. 이 프로젝트의 규칙은 **다시 세어야 하는 숫자를 문서에 적지 않는다**이고,
복사된 숫자는 조용히 틀린 채로 판단 근거가 된다. 훅은 사람이 기억하지 않아도 그 순간에 돈다.

최근에 갱신된 run만 본다. 훅은 모든 Bash·Write·Edit 뒤에 붙으므로, 무관한 명령에서
조용하지 않으면 그 자체가 소음이 된다. 손으로 돌릴 때는 창을 무시하게 할 수 있다.

```bash
.claude/hooks/check-report-shape.py --all
```

## 검증

```bash
python3 -m pytest .claude/os/engine/tests -q
```
