---
name: visual-confidence
description: AI 눈 판정을 같은 스크린샷에 대해 독립 블라인드로 N번 반복해, 판정의 일치율(안정성)·다수결·흔들림(flaky)을 측정한다. AI 판정은 비결정적이라 한 번 돌리면 운에 휘둘리므로, 여러 번 돌려 "이 판정이 안정적인가 / 사각지대가 일관되게 못 잡히는가"를 확인하는 용도. 사용자가 "판정 반복", "N번 돌려봐", "안정성 측정", "흔들리는 판정 찾아줘", "사각지대 일관성 확인", "visual-confidence" 등을 말할 때 사용한다. demo-app 에서 동작한다.
model: sonnet
effort: low
---

# visual-confidence — AI 판정 안정성 측정 (N회 반복 + 다수결)

AI 눈 판정은 **유일한 비결정 요소**다(변형·정답·코드측정·채점은 모두 고정). 한 번만 돌리면
"운 좋게 맞췄나 / 나쁘게 틀렸나"를 구분 못 한다. 이 스킬은 같은 스샷에 **독립 블라인드 판정을 N번**
돌려서 **일치율·다수결·flaky** 를 뽑는다.

→ 비결정성·블라인드 원칙의 배경(rubric 6장·3장)은 이 스킬 호출 시 훅(inject-context)이 자동 주입한다 — 파일을 다시 Read 하지 않는다. 이 스킬은 그걸 *반복·집계*하는 도구다.

역할 경계:
- 이 스킬은 **이미 촬영된 스샷**(`screenshots/<키>/*.png`)에 대한 **AI 판정만 반복**한다. 촬영·갤러리 빌드는 하지 않는다(필요하면 `visual-check` 가 먼저 만들어 둔다).
- 판정은 반드시 **독립·블라인드**: 각 판정 에이전트는 *정답(expected)도, 다른 판정 결과도* 모른 채 스샷만 보고 답한다.

## 절차

### 1. 대상과 N 정하기
- 컴포넌트 키 기본값: `card`. 사용자가 지정했으면 그 키.
- 범위/N — 사용자가 명시 안 했으면 **AskUserQuestion** 으로 고른다:
  - `특정 변형 1개 집중 (N=5)` — 예: 사각지대 `tone-c` 를 5번 못 박기. 발표용.
  - `전체 변형 (N=3)` — 흔들리는(flaky) 판정을 훑어 찾기.
- 전제 확인:
```bash
cd demo-app && ls screenshots/<키>/measurements.json screenshots/<키>/*.png >/dev/null 2>&1 \
  && echo OK || echo "촬영 먼저 필요 — visual-check 로 캡처하세요"
```
스샷이 없으면 여기서 멈추고 `visual-check` 로 먼저 촬영하도록 안내한다.

### 2. 대상 변형 목록 뽑기
```bash
cd demo-app && node -e "const m=require('./screenshots/<키>/measurements.json'); console.log(m.map(x=>x.id).join(' '))"
```
- "특정 변형" 모드면 그 id 하나만. "전체" 모드면 전부.

### 3. 변형마다 독립 블라인드 판정 N회 (`visual-judge` 서브에이전트, 병렬)
각 변형 × N 번, **공유 서브에이전트 `visual-judge`** 를 띄운다 (Agent 도구, `subagent_type: visual-judge`).
- 한 호출당 **스샷 1장 경로만** 넘긴다. 예: `demo-app/screenshots/<키>/<id>.png 를 판정해줘.`
- **정답(expected)·다른 판정 결과는 절대 넘기지 않는다** — visual-judge 가 블라인드로 판정한다.
- N개를 **한 메시지에서 동시에** 띄워 병렬 실행한다.
- visual-judge 는 두 줄(근거 + 레벨)로 답하므로, **마지막 줄의 단어(ok/warn/error)** 를 레벨로 모은다.

> 참고: 이 단일 판정 일꾼(`visual-judge`)은 `visual-check` 도 공유해서 쓴다. 판정 기준이 한 곳에 모여 일관된다.

### 4. 집계 — 일치율·다수결·flaky
변형별로 N개 레벨을 세어:
- **분포**: 예 `{ok:5}` 또는 `{ok:2, warn:1}`
- **다수결(majority)**: 최다 득표 레벨
- **일치율(agreement)**: 최다 득표수 / N
- **flaky**: 일치율 < 1.0 (만장일치 아님) 이면 흔들림

`screenshots/<키>/confidence.json` 에 기록:
```json
{ "<id>": { "n": 5, "votes": {"ok":5}, "majority": "ok", "agreement": 1.0, "flaky": false } }
```

### 5. 다수결을 정식 판정으로 반영 (선택)
`screenshots/<키>/ai-notes.json` 의 각 변형 `level` 을 **다수결 값**으로 갱신하고, `note` 끝에 안정성 한 줄을 덧붙인다 — 예: `… (안정성: 5/5 일치)`. 기존 설명 문장은 지우지 말 것.
→ 그 뒤 갤러리를 다시 빌드하면 채점이 다수결 기준으로 반영된다: `cd demo-app && npm run gallery -- <키>`

### 6. 표로 보고
```
🔁 <키> AI 판정 안정성 (N=<n>, 변형 <개수>개)

| 변형 | 다수결 | 분포 | 일치율 | 흔들림 |
|------|--------|------|--------|--------|
| tone-c | 정상 | 정상×5 | 100% | 안정 |
| disabled | 주의 | 주의×2·정상×1 | 67% | ⚠️ flaky |
```
- **flaky 칸을 강조**한다 — 거기가 "AI가 흔들리는 판정"이라 신뢰도가 낮은 지점이다.
- 사각지대(예: `tone-c`)가 **N번 모두 같은 오답**이면 "일관된 사각지대"로, 운이 아님을 명시한다.
- 끝에 한 줄 요약: 평균 일치율, flaky 개수.
