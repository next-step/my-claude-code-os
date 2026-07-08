# CONTEXT.md — 변경 이력 / 의도·컨텍스트 로그

이 파일은 **클로드 OS의 동작 방식·의도·메모리가 바뀔 때마다** 날짜와 함께 적재하는 변경 로그다.
새 변경은 **맨 위에** 날짜 헤더로 추가한다(최신이 위). 각 항목은 "무엇을 / 왜 / 어떻게(파일)"를 남긴다.

---

## 2026-07-09

### 단계별 모델/추론강도 정책 도입 — 전부 Opus, effort만 차등
- **무엇을**: paper-os 각 단계 에이전트에 모델·추론강도를 단계별로 배정. 전 단계 Opus 고정, effort만 차등(analyze/code/run=high, triage/detail/design/gate=medium, render=low).
- **왜**: 사고량이 큰 코드 분석·실행에 더 높은 추론강도를 주고, 조립·렌더처럼 가벼운 단계는 낮춰 품질과 비용을 함께 통제. 반복 의도는 프롬프트가 아니라 워크플로/스킬 기본값에 고정하는 정석대로 처리.
- **설계 메모**: 실질 차등은 워크플로의 `effort`에서 일어난다(대화형 agent 프론트매터엔 표준 effort 필드가 없어 model만 지정). 재튜닝은 `POLICY` 맵 한 곳만 고치면 됨.
- **어떻게(파일)**:
  - `.claude/workflows/paper-os.js` — 중앙 `POLICY` 맵 + 헬퍼 `M(stage)` 추가, 13개 `agent()` 호출 전부에 `{model,effort}` 주입.
  - `.claude/agents/*.md`(9개) — 프론트매터에 `model: opus` 명시(대화형 경로 고정).

### feedback 스킬 단계별 분리 — 단일 스킬 → 핵심 5개 전용 스킬
- **무엇을**: 6단계를 한 파일로 검증하던 `feedback` 스킬을 단계별 전용 스킬로 분리(`feedback-analysis/detail/code/run/html`). 각 스킬은 해당 단계 체크리스트만 담은 자급식 파일.
- **왜**: 단계마다 채점 기준이 달라 한 파일에 섞이면 초점이 흐려짐. 워크플로 게이트 대상이 정확히 이 5개라 1:1로 매핑됨. design은 애초에 게이트를 안 타 기존 `feedback`(design/폴백)으로 유지.
- **어떻게(파일)**:
  - `.claude/skills/feedback-analysis|detail|code|run|html/SKILL.md` — 신설(단계별 체크리스트·출력형식·규칙). run은 "원본을 사용자가 실행" 모델에 맞춰 실제 실행 로그 요구 제거.
  - `.claude/skills/feedback/SKILL.md` — design 검증·폴백 전용임을 상단에 명시, 전용 5개로 안내.
  - `.claude/workflows/paper-os.js` — `gated()`가 단계에 맞는 `feedback-<stage>` 스킬을 읽도록 수정(없는 단계만 `feedback` 폴백).

### 컨텍스트 예산 시각화 — HTML 대시보드 신설
- **무엇을**: `PAPER-OS-CONTEXT-BUDGET.md`(측정·최적화 기록)를 한눈에 보는 자급식 HTML 대시보드로 도식화. KPI(−53%)·파일별/단계별 막대·두 허브 반복 로딩 흐름도·OPT 카드·전후 비교표.
- **왜**: 수치·병목·최적화 효과를 텍스트보다 시각적으로 파악하기 쉽게. 프로젝트 규칙(모든 산출물은 프로젝트 안)대로 외부 호스팅 아닌 프로젝트 내 파일로 생성.
- **어떻게(파일)**: `PAPER-OS-CONTEXT-BUDGET.html` — 신설(인라인 CSS, 라이트/다크 테마 대응, 반응형, 외부 의존 없음).

### /ab-test 스킬 신설 + 워크플로 A/B 실행 인프라
- **무엇을**: 같은 논문을 두 번 돌려 **CONTEXT.md 배경지식 주입(A) vs 미주입(B)** 를 비교하는 `/ab-test` 스킬 추가. 단일 변수 원칙·정량(크기/토큰/게이트)·블라인드 정성 채점·리포트 절차를 규정.
- **왜**: "CONTEXT.md를 파이프라인에 배경지식으로 주면 산출물이 좋아지는가"를 프롬프트 감이 아니라 실측으로 검증하기 위함.
- **어떻게(파일)**:
  - `.claude/skills/ab-test/SKILL.md` — 신설.
  - `.claude/workflows/paper-os.js` — A/B 노브 2개(`context`=배경지식 파일 주입, `tag`=출력 폴더 분리 `__A`/`__B`) 추가. `INTENT`에 `CTX` 프리앰블 결합, `FOLDER` 기준 경로 정합화.

