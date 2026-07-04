---
name: visual-regress
description: 코드 변경 전후(before/after)로 공통 컴포넌트 변형들을 다시 촬영해 "의도한 변경 말고 딸려서 바뀐 게 있나"를 잡는 시각 회귀 검증. 사용자가 "회귀 검사", "바뀐 거 있나 봐줘", "before after 비교", "visual-regress", "내 변경이 딴 데 영향 줬나" 등을 말할 때 사용한다. demo-app 에서 동작한다.
model: sonnet
effort: medium
---

# visual-regress — 코드 변경의 시각 회귀 검증 (오케스트레이션 스킬)

**전제:** 누군가 코드를 바꿨다. 그 변경이 공통 컴포넌트의 *겉모습*을 **의도 외로** 건드렸는지(딸려서 바뀜)
before/after 를 다시 촬영해 잡는다. (OS.md 7단계)

`visual-check` 와의 차이:
- `visual-check`(1장·절대) = "이거 그 자체로 깨졌나?" — **첫 등록·기준선 만들 때.**
- `visual-regress`(2장·상대) = "기준선 대비 의도 외로 바뀌었나?" — **그 뒤로 코드 바꿀 때마다.**
- 둘은 서로의 사각지대를 메운다 → 변경 후엔 보통 둘 다 돌린다(아래 메모).

## 역할 분담 (이 OS의 핵심 철학)
→ **판정 공통어(절대/상대·블라인드·코드↔AI 역할분담·사각지대)는 `.claude/visual-rubric.md` 가 정본이며, 이 스킬 호출 시 훅(inject-context)이 자동 주입한다. 주입된 내용을 따르고 파일을 다시 Read 하지 않는다**(이중 로딩 방지).
- 이 스킬에 해당하는 부분: **픽셀 차이(`regress-diff.mjs`) = WHAT**(무엇이 바뀌었나, 판정 안 함) / **AI 눈(`visual-comparator`) = MATTER**(그 변화가 의도 외냐). 픽셀이 *바뀐 변형을 추려주면* AI 는 **바뀐 것만** 보고 same/expected/unexpected 를 가린다(비용↓·노이즈↓).

대상 프로젝트: `demo-app`. 기준선 `screenshots/<T>/baseline/` · 현재 `screenshots/<T>/*.png`.

## 절차

### 0. 대상 + 의도 확정
- 대상 키 `<T>` (기본 `card`).
- **사용자가 이번에 의도한 변경**을 한 줄로 받아둔다(예: "제목을 굵게"). 안 주면 물어보거나, 없이 진행(그러면 *모든* 의미 있는 변화를 unexpected 로 본다).
- dev 서버 확인 (무대 URL 은 config seam CLI 에서 — 하드코딩 금지):
```bash
URL=$(node "$CLAUDE_PROJECT_DIR/.claude/scripts/visual-config.mjs" <T>)
curl -sf "$URL" >/dev/null && echo UP || echo DOWN
```
  - **UP** = 사용자가 띄운 서버 → 그대로 쓰고 **마커 안 남김**.
  - **DOWN** = 직접 띄우고 **PID 마커 기록**(세션 끝 SessionEnd 훅이 이것만 정리):
```bash
cd demo-app && npm run dev >/tmp/visual-dev.log 2>&1 &
echo $! > "$CLAUDE_PROJECT_DIR/.claude/.visual-dev-server.pid"
```

### 1. 기준선(before) 있는지 확인
```bash
cd demo-app && ls screenshots/<T>/baseline/*.png >/dev/null 2>&1 && echo HAVE || echo NONE
```
- **NONE 이면** 회귀를 잴 before 가 없다. 사용자에게 알리고 → **지금 상태를 기준선으로 박는다**(단, 기준선이 깨진 채 박히면 회귀가 영원히 통과되므로, 먼저 `visual-check` 로 기준선이 멀쩡한지 검증할 것을 권한다):
```bash
cd demo-app && npm run capture -- <T> && npm run baseline -- <T>
```
  여기서 멈추고 "기준선을 박았다. 이제 코드를 바꾼 뒤 다시 불러달라"고 안내한다.
- **HAVE 이면** 다음으로.

### 2. 현재(after) 촬영
```bash
cd demo-app && npm run capture -- <T>
```

### 3. 픽셀 비교 — 바뀐 변형 추리기 (WHAT)
```bash
cd demo-app && npm run regress -- <T>
```
- 출력 JSON 의 `changed` 가 **픽셀상 바뀐 변형 목록**(+`diffPercent`/크기변경). `screenshots/<T>/regress.json` 에도 저장된다.
- `changedCount === 0` 이면 → **회귀 없음.** AI 판정 생략하고 "변화 없음"으로 보고하고 끝낸다.

