# 랄프 루프 상태 (loop)

> `/ralph` 오케스트레이터가 매 이터레이션마다 갱신한다. 이 파일이 있으면 진행 중인 루프다.
> 새 루프를 시작할 때 이 템플릿을 `.claude/ralph/loop.md`로 복사해 채운다.
> 컨텍스트가 리셋돼도 이 파일의 히스토리에서 마지막 지표·이터레이션을 복원해 이어간다.

status: running        # running | converged | budget_exhausted | stalled | regressed_out
started_at: <시각>
updated_at: <시각>

## 계약 (파라미터 — 시작 게이트에서 사람이 확정)
- 목표(goal): 테스트 라인 커버리지를 목표값까지 끌어올린다
- 지표(metric): `.claude/ralph/measure-coverage.sh line`  (stdout에 커버리지 % 하나)
- 방향(direction): maximize        # maximize≥T | minimize≤T | reach==T
- 목표값(target): 90.0
- 예산(budget): 8                  # 최대 이터레이션 (안전 상한)
- 인내(patience): 3                # 무개선/악화 연속 N회면 정체로 중단
- 회귀 가드(guard): on             # 지표 악화·테스트 깨짐 시 그 이터레이션 롤백

## 지표 히스토리 (append-only — 루프의 심장)
| iter | 지표값 |  델타  | 조치 | 채택? |
|-----:|-------:|------:|------|:----:|
|  0(base) | <baseline> |  —   | 측정만 | — |

## 종료 요약 (루프가 끝날 때 채움)
- baseline → final:
- 이터레이션 수:
- 목표 도달:
- 미달 시 원인/다음 선택지:

## 로그
- [start]
