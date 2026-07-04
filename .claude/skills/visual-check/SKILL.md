---
name: visual-check
description: 공통 컴포넌트의 여러 변형을 한 갤러리로 모아, 코드 사실 측정과 AI 눈의 동적 판정을 나란히 검증한다. "갤러리 만들어줘", "변형들 확인해줘", "카드 안 깨졌는지 봐줘", "시각 검증", "검사해줘" 같은 요청에 사용한다. 각 변형의 단일 판정은 공유 서브에이전트 visual-judge 가 한다. demo-app 에서 동작한다.
model: sonnet
effort: medium
---

# visual-check — 공통 컴포넌트 변형 갤러리 검증 (오케스트레이션 스킬)

여러 곳에서 쓰이는 **공통 컴포넌트**의 변형들을 한 화면에 모아 촬영하고, **코드 사실 측정**과
**AI 눈 판정**을 나란히 두어 깨진 변형을 잡아낸다. (OS.md 1~6단계)

역할 경계:
- 이 스킬은 **오케스트레이션**(촬영→측정→판정 수집→갤러리→보고)을 한다.
- **각 변형의 단일 판정은 공유 서브에이전트 `visual-judge`** 가 한다 (스샷 1장 → ok/warn/error). 같은 일꾼을 `visual-confidence` 도 쓴다(재사용).
- 제품 코드는 수정하지 않는다(판정 기록 `ai-notes.json` 만 작성).

대상 프로젝트: `demo-app`. 등록처 `src/gallery/registry.ts` · 변형 `src/gallery/variants/<키>.ts` · 화면 `/gallery?c=<키>`.

## 핵심 원칙 (역할 분담)
→ **판정 공통어(절대/상대·블라인드·코드↔AI 역할분담·사각지대)는 `.claude/visual-rubric.md` 가 정본이며, 이 스킬 호출 시 훅(inject-context)이 자동 주입한다. 주입된 내용을 따르고 파일을 다시 Read 하지 않는다**(이중 로딩 방지). 여기서 다시 설명하지 않는다.
- 이 스킬에 해당하는 부분: **코드는 사실만**(overflow 잘림만 단정, 나머진 수치) / **AI 눈(visual-judge)이 판정**(ok/warn/error) / **둘이 어긋나는 칸이 가장 중요한 신호** — 갤러리에서 초록 테두리.

## 절차

### 0. 대상 확정
대상 키 `<T>` 를 정한다. 보통 이미 정해진 채로 온다(사용자 지정, 또는 `visual-list` 에서 선택).
- 대상이 없으면 `visual-list` 로 목록을 보고 고르게 안내. 없는 키면 `visual-add` 로 등록 안내.

### 0-B. dev 서버 확인
무대 URL 은 하드코딩하지 않는다 — config seam(CLI)에서 얻는다:
```bash
URL=$(node "$CLAUDE_PROJECT_DIR/.claude/scripts/visual-config.mjs" <T>)
curl -sf "$URL" >/dev/null && echo UP || echo DOWN
```
- **UP 이면** 사용자가 이미 띄운 서버다 — 그대로 쓰고 **마커를 남기지 않는다**(남의 서버는 SessionEnd 훅이 안 건드림).
- **DOWN 이면** 직접 띄우되, **이 OS가 띄웠다는 PID 마커를 남긴다**(세션 끝에 훅이 이것만 정리):
```bash
cd demo-app && npm run dev >/tmp/visual-dev.log 2>&1 &
echo $! > "$CLAUDE_PROJECT_DIR/.claude/.visual-dev-server.pid"
```
그 뒤 200 될 때까지 짧게 대기(`curl` 재시도).

### 1. 변형 촬영 + 코드 측정
```bash
cd demo-app && npm run capture -- <T>
```
- 산출물: `screenshots/<T>/<id>.png`, `screenshots/<T>/measurements.json` (overflow 만 코드 깨짐).

### 2. 변형마다 AI 판정 (`visual-judge` 서브에이전트, 병렬)
`measurements.json` 에서 변형 id 목록을 뽑고, **변형마다 `visual-judge` 를 1번씩** 띄운다 (Agent 도구, `subagent_type: visual-judge`, 한 메시지에서 병렬).
- 각 호출에 **스샷 경로만** 넘긴다: `demo-app/screenshots/<T>/<id>.png 를 판정해줘.`
- **정답(expected)·코드 수치·다른 결과는 넘기지 않는다** — 블라인드 판정.
- visual-judge 가 두 줄(근거 + 레벨)로 답하면, **마지막 줄 단어**를 level, 윗줄을 note 로 쓴다.

### 3. AI 판단 기록
- `screenshots/<T>/ai-notes.json` 에 `{ "<id>": { "level": "ok|warn|error", "note": "<visual-judge 근거>" } }` 로 모아 적는다.

### 4. 갤러리 생성 (아직 열지 않음)
```bash
cd demo-app && npm run gallery -- <T>
```
- `screenshots/<T>/index.html` 생성: 스샷 · 코드 사실 · AI 판정 · 정답 대비 채점.

### 5. 보고 (점수 먼저, 채팅으로)
갤러리를 **열기 전에** 결과를 먼저 보고한다.
```
🔍 <T> 변형 갤러리 검증 결과   (총 N개)
AI 자체 분별 점수: X점 (정답 m/N) · 코드 점수: Y점 (overflow만)

🟢(강점) 코드는 수치만인데 AI가 잡은 칸 · 🔴(사각지대) AI가 정답 놓친 칸 · ✅ 일치
해석: (코드↔AI 어긋난 칸 = 가장 중요한 신호 / 사람이 확인할 칸)
```

### 6. 갤러리 열기 묻기 (마지막)
보고 뒤 **"갤러리를 열까요?" 를 물어보고**, 승인하면 연다:
```bash
cd demo-app && npm run gallery -- <T> --open
```
(열기는 외부 동작이므로 묻지 않고 임의로 열지 않는다.)

## 메모
- AI 눈은 미세 색차·1px 을 못 본다 → 그건 코드 수치를 신뢰. 코드는 맥락을 모른다 → 그건 AI가 판정.
- 더 깊은 안정성(같은 판정 N회 반복·다수결)은 `visual-confidence` 스킬이 같은 `visual-judge` 로 한다.
- (확장) OS.md 7단계: git HEAD 자동 before/after, Figma 정답지 비교.
