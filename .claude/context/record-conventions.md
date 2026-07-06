# 기록 규약 (record-conventions)

> 추천·분석·회고 기록을 남기고 읽는 공통 규칙. 출처: docs/OS.md 기록 설계 (save_analysis.py·save_run.py·save_retro.py).

## 공통: append-only 박제

- 모든 기록은 `data/` 아래에 **append-only**로 남긴다. 과거 기록을 수정·삭제하지 않는다(예측 박제 — 회고가 성패를 검증할 원본).
- 파일명은 `YYYY-MM-DD-<이름>.md`. **같은 날 재실행은 `-2`, `-3`…** 접미사로 새 파일을 만든다(과거를 덮지 않음).

## 기록 3종과 책임

| 기록 | 경로 | 작성 주체 | 담는 것 |
|------|------|----------|---------|
| 분석 1건 | `data/analyses/YYYY-MM-DD-회사.md` | `save_analysis.py` (analyze-company) | 진입/목표/손절·근거·atr_pct 스냅샷. **가격 수치의 단일 진실원천** |
| 선정 결정 | `data/recommendations/YYYY-MM-DD-run.md` | `save_run.py` (recommend-stocks) | 필터 기준·단계별 개수·탈락 표본(당시가 포함)·picks |
| 회고 | `data/retros/YYYY-MM-DD-retro.md` | `save_retro.py` (portfolio-retrospect) | 토론 경위·종목별 평가·튜닝안 |

## frontmatter 스키마 핵심

- **분석 기록**: 정량(진입/목표/손절·atr_pct 등)은 frontmatter에, 근거는 본문에. `status:`는 `open`으로 시작 — **회고만 이 한 줄을 갱신**하고 나머지는 불변.
- **status 전이**: `open → watching → hit_target | stopped`. 터미널 상태(hit_target/stopped)는 **sticky** — 한 번 도달하면 이후 가격이 되돌아와도 바꾸지 않는다("그땐 맞았다"가 사건의 진실).
- **ref 역참조**: 추천 기록의 `picks[].analysis`에는 분석 기록의 상대경로 ref만 담는다. 진입/목표/손절 숫자를 추천 기록에 **복제하지 않는다** — 표를 그릴 땐 ref를 따라가 분석 frontmatter에서 끌어오고, 없으면 "참조불가"로 표기.

## 읽을 때 주의

- `actual_return_pct`류 수치는 실현수익이 아니라 **진입갭(미체결)**일 수 있다 — 진입 체결여부·MFE/MAE 필드와 함께 해석한다(2026-06-30 회고에서 오독 사례 확정).
- standalone 분석(사용자 직접 요청)과 추천 바스켓 분석은 **context를 분리해 집계**한다(선정 논리가 다름).
