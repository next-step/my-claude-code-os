---
name: code-run
description: Produce ACTUALLY-RUNNABLE code that implements the paper's method — the user (or Claude) can run it and it really executes and does the task. Pick the medium by what genuinely runs the method: a terminal/CLI project (Python/Node/…) for model/compute tasks (default), or a self-contained HTML only when the method truly runs client-side. Real running code is the priority, NOT a visualization/dashboard of numbers. Output a runnable project under output/<slug>/app/ + a run guide. Use after /code (코드실행).
---

# /code-run — 실제 실행 코드 구현 스킬 (코드실행!)

`/code` 분석 결과를 받아, **논문의 방법을 실제로 구현해 "진짜 돌아가는 코드"** 를 만든다.

> 핵심 원칙 (이 스킬의 정체성):
> 1. **실제 돌아가는 코드가 우선 (Runnable Code First)** — 논문 수치를 "보여주는" 시각화·대시보드·애니메이션이 목표가 아니다. **논문의 태스크를 실제로 수행하는, 사용자가 돌릴 수 있는 코드**가 목표다. 화면 UI/지표 표시에 힘을 빼지 말고, 실행되는 구현에 집중한다.
> 2. **매체는 "실제로 돌아가는 것" 기준으로 고른다** —
>    - **모델/컴퓨트/CLI/서버 태스크**(예: GPT-2 생성, 학습·추론 파이프라인) → **터미널 실행 프로젝트**(Python/Node CLI 등): 진입 스크립트 + 고정 의존성 + 실행 스크립트 + README(복붙 명령). **이게 기본값.**
>    - **순수 클라이언트사이드 알고리즘**(브라우저에서 진짜로 계산되는 것, 예: 픽셀 연산·자료구조) → 자급식 HTML도 **실제로 그 알고리즘을 돌린다면** 허용. 단 "보여주기"가 아니라 실제 실행이어야 함.
>    - 판단 기준 한 줄: **"이게 논문의 방법을 실제로 실행하는가?"** 실제 실행 > 시각화.
> 3. **진짜 구현, 대체는 최소화·라벨** — 논문의 방법을 실제 코드로 구현한다. 돌릴 수 있는 건 실제 라이브러리/모델로 돌린다(예: `transformers`로 실제 GPT-2 추론, 실제 평가지표 계산). **정말 못 구하는 것**(독점 가중치 등)만 라벨된 대체로 두고 명시한다. 결과·로그를 지어내지 않는다.
> 4. **실행으로 검증** — 런타임이 이 환경에서 가능하면 클로드가 **직접 실행해** 동작을 확인한다. 불가하면(예: 이 환경의 python은 Store 스텁이라 실패) **정확한 복붙 명령**을 주고 "사용자가 자기 터미널에서 실행"임을 명시한다. 실행 안 했으면 로그를 지어내지 말 것("미실행"으로 표기).

> 슬래시 이름: `/code-run` (원 요청의 `/코드실행!`에 해당).

## 입력 (우선순위)
1. `output/<slug>/04_runcard.md` (있으면 최우선 — 실행 사실 요약 카드)
2. `output/<slug>/04_code.md` (논문↔코드 매핑, 진입점, 하이퍼파라미터, **실구현 가능한 부분 ↔ stand-in 필요 부분** 구분)
3. `output/<slug>/01_analysis.md` (방법·태스크·보고 지표의 정본)
4. `output/<slug>/app/LEARNINGS.md` (있으면 — 이전 루프 학습)
5. `output/<slug>/app/scorecard.json` (있으면 — 직전 점수·미달 항목, 우선 개선)

없으면 먼저 `/analyzer`·`/code`를 돌려야 한다.

## 절차
1. **매체 결정** — 논문의 태스크가 실제로 돌아가는 매체를 고른다(원칙 2). 모델/컴퓨트면 터미널 CLI. 근거를 한 줄 남긴다.
2. **실제 태스크 + 실구현 범위 확정** — 논문의 대표 태스크(예: 레시피 생성 + 평가)와, 브라우저/로컬에서 **실제로 실행 가능한 부분** vs **stand-in이 불가피한 부분**을 `04_code.md` 근거로 나눈다. 실구현 가능한 알고리즘 기여(포맷·자료구조·평가지표·추론 호출)는 전부 실제로 구현한다.
3. **개선 우선순위 반영** — `LEARNINGS.md`·직전 `scorecard.json`의 `must_fix`를 먼저 반영.
4. **runnable 프로젝트 작성** — `output/<slug>/app/` 아래에:
   - **진입 스크립트**(예: `main.py`/`cli.py`/`index.js`) — 논문 태스크를 실제로 수행. 인자/입력을 받아 **실제 출력**을 낸다.
   - **핵심 구현 모듈** — 논문의 방법을 실제 코드로. 실제 라이브러리/모델 사용(가능하면). 못 구하는 부분만 라벨된 stand-in.
   - **고정 의존성**(`requirements.txt`/`package.json`, 버전 고정) + **실행 스크립트**(`run.ps1`/`run.sh`) + **README.md**(복붙 명령: 설치→실행, 예시 입력/출력, 필요 자원).
   - 작은 **샘플 입력**(내장 예시)으로 인자 없이도 동작하게.
