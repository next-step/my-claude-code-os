# 카탈로그 속성 추출 OS

카탈로그에서 **성별·색상·소재처럼 여러 속성의 데이터**를 만들 때, 정책과 골든셋의 차이·공백을
찾고 사람의 결정을 다음 실행에 남기는 시스템. 실행기와 보고서는 공통으로 쓰고 속성별 규칙만
프로필·어댑터로 교체한다.

성공 기준은 정확도가 아니다. **부족한 GT는 건 단위로, 부족한 정책은 군집 단위로, 근거와 함께
지목하는 것**이 산출물이다. 판단이 갈리면 최종 근거는 [engine/goal.md](.claude/os/engine/goal.md)다.

NextStep "나만의 클로드 코드 OS 만들기" 미션 저장소다. 주차별 요구사항을 구현해 본인 GitHub
아이디 브랜치로 PR을 올리고, 피드백을 반영해 merge되면 다음 주차로 넘어간다.
리뷰 절차는 [온라인 코드 리뷰 과정](https://github.com/next-step/nextstep-docs/tree/master/codereview)을 따른다.

## 작업 규칙

1. 클로드 OS 관련 파일(.claude 아래 md, 스크립트, 프로필)은 반드시 이 프로젝트 안에 만든다.
   홈 디렉터리의 .claude에 두지 않는다.
2. 실습 중이다. 무엇을 했는지만이 아니라 왜 그렇게 나눴는지, 다른 선택지는 무엇이었는지 설명을 붙인다.
   사용자가 AI와의 협업 방식을 배우는 것이 목적이다.
3. 구조는 세 층이다. `engine/`과 `review/`는 공통이고 어떤 속성이 있는지 모른다.
   `attributes/<id>/`는 속성 팩이고 profile.json이 유일한 플러그다. `runs/<id>/`는 산출물이라 지워도 된다.
   엔진에 성별, 가방 같은 도메인 규칙을 넣지 않는다.
4. **판례는 자산이다.** 정책의 각 규칙에 이름이 있고(`P1_DIRECT_TEXT` 같은 대문자 토큰),
   판례는 `rule:`·`signals:`로 **자기가 어디에 걸리는지 스스로 선언한다.** 판례 ID를 코드에
   적지 않는다 — 적으면 판례를 새로 써도 심판이 모르고, 닫아도 코드를 고쳐야 한다.
   판례는 `applies:`로 종류를 밝힌다. `EVIDENCE`(무엇이 근거인가)는 규칙 브리프에 실려
   다음 판독기에게 가고, `RULING`(무엇으로 정할 것인가)은 가지 않는다 — 판정 규칙을 읽은
   판독기는 「무엇이 보이는가」 대신 「무엇이 답인가」를 먼저 정한다.
   손으로 쓴 정책과 판례는 `attributes/<id>/policy/`에만 둔다. `runs/` 안의 정책은 가져온 읽기 전용 스냅샷이다.
   골든셋도 같다 — 정답은 `.claude/gt/<id>/gt.jsonl` **한 곳에만** 있다. 계보가 여럿이면
   `build_gt.py`가 순위로 합치고 진 라벨을 이력으로 남긴다. 정답이 두 파일에 있으면 화면마다
   다른 답을 그린다. 계약은 [gt-layer.md](.claude/os/engine/contracts/gt-layer.md)에 있다.
5. IMPORTANT: 사람 판정 원장 `runs/<id>/review/decisions.json`에는 사용자가 명시적으로 확정한 결정만
   기록한다. AI 추천을 자동으로 기록하지 않는다.
   그 원장이 **정본**이고, 거기서 `build_gt_decisions.py`가 네 파일을 파생한다 —
   `corrections.jsonl`(고쳐라) · `confirmations.jsonl`(맞다) · `pending-precedent.jsonl`(판례 대기) ·
   `precedent-log.json`(판례별 사례집). 넷 다 `.claude/gt/<id>/from-decisions/`에 있고 지워도 다시 만들어진다.
   **유지도 결정이다** — 라벨을 안 바꾸지만 `humanConfirmed`로 남아야 다음 사이클이 같은 건을
   다시 묻지 않는다.
   GT를 건드리는 판정은 **어느 정책 경계 위에 섰는지**를 함께 남긴다. 판례 하나를 가리키거나,
   「걸리는 판례가 없다」를 명시한다 — 안 적은 것과 없다고 판단한 것은 다른 사실이다.
   가리킨 판례가 아직 `OPEN`이면 그 판정은 원장에 남되 GT에는 안 나가고 기다린다.
   경계가 열려 있는데 개별 건을 확정하면 그 건들이 곧 답이 되어 버리기 때문이다.
   계약은 [gt-layer.md](.claude/os/engine/contracts/gt-layer.md)에 있다.
6. 하네스는 스킬을 `.claude/skills/<이름>/SKILL.md`, 에이전트를 `.claude/agents/`에서만 읽는다.
   실체는 각 패키지의 `skills/`·`agents/`에 두고, 그 자리에는 심볼릭 링크만 둔다.
   에이전트 링크는 `.claude/agents/<패키지>/<이름>.md`로 소속을 드러낸다. 하네스가 재귀로 읽고
   정체는 `name`이 정하므로 호출 이름은 그대로다. 에이전트는 `Read`·`Grep`·`Glob`만 갖는다 —
   판단은 하되 기록하지 않는다. 목록과 나눈 이유는 [PACKAGES.md](.claude/os/PACKAGES.md)에 있다.
7. 엔진이 낸 결과를 심사하는 `review/`는 **읽기만 한다.** 엔진을 import하지 않고 프로필도 읽지
   않으며, 자기 결과를 `runs/<id>/run-review/`에만 쓴다. 읽는 쪽이 원본을 고치면 다음 사람은
   어느 숫자가 원본인지 알 수 없다. 인계는 산출물 한 장이다 —
   [handoff.md](.claude/os/review/contracts/handoff.md).
8. 문서에 **다시 세어야 하는 숫자를 적지 않는다.** 건수·항목 수는 `run-summary.json`이나 분류표를
   가리킨다. 복사된 숫자는 조용히 틀려서, 틀린 채로 판단 근거가 된다.
   보고서를 뽑으면 `PostToolUse` 훅 `check-report-shape.py`가 이 규칙을 그 자리에서 확인한다.

## 무엇을 언제 읽는가

이 파일은 매번 로드된다. 그래서 여기에는 **매번 필요한 것만** 두고, 나머지는 필요할 때 연다.

| 하려는 일 | 여는 문서 |
|---|---|
| 사이클을 돌린다 | 스킬 `catalog-data-os` → 속성 스킬 (`bag-category-gender-os`) |
| 산출물을 브라우저에서 본다 | `./serve.sh start` → http://127.0.0.1:7391 |
| GT 정정 후보를 승인한다 | 위 화면의 각 조서 아래 **판정** 칸. 근거 판례·정책 규칙을 함께 고른다 |
| 판독기에게 정책을 넘긴다 | `policy/rule-briefs/<규칙ID>.md`를 **내용째로**. 손으로 발췌하지 않는다 |
| 이 결과로 판정을 시작해도 되는지 본다 | 스킬 `catalog-run-review` · [handoff.md](.claude/os/review/contracts/handoff.md) |
| 다음에 무엇을 고칠지 고른다 (GT·정책 개선 포인트) | 스킬 `catalog-improvement-sweep` |
| 판독기가 든 근거가 사진과 맞는지 되짚는다 | 스킬 `catalog-evidence-recheck` |
| 정책과 GT 중 어느 쪽이 틀렸는지 가른다 | [engine/goal.md](.claude/os/engine/goal.md)의 판정표 |
| 새 속성을 추가한다 | [customization-boundary.md](.claude/os/engine/contracts/customization-boundary.md) |
| 정책·판례 파일을 만들거나 고친다 | [policy-layer.md](.claude/os/engine/contracts/policy-layer.md) |
| 골든셋 계보를 합치거나 GT를 고친다 | [gt-layer.md](.claude/os/engine/contracts/gt-layer.md) |
| 정의가 비어 있어 질문부터 만든다 | [interview-protocol.md](.claude/os/interview/contracts/interview-protocol.md) |
| 패키지 경계·의존 방향을 확인한다 | [PACKAGES.md](.claude/os/PACKAGES.md) · 각 패키지 `package.md` |
| 왜 이 설계인지 되짚는다 | [DESIGN.md](.claude/os/DESIGN.md) |

## 구조

```
serve.sh        산출물을 로컬 웹으로 띄우는 진입점. 실체는 engine/scripts/serve_reports.py
.claude/gt/<id>/  골든셋 원장. 상품 하나에 라벨 하나  gt.jsonl  lineage.json
.claude/os/
  engine/       공통 코어. 속성을 모른다        contracts/ scripts/ skills/ agents/ workflows/ templates/ tests/
  review/       엔진 산출물을 심사한다. 읽기만 한다  contracts/ scripts/ skills/ agents/ tests/
  interview/    정의가 비어 있을 때 채우는 절차  contracts/ scripts/ skills/ agents/ tests/
  attributes/<id>/  속성 팩. profile.json이 유일한 플러그
                    policy/ ← 유일한 진실   adapters/ skills/ goal.md run.sh
  runs/<id>/    산출물. 지워도 된다            golden/ queue/ review/ reports/ run-review/(심사) improvements/(개선 포인트) policy/(스냅샷) asset/(이미지)
  DESIGN.md     설계 근거 §1~§16
```

의존은 한 방향이다 — **속성은 엔진을 알고, 엔진은 속성을 모른다.** 합격 기준은 하나다.
속성 폴더를 통째로 지워도 엔진이 그대로 돈다. `test_package_boundary.py`가 매번 확인한다.

## 자주 쓰는 명령

```bash
.claude/os/attributes/bag-category-gender/run.sh
```

```bash
./serve.sh start
```

```bash
python3 -m pytest .claude/os/engine/tests .claude/os/review/tests .claude/os/interview/tests .claude/os/attributes/bag-category-gender/tests -q
```

## 지금 도는 것 — 가방 상품 대상 성별

첫 동작 프로필이다. 정책은 `core-catalog-platfom`의 가방 Judge 프롬프트, 골든셋은 상품 단위
가방 GT를 쓴다. `run.sh` 한 번이 정책·GT 스냅샷 → 감사 큐 → 정책 질문서 → 사람 판정 진행률 →
HTML 보고서까지 돌고, 그 뒤에 심사가 이어진다. 결과는
`runs/bag-category-gender/reports/`의 네 장(`catalog-audit.html` 표지 · `gt-fixes.html` GT 정정 후보 ·
`suspect-gt.html` 의심되는 GT 찾기 · `policy-gaps.html` 빈 정책 찾기)과 `runs/bag-category-gender/run-review/`.
사례 보고서는 상품마다 판단기가 본 대표 이미지와 상세 타일을 밀집해 싣는다. 정정 후보는 한 제안이
한 장의 조서다 — `현재 GT → 제안`과 GT 출처, 판독기·리뷰어의 문장, 그리고 **판독기가 인용한 사진**이
한 화면에 있다. "이 GT가 틀렸다"는 주장이라 사진 없이는 반박도 동의도 못 하기 때문이다.
조서 끝에 **판정** 칸이 있다 — 보고 나서 그 자리에서 답한다.

GT를 묻는 두 장(`gt-fixes`·`suspect-gt`)에는 **실행 품질 지표를 싣지 않는다.** 표면 정확도·처리 건수·
정책 버전은 "이 GT가 틀렸나"에 답을 주지 않으면서, 옆에 있으면 판단에 섞인다. 실행 건강은 표지의 일이다.
형태의 기준과 아직 못 따라간 것은 [samples/README.md](.claude/os/attributes/bag-category-gender/samples/README.md)에 있다.

심사는 엔진이 방금 쓴 `run-summary.json`만 읽어 숫자를 다시 세고, 판정을 `FAIL`·`WARN`·`PASS`로
낸다. 미판정 건수보다 먼저 볼 것은 심사가 낸 **지금 사람이 가를 수 있는 건수**다 —
심판이 충돌 없다고 본 건과 미결 판례에 막힌 건을 뺀 나머지가 실제로 할 일이다.

**그 건수는 상품 단위라 일감의 크기가 아니다.** 심판이 「사람이 목표 기준으로 경계를 정한다」로
본 건은 상품 수십 개가 곧 정책 공백 하나이고, 골든셋과 실행 라벨이 이미 같은 건은 상품 단위로
뒤집을 것이 없다. 그래서 심사는 `decidableByOwner`와 `decidableWithAgreedLabels`를 함께 낸다.
건수만 보고 사람 시간을 잡으면 어긋난다.

큐는 두 갈래다. 하나는 **실행이 낸 값과 GT를 비교**하는 신호들이고, 다른 하나는
실행을 보지 않고 **GT를 정책과 직접 대조**하는 신호다. 뒤엣것이 필요한 이유는 앞엣것의 사각
때문이다 — 실행이 GT와 같은 값을 내면 비교할 것이 없어, 둘이 함께 정책을 어겨도 조용하다.

비교하는 쪽은 다섯 신호로 나뉜다 — 골든셋 소스 간 라벨 충돌, 정책과 실행 변환의 직접 모순, 근거 없이
GT와 우연히 일치, 정책이 답을 못 내는 공백, 정책 실행과 GT의 충돌. 신호별 정의와 어느 목록으로
접히는지는 [engine/goal.md](.claude/os/engine/goal.md) §6에 있다.

## 루프 — 사람이 답한 경계가 다음 실행으로 돌아온다

이 OS의 값어치는 한 번의 감사가 아니라 **경계가 쌓이는 속도**다. 그 고리는 이렇게 닫힌다.

```
정책 규칙  P1_DIRECT_TEXT · P2_COMBINED_DESIGN · P3_WEARER …
   │  규칙마다 브리프 한 장 (정책 원문 통째 + 확정된 근거 판례 + 적용 사례)
   ↓
판독  1순위·2순위·3순위 판독기가 자기 규칙 브리프를 받는다
   ↓
감사  실행과 GT를 대조해 정정 후보를 낸다
   ↓
승인  「어느 판례 / 어느 규칙 위의 판단인가」를 함께 고른다   ← 사람
   ↓
원장  decisions.json → 판례별·규칙별 사례집
   └──→ 다음 사이클의 브리프에 실려 판독으로 돌아간다
```

고리가 끊기는 자리는 셋이고, 셋 다 막아 두었다.

- **판례가 코드에 박히면** 판례를 더해도 실행이 안 바뀐다 → 판례가 `rule:`로 스스로 건다.
- **발췌를 손으로 뜨면** 조용히 잘린다 → 브리프가 섹션을 통째로 싣는다.
- **승인이 경계를 안 남기면** 다음에 되짚을 수 없다 → 판례나 규칙 중 하나는 반드시 적는다.

판례가 없는 규칙 위에서 사람이 반복해 판단하면 브리프가 그 사실을 센다. **그 숫자가
다음에 판례를 열 자리를 가리킨다** — 사람이 같은 경계를 매번 혼자 다시 넘고 있다는 뜻이다.

공통 흐름은 스킬 `catalog-data-os`, 가방 연결은 `bag-category-gender-os`가 맡는다. 공유 서브에이전트
`catalog-golden-adjudicator`가 근거를 정리하고, 확정은 데이터 운영팀만
`runs/<id>/review/decisions.json`에 남긴다. AI 추천은 사람 판정률에 넣지 않고, 판정을 바꿀 때는
이전 `decisionId`를 `supersedes`로 남긴다.

## 산출물을 읽는 자리 — 로컬 서버

`./serve.sh start`가 상시 프로세스 하나를 띄운다(`stop`·`status`·`restart`·`logs`·`open`).
**메뉴는 없다.** 뿌리를 열면 `run-summary.json`의 `artifacts`가 선언한 `gtFixesReport`,
곧 **GT 정정 후보**로 곧장 보낸다. 경로는 요청마다 다시 읽으므로 사이클을 다시 돌리면
새로고침만으로 바뀐다. 나머지 보고서는 그 화면 안의 상대 링크로 이어진다.

메뉴를 없앤 이유는 그 화면이 스스로 문제를 만들었기 때문이다 — 「GT 정정 후보」와
「의심되는 GT 찾기」가 같은 상품을 담고 있는데 카드 문구는 다른 묶음처럼 말했고,
「재판독 판정」은 위 둘과 한 건도 겹치지 않으면서 «위 보고서»를 가리켰다.
**고를 것이 없는데 고르게 만드는 화면**이었다.

**서버는 아무 화면도 그리지 않는다.** 그래서 숫자를 만들 자리 자체가 없다 —
세는 일은 보고서가 하고 서버는 리다이렉트만 한다. `test_serve.py`가 그것을 확인한다.

**쓰는 자리는 하나뿐이다 — 승인.** 「GT 정정 후보」의 각 조서에 판정 칸이 있어서, 읽던
자리에서 그대로 답한다. 전에는 터미널을 열고 상품 키를 옮겨 적어야 했고, 그래서 답이
안 쌓였다. 버튼은 `POST /decide`로 가고 그 요청은 CLI와 **같은 기록 함수**를 지난다 —
문이 둘이면 규격도 둘이 되고, 원장에 검증된 줄과 안 된 줄이 섞인다.
서버는 판정 원장 말고는 아무것도 쓰지 않는다. 보고서도 GT도 정책도 건드리지 않는다.

재판독 판정(`run-review/recheck.html`)은 심사 산출물이라 요약의 `artifacts`에 없다.
메뉴가 사라져 링크로는 닿지 않으므로 주소로 연다 —
`/f/<프로필ID>/run-review/recheck.html`.

미션 완료 조건 대응표와 설계 배경은 [DESIGN.md](.claude/os/DESIGN.md)에 있다.
