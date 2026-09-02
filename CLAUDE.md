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
4. 손으로 쓴 정책과 판례는 `attributes/<id>/policy/`에만 둔다. `runs/` 안의 정책은 가져온 읽기 전용 스냅샷이다.
5. IMPORTANT: 사람 판정 원장 `runs/<id>/review/decisions.json`에는 사용자가 명시적으로 확정한 결정만
   기록한다. AI 추천을 자동으로 기록하지 않는다.
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
| 이 결과로 판정을 시작해도 되는지 본다 | 스킬 `catalog-run-review` · [handoff.md](.claude/os/review/contracts/handoff.md) |
| 정책과 GT 중 어느 쪽이 틀렸는지 가른다 | [engine/goal.md](.claude/os/engine/goal.md)의 판정표 |
| 새 속성을 추가한다 | [customization-boundary.md](.claude/os/engine/contracts/customization-boundary.md) |
| 정책·판례 파일을 만들거나 고친다 | [policy-layer.md](.claude/os/engine/contracts/policy-layer.md) |
| 정의가 비어 있어 질문부터 만든다 | [interview-protocol.md](.claude/os/interview/contracts/interview-protocol.md) |
| 패키지 경계·의존 방향을 확인한다 | [PACKAGES.md](.claude/os/PACKAGES.md) · 각 패키지 `package.md` |
| 왜 이 설계인지 되짚는다 | [DESIGN.md](.claude/os/DESIGN.md) |

## 구조

```
.claude/os/
  engine/       공통 코어. 속성을 모른다        contracts/ scripts/ skills/ agents/ templates/ tests/
  review/       엔진 산출물을 심사한다. 읽기만 한다  contracts/ scripts/ skills/ agents/ tests/
  interview/    정의가 비어 있을 때 채우는 절차  contracts/ scripts/ skills/ agents/ tests/
  attributes/<id>/  속성 팩. profile.json이 유일한 플러그
                    policy/ ← 유일한 진실   adapters/ skills/ goal.md run.sh
  runs/<id>/    산출물. 지워도 된다            golden/ queue/ review/ reports/ run-review/(심사) policy/(스냅샷) asset/(이미지)
  DESIGN.md     설계 근거 §1~§16
```

의존은 한 방향이다 — **속성은 엔진을 알고, 엔진은 속성을 모른다.** 합격 기준은 하나다.
속성 폴더를 통째로 지워도 엔진이 그대로 돈다. `test_package_boundary.py`가 매번 확인한다.

## 자주 쓰는 명령

```bash
.claude/os/attributes/bag-category-gender/run.sh
```

```bash
python3 -m pytest .claude/os/engine/tests .claude/os/review/tests .claude/os/interview/tests .claude/os/attributes/bag-category-gender/tests -q
```

## 지금 도는 것 — 가방 상품 대상 성별

첫 동작 프로필이다. 정책은 `core-catalog-platfom`의 가방 Judge 프롬프트, 골든셋은 상품 단위
가방 GT를 쓴다. `run.sh` 한 번이 정책·GT 스냅샷 → 감사 큐 → 정책 질문서 → 사람 판정 진행률 →
HTML 보고서까지 돌고, 그 뒤에 심사가 이어진다. 결과는
`runs/bag-category-gender/reports/`의 세 장(`catalog-audit.html` 표지 · `suspect-gt.html` 의심되는 GT 찾기 ·
`policy-gaps.html` 빈 정책 찾기)과 `runs/bag-category-gender/run-review/`. 사례 보고서는 상품마다
판단기가 본 대표 이미지와 상세 타일을 밀집해 싣는다.

심사는 엔진이 방금 쓴 `run-summary.json`만 읽어 숫자를 다시 세고, 판정을 `FAIL`·`WARN`·`PASS`로
낸다. 미판정 건수보다 먼저 볼 것은 심사가 낸 **지금 사람이 가를 수 있는 건수**다 —
심판이 충돌 없다고 본 건과 미결 판례에 막힌 건을 뺀 나머지가 실제로 할 일이다.

큐는 다섯 신호로 나뉜다 — 골든셋 소스 간 라벨 충돌, 정책과 실행 변환의 직접 모순, 근거 없이
GT와 우연히 일치, 정책이 답을 못 내는 공백, 정책 실행과 GT의 충돌. 신호별 정의와 어느 목록으로
접히는지는 [engine/goal.md](.claude/os/engine/goal.md) §6에 있다.

공통 흐름은 스킬 `catalog-data-os`, 가방 연결은 `bag-category-gender-os`가 맡는다. 공유 서브에이전트
`catalog-golden-adjudicator`가 근거를 정리하고, 확정은 데이터 운영팀만
`runs/<id>/review/decisions.json`에 남긴다. AI 추천은 사람 판정률에 넣지 않고, 판정을 바꿀 때는
이전 `decisionId`를 `supersedes`로 남긴다.

미션 완료 조건 대응표와 설계 배경은 [DESIGN.md](.claude/os/DESIGN.md)에 있다.