### 워크플로 버그 2건 수정 (A/B 실행 중 발견)
- **args 문자열 파싱**: 이 환경에서 `args`가 JSON 문자열로 전달돼 `isObj`가 false→`tag`/`context` 무시로 두 팔이 같은 폴더를 덮어썼다. 최상단에 "객체형 문자열이면 JSON.parse" 정규화 추가(`ARGS`), 순수 URL 문자열은 그대로. `.claude/workflows/paper-os.js`.
- **코드 분할경로 runcard 누락**: 코드 다중 에이전트 경로의 merge가 `04_runcard.md`를 발행하지 않아 code-run 다운스트림 최적화(OPT-1)가 깨졌다. merge 프롬프트가 단일 경로와 동일하게 runcard를 반드시 발행하도록 수정. `.claude/workflows/paper-os.js`.

### CRLF 대응 — `.gitattributes` 신설
- **무엇을**: `.claude/**`·`*.js`·`*.json`·`*.css`에 `eol=lf` 강제.
- **왜**: `core.autocrlf=true`가 체크아웃 시 워크플로 파일을 CRLF로 바꿔, Workflow 권한 다이얼로그가 CR(0x0d)을 "숨은 제어문자"로 차단 → 실행 자체가 막혔다. LF 고정으로 재발 방지.

### A/B 결과 (liveedit_2606.26740) — CONTEXT.md 주입은 도움 안 됨(소폭 해로움)
- **무엇을**: 블라인드 채점에서 미주입(B)이 4단계 중 3개(analysis·detail·run) 우세, 주입(A)은 산출물 +27%·파이프라인 토큰 +30%만 늘림. 공정 비교 단계에서 CONTEXT는 밀도↓·헤지↑·수치모순 1건을 유입.
- **교란요인(정직)**: Triage엔 CONTEXT 미주입인데도 복잡도 판정이 A=high/B=medium으로 갈림 → 코드 크기 차이 상당수는 CONTEXT 효과가 아니라 실행 간 무작위성. 단일 표본 한계.
- **어떻게(파일)**: `output/liveedit_2606.26740__{A,B}/`(두 팔 산출물), `output/liveedit_2606.26740__ab/AB_REPORT.md`(정량·블라인드 채점·판정·교란요인·재현).
- **권고**: CONTEXT 전체 통째 주입 금지 → 필요한 규약만 좁게(이미 `00_intent.md`가 담당). 다른 논문 1~2편으로 반복해 결론 확정.

---

## 2026-07-02

### paper-os 단계별 컨텍스트량 측정·최적화 (약 −53%)
- **무엇을**: 파이프라인 각 단계가 컨텍스트에 싣는 양(에이전트가 Read하는 SKILL.md+산출물 합)을 실측해 기준선을 만들고, 병목(허브 문서 반복 로딩)을 4개 최적화로 줄였다. 실행 1회 기준 398,269자 → 187,461자(약 −53%, ≈159k→75k 토큰 추정).
- **왜**: `03_detail.md`·`04_code.md`(각 ~49k)가 자신의 게이트·Run·Render에서 2~3회 재로딩되고, `report.html`(69k)이 게이트에서 통째로 읽혀 낭비가 곱으로 커졌다. 반복 의도는 프롬프트가 아니라 스킬/워크플로 기본값을 고쳐 고정하는 것이 정석.
- **어떻게(최적화)**:
  - OPT-1 Run 인터페이스 축소 — `code` 스킬이 소형 `04_runcard.md`(≤~1,800자, 레포/커밋/진입점/의존성/최소 실행 경로)를 별도 발행하고 Run은 이 카드만 읽음(폴백: 04_code). Run 57,060→9,323.
  - OPT-2 허브 문서 밀도화 — `detail`·`code`에 ~24,000자(약 300줄) 분량 예산 명시(골격 유지, 반복·군더더기·코드 전체 붙여넣기 금지).
  - OPT-3 Render 게이트 경계검증 — `feedback`이 report.html을 통독하지 않고 골격·TOC·필수 헤딩·KaTeX/badge 유무만 구조 검증(본문 정확도는 md 게이트에서 이미 확인). Gate:html 71,276→~10,239.
- **어떻게(파일)**:
  - `.claude/skills/code/SKILL.md` — 절차6·`04_runcard.md` 스키마·분량 예산·보고 경로 추가.
  - `.claude/skills/detail/SKILL.md` — 분량 예산 추가.
  - `.claude/skills/feedback/SKILL.md` — 큰 렌더 산출물 경계검증 규칙 추가.
  - `.claude/workflows/paper-os.js` — Run 단계가 `04_runcard.md` 우선 읽도록 프롬프트 수정.
  - `PAPER-OS-CONTEXT-BUDGET.md` — 신설: 측정 모델·기준선 표·병목 진단·최적화 근거·전후 비교·검증(재실행)법 기록.
- **수치 성격**: Before는 현재 파일 실측(정확), After는 새 예산/인터페이스 기준 예상치 → 재실행 시 생성되는 작은 산출물로 실측 확정 예정.

