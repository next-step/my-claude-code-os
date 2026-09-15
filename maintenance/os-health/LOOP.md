# OS 건강도 루프 — 실행할수록 개선되는 시스템 루프 (Step 3)

> 설계 배경은 [`maintenance/interviews/2026-09-14-os-health-loop.md`](../interviews/2026-09-14-os-health-loop.md) 참고.

## 한 줄 요약

세션이 끝날 때마다 이 OS의 건강 상태(`OS.md` §4 성공 기준)를 스냅샷으로 남기고,
다음 세션이 열릴 때 직전 스냅샷과 비교한 추이를 보여준다 — **세션이 쌓일수록
"이 OS가 잘 돌아가는지"를 아는 정확도가 올라간다.**

## 왜 (Why)

인터뷰에서 확인한 반복 고통: *"OS가 잘 돌아가는지 알 방법이 없다."*
랄프 루프(1부 실습)는 **하나의 목표**를 달성하면 종료되지만, 이 루프는 **종료되지 않고**
매 세션마다 실행되며 자산(이력)을 계속 쌓는다 — 정해진 태스크 안에서 도는 로컬 최적화 루프와
달리, 태스크를 만드는 워크플로우 자체를 계속 관찰·개선하는 글로벌 최적화 루프다.

## 흐름

```
세션 종료                                세션 시작
  │  SessionEnd 훅                         │  SessionStart 훅
  │  (os-health-snapshot.sh)               │  (session-open-requests.sh, 확장)
  ▼                                        ▼
maintenance/requests/*.md 스캔          history.tsv 최근 2줄 비교
  │                                        │
  ▼                                        ▼
history.tsv 에 스냅샷 한 줄 append   "[OS 건강도] ... (전 세션 대비 ±N%p)" 출력
(덮어쓰지 않음 — append 전용)
```

## 무엇을 측정하는가 — `OS.md` §4 성공 기준 재사용

| 지표 | 계산 | 방향 |
| --- | --- | --- |
| 내부 처리 비율 | `internal / (internal + outsource)` — `undecided` 제외 | ↑ |
| 평균 처리 일수 | 종결 상태(`done`/`handed_off`/`outsourced`) 요청의 `updated - created` 평균 | ↓ |
| blocked 비율 | `status:blocked` 요청 수 / 전체 요청 수 | ↓ |

새 DB 없이 기존 케이스 파일 frontmatter만 읽는다 (`OS.md` §5 원칙 3).

## 루프가 나아지는지 재는 지표 — OS 건강도 수식

위 세 지표 각각의 추이만 봐도 되지만, "루프가 전반적으로 나아지고 있는지"를 한눈에 보려고
정량 지표 하나(0~100)로 합쳤다.

```
OS 건강도 = 100 - blocked 비율
```

- **내부 처리 비율은 합산에서 뺐다.** 처음엔 `(내부처리비율 + (100 - blocked비율)) / 2` 로
  설계했는데, 이러면 "역량 밖이라 정당하게 외주로 보낸 것"과 "내부에서 붙잡고 있다가 막혀
  시간을 낭비한 것"이 같은 방향(둘 다 감점)으로 섞인다. 실사용 중 실제로 정당한 outsource
  요청 1건 때문에 점수가 100→84로 떨어지는 걸 보고 이 결함을 발견해 수정했다 — 판단 과정은
  [`2026-09-14-os-health-loop.md`](../interviews/2026-09-14-os-health-loop.md) §7 참고.
- 그래서 지금은 **"실행이 막혔는가"만** 감점 대상이다. outsource 로 보낸 것 자체는 감점하지 않는다.
- 평균 처리 일수도 합산에 안 넣는다 — "며칠이 좋은 건지" 자연스러운 상한이 없어서, 임의의
  기준(예: "3일 이내면 만점")을 지어내는 대신 별도 추이로만 본다
  (`.claude/context/dod-patterns.md` 안티패턴 "임의 기준 도입" 회피와 같은 원칙).
- 내부 처리 비율·평균 처리 일수는 `history.tsv`·`SessionStart` 브리핑에 여전히 표시된다 —
  건강도 점수에서만 빠졌을 뿐, 추이 관찰 대상에서 빠진 건 아니다.

## 저장 형식

`maintenance/os-health/history.tsv` — 탭 구분, append 전용.

```
# date	total	classified	internal_rate_pct	avg_days	blocked_rate_pct	health_score
2026-09-14T23:10	1	1	100	0.0	0	100
2026-09-15T20:26	3	3	67	0.0	0	100
```

## 실행 확인 (수동 재현, 실제 훅과 동일 로직)

```bash
$ CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/os-health-snapshot.sh
$ CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/session-open-requests.sh
[유지보수 OS] 진행 중인 요청 없음. 새 요청은 /intake 로 접수하세요.
[OS 건강도] 100/100(전 세션 대비 0) · 요청 3건 · 내부처리 67%(0%p) · 평균처리 0.0일 · blocked 0%(0%p)
```

요청이 1건 → 3건(internal 2·outsource 1)으로 늘어도 아무것도 blocked 되지 않았으니 건강도는
100 그대로다 — outsource 자체는 더 이상 감점 요인이 아님을 보여주는 실행 결과.

## 한계 / 남은 가정

인터뷰 가정 원장([해당 파일](../interviews/2026-09-14-os-health-loop.md) §5)의 위험 `중간` 항목 2개가 아직 남아 있다.

- 조회는 `SessionStart` 훅 확장으로만 한다 — 별도 `/digest` 조회 스킬은 1차 범위 밖
- `SessionEnd` 훅 이벤트가 실제 Claude Code 하네스에서 매 세션 종료마다 정확히 발화하는지는
  실사용(여러 번의 실제 세션 종료)으로 재확인 필요 — 지금까지는 스크립트를 수동 실행해 로직만 검증했다

상태 스냅샷만 쌓을 뿐 **원인을 자동으로 고치지는 않는다** — "같은 문제가 반복되면 자동으로
고친다"는 수준까지는 가지 않은 1차 범위(추후 확장 가능).