5. **실행 검증** — 런타임 가능하면 클로드가 직접 실행해 출력 확인(README에 실측 로그 첨부). 불가하면 복붙 명령 + "사용자 실행 필요" 명시, 로그는 미실행 표기.
6. **run 가이드 발행** — `output/<slug>/05_run.md`에 실행법(터미널 명령)·기대 출력·자원 요구·정직성 고지 정리. `output/<slug>/app/REPRODUCE.md`에 "무엇을 실제로 구현/실행했나 ↔ 논문 근거"를 표로(→ `/score` 채점 입력).

## 산출물
- **`output/<slug>/app/`** (정본) — 실제 실행되는 프로젝트(진입 스크립트 + 모듈 + 고정 의존성 + 실행 스크립트 + README + 샘플 입력). 순수 클라이언트사이드 알고리즘일 때만 대신 자급식 실행 HTML 가능.
- **`output/<slug>/app/REPRODUCE.md`** — 실제 구현/실행 항목 ↔ 논문 근거 매핑(채점 입력).
- **`output/<slug>/05_run.md`** — 실행 가이드(복붙 터미널 명령 + 기대 출력 + 정직성 고지).

### `05_run.md` 템플릿
```markdown
# 실행 가이드: <제목>

> 실제 실행 코드입니다. <실제로 구현/실행되는 것>은 진짜로 돌아가고, <불가피한 stand-in>만 라벨된 대체입니다.
> 원본 공식 레포: <URL>

## 실행 방법 (복붙)
​```bash
cd output/<slug>/app
pip install -r requirements.txt        # 또는 npm install
python main.py --<예시 인자>            # 또는 node index.js / bash run.sh
​```

## 기대 출력
- <실행하면 실제로 나오는 것: 생성 결과·계산된 지표·파일 등>

## 자원 요구 / 정직성
- <필요 런타임·모델 다운로드·CPU/GPU>. <stand-in으로 대체한 부분과 이유>.
- 실제 실행 로그: <클로드가 돌렸으면 실측 첨부, 아니면 "사용자 실행 필요/미실행">.
```

## 실행 주체 규칙
- 런타임이 이 환경에서 되면 클로드가 **직접 실행해 검증**한다(무거운 다운로드/학습 전에는 먼저 고지).
- 안 되면(스텁 python 등) 복붙 명령을 주고 **사용자가 실행**하게 한다. 실행 안 한 로그를 지어내지 않는다.
- 실제 모델 가중치로 추론하지 않았으면 그렇게 주장하지 않는다.

## 에이전트 간 소통 (협업 규약)
같은 논문을 다루는 **analyzer·code·code-run** 은 독립 컨텍스트라 공용 게시판 **`output/<slug>/CHANNEL.md`** 로만 소통한다. 이 스킬은 구현을 하며 **가장 많이 질문하는 소비자**다.
- **시작 전**: `CHANNEL.md`가 있으면 읽고, `analyzer`/`code`가 남긴 답변(`→ code-run RESOLVED`)을 반영. 나 앞으로 온 OPEN 질문에 답한다.
- **막히면 물어라**: 구현에 꼭 필요한데 `01_analysis.md`/`04_code.md`에 없거나·모순되거나·불명확하면 지어내지 말고 남긴다:
  - `## Q<n> [code-run → analyzer] (OPEN)` — 논문 내용·수치·방법
  - `## Q<n> [code-run → code] (OPEN)` — 저장소·진입점·의존성·실제 코드값
  (끝에 append, 기존 삭제 금지.)

## 품질 기준
- **실제로 실행돼야 한다**: 복붙 명령으로 (사용자 또는 클로드가) 돌리면 논문 태스크가 실제로 수행되고 **진짜 출력**이 나온다. 시각화/목업은 목표가 아니다.
- 논문의 **방법이 실제 코드로 구현**돼 있어야 한다(하드코딩된 결과·가짜 로그 금지). stand-in은 최소화하고 라벨.
- 의존성은 **버전 고정**, 진입점·실행 명령이 명확해야 한다(재현성).
- 실행 로그는 실측만. 미실행이면 "미실행"으로 정직하게.
- 완료 후 `app/` 진입점 경로 + 복붙 실행 명령을 보고.