### PAPER-AI-PIPELINE.md 문서 정합화
- **무엇을**: 안내 문서를 실제 구조와 일치시킴. interview 단계를 파이프라인 맨 앞에 추가(스킬 7→8, 에이전트 8→9), code-run 설명을 "실제 실행"→"원본 레포·사용자 터미널 가이드"로 수정, 산출물 디렉토리를 `output/<slug>/` per-paper 구조 + `00_intent.md`로 갱신, 데이터 흐름도에 interview→00_intent 추가.
- **왜**: interview 신설·code-run 철학 전환·per-slug 폴더화로 문서가 실제와 어긋나 있었음(신규 사용자 오해 방지).
- **어떻게(파일)**: `PAPER-AI-PIPELINE.md` 전면 갱신.

### interview 스킬 신설 — paper-os 앞단 의도 확정 게이트
- **무엇을**: 논문 파이프라인 전용 `/interview` 스킬을 추가. 사용자 요청에서 **① 가정 추출 → ② 빈틈 탐지 → ③ 대안 제시(A/B)** 로 의도를 확정하고 `output/<slug>/00_intent.md` 로 저장한다. `paper-os`의 모든 단계가 이 파일을 스킬 기본값보다 우선 읽는다.
- **왜**: code-run이 의도(원본/재구현·실행 주체·실행 위치)를 앞에서 안 물어 어긋난 사고를 **시작 시점에** 잡기 위함. 인터뷰 결과를 대화가 아니라 파일로 남겨 의도가 증발하지 않게 함. 스코프는 요청대로 **paper-os 전용**.
- **설계 메모**: 인터뷰는 대화형(AskUserQuestion)이라 백그라운드 워크플로우 안에서 못 돌린다 → paper-os **실행 전** 메인 대화에서 단독 실행하고, 워크플로우는 그 산출 파일만 소비.
- **어떻게(파일)**:
  - `.claude/skills/interview/SKILL.md` — 신설(세 동작 루프·정지조건 2라운드·숨은변수 체크리스트·00_intent.md 출력 스키마).
  - `.claude/agents/interview-agent.md` — 신설(대화형, AskUserQuestion 보유).
  - `.claude/workflows/paper-os.js` — `Intent` phase 추가, `INTENT` 프리앰블을 analyzer/detail/code/code-run/html 프롬프트에 주입, Triage가 기존 00_intent.md 폴더 slug 재사용. **부수 수정**: code-run 단계 프롬프트가 옛 "토이 데모 자동실행"으로 남아 있던 것을 새 스킬(원본·사용자 실행)에 맞게 정정.

### code-run 스킬의 실행 철학 전환 — "재구현 자동실행" → "원본 레포, 사용자 터미널 실행"
- **무엇을**: `/code-run`(코드실행) 단계의 기본 동작을 바꿨다.
  - 이전: 04_code.md 문서 동작을 **재구현한 토이 데모**를 만들고 **클로드가 자기 샌드박스에서 자동 실행**해 로그를 캡처.
  - 이후: **원본 공식 레포**를 대상으로, 클로드는 **직접 실행하지 않고** 사용자가 자기 터미널에 붙여넣어 돌릴 **복붙용 명령 블록 + 관찰 가이드**만 발행. 실행·관찰 주체는 사용자. 재구현 토이는 원본 실행이 구조적으로 불가할 때만 fallback(원본 아님을 명시).
- **왜**: 사용자의 실제 의도는 "실제 데모가 여기(클로드)가 아니라 **따로 내 터미널에서** 돌아가는 것"이었는데, 기존 스킬 명세가 이와 다른 기본값(토이·자동실행·캡처)을 갖고 있어 산출물이 의도와 어긋났다. 반복되는 의도는 프롬프트로 매번 반복하지 않고 **스킬 기본값 자체를 고쳐 고정**하는 것이 클로드 OS의 정석.
- **어떻게(파일)**:
  - `.claude/skills/code-run/SKILL.md` — 원본 우선/사용자 실행 주체/복붙 명령 블록/미실행 시 "아직 미실행" 표기 규칙으로 전면 개정.
  - `.claude/agents/code-run-agent.md` — 위 철학에 맞춰 개정(Bash 자동 실행 금지 기본값).
  - `output/joyaivl_2606.14777/05_run.md` — 원본 레포(JD `JoyAI-VL-Interaction`, 커밋 9d07596) 실행 가이드로 재작성. 기존 토이 데모는 GPU 없을 때 fallback으로 강등.
  - `output/liveedit_2606.26740/05_run.md` — 원본 레포(`cp-cp/LiveEdit`) 추론 실행 가이드로 재작성.

### 협업 원칙 메모리 추가
- **무엇을**: "반복되는 의도는 스킬 기본값으로 고정한다"는 협업 원칙을 메모리로 저장.
- **왜**: 같은 의도 불일치가 재발하지 않도록, 일회성 프롬프트가 아니라 명세 수정으로 대응하는 습관을 고정.
- **어떻게(파일)**: `memory/intent-into-skill-defaults.md` (+ MEMORY.md 인덱스 한 줄).

### CONTEXT.md 도입
- **무엇을**: 변경 이력/의도 로그 파일(이 파일)을 프로젝트 루트에 신설. 앞으로 동작·의도·메모리 변경 시 날짜와 함께 여기에 적재.
- **왜**: "무엇이 왜 바뀌었는지"를 시간순으로 추적 가능하게.