### 4. 바뀐 변형만 AI 비교 판정 (`visual-comparator` 서브에이전트, 병렬)
`changed` 의 각 id 에 대해 **`visual-comparator` 를 1번씩** 띄운다 (Agent 도구, `subagent_type: visual-comparator`, 한 메시지에서 병렬).
- 각 호출에 넘기는 것:
  - before: `demo-app/screenshots/<T>/baseline/<id>.png`
  - after: `demo-app/screenshots/<T>/<id>.png`
  - (있으면) diff: `demo-app/screenshots/<T>/diff/<id>.png`
  - **이번에 의도한 변경 한 줄** (0번에서 받은 것). 없으면 "의도 안 알려짐".
- **정답(expected)·픽셀 수치·다른 판정 결과는 넘기지 않는다** — comparator 가 블라인드로 두 그림만 비교한다.
- comparator 가 두 줄(근거 + `same|expected|unexpected`)로 답하면, **마지막 줄 단어**를 verdict, 윗줄을 note 로 쓴다.
- 크기 변경(`dimensionMismatch`)이라 diff 이미지가 없어도, before/after 두 장은 넘겨 판정시킨다.
- **예외 — `newVariant: true`(baseline 이후 추가된 변형):** before 가 없어 비교 판정이 불가능하다. comparator 에 보내지 말고 **`visual-judge`(1장 절대 판정)** 에 보낸다. verdict 대신 judge 의 level(ok/warn/error)을 note 와 함께 머지하고, 보고에 "신규 변형이라 회귀가 아닌 절대 판정"임을 명시한다.

> 참고: `visual-comparator` 는 `visual-judge` 의 짝(2장 비교 버전)이며, 앞으로 blindspot/figma 도 공유할 2번째 "공유 눈"이다.

### 5. 판정을 regress.json 에 머지
`screenshots/<T>/regress.json` 의 각 `results[id]` 에 `verdict`(same|expected|unexpected) 와 `note` 를 적어 넣는다(드릴다운 갤러리가 읽는다).

### 6. 보고 — 마크다운 표 (1순위, 대화창)
바뀐 변형을 표로 찍는다. **이게 기본 출력이다.**
```
🔬 <T> 시각 회귀 (의도: "<이번 의도>")
기준선 대비 바뀐 변형 K / 전체 N · 의도 외 변경(🔴) M개

| 변형 | 픽셀차이 | AI 판정 | 근거 |
|------|---------|---------|------|
| badge-card | 1.8% | 🔴 의도 외 변경 | 배지 배경색이 옅어지고 모서리가 각짐 |
| title-card | 0.6% | 🟢 의도된 변경 | 제목만 굵어짐(의도와 일치) |
```
- `unexpected` = 🔴(회귀 의심·사람이 볼 곳), `expected` = 🟢, `same` = ⚪.
- 안 바뀐 변형(픽셀상 동일)은 표에서 생략하고 "그 외 N−K개 변화 없음" 한 줄로.
- 한 줄 결론: 🔴 가 0이면 "의도 외 변경 없음 — 안전", 있으면 "🔴 M개 확인 필요".

### 7. 드릴다운 갤러리 — 🔴 있을 때만 열기 묻기
의도 외 변경(🔴)이 **하나라도 있으면** before|after|diff 나란히 보는 HTML 을 제안한다:
```bash
cd demo-app && npm run regress-gallery -- <T>        # 빌드
cd demo-app && npm run regress-gallery -- <T> --open # 승인 시 열기
```
- 🔴 가 없으면 갤러리는 굳이 열지 않는다(표로 충분).
- 열기는 외부 동작이므로 묻지 않고 임의로 열지 않는다.

### 8. (사용자가 "이건 의도된 새 정상"이라 하면) 기준선 갱신
승인 시 현재를 새 before 로 박는다:
```bash
cd demo-app && npm run baseline -- <T>
```

## 메모
- **comparator 의 사각지대:** before/after 둘 다에 똑같이 있던 *원래부터 깨진 것*은 "변화 없음=통과"로 못 잡는다. 그래서 **기준선을 박을 때 `visual-check`(절대 판정)로 검증**해야 한다. 변경 후 검증은 regress + (의심되면) check 를 함께.
- **픽셀 differ 의 약점은 AI 가, AI 의 약점(1px·미세색·고립 균일)은 픽셀이** 메운다 — 그래서 둘을 같이 쓴다.
- 노이즈(안티앨리어싱)는 `regress-diff.mjs` 가 `includeAA:false` + 0.02% 임계로 걸러 AI 호출을 아낀다.
