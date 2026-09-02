---
name: catalog-interview
description: 어떤 카탈로그 속성이든 비어 있는 정의를 찾아 한 번 답하면 닫히는 경계 질문으로 바꾸고, 사람이 확정한 답만 원장에 기록한다. "정책이 애매해", "허용값부터 정하자", "새 속성 시작", "이 질문에 답할게" 요청에서 사용한다.
---

# 카탈로그 정의 인터뷰

모호함을 구체로 바꾸는 절차는 네 단계다 — **분류 → 위치 → 질문 → 검사**.
분류표는 `.claude/os/interview/contracts/ambiguity-taxonomy.md`,
규약은 `.claude/os/interview/contracts/interview-protocol.md`에 있다.

## 0. 자료가 있으면 먼저 접수한다

PRD·LLD·가이드가 있으면 `catalog-source-intake`로 먼저 등록·스냅샷·커버리지 표를 만든다.
그러면 스캐너가 슬롯마다 자료 후보를 붙이고, 질문이 백지 질문에서 **확인 질문**으로 바뀐다.
자료 문장은 답이 아니라 후보다 — 세 관문은 그대로다.

## 1. 빈칸부터 센다

```bash
python3 .claude/os/interview/scripts/scan_ambiguity.py --profile '<profile.json>'
```

빈 페이지에서 시작하지 않는다. 스캐너가 `EMPTY`·`THIN`·`FILLED`를 세고 다음 질문 하나를 고른다.
큐에 이미 올라온 애매 상품도 함께 센다(`ambiguousProducts`). 반례는 지어내지 않고 여기서 고른다.
모드가 `NEW`면 정의가 아직 안 선 것이고, `GAP`이면 자리표시자와 열린 판례만 남은 것이다.

슬롯 순서는 레이어 서열 **목표 > 정책 > GT**를 따른다.

| 층 | 슬롯 | 묻는 것 |
|---|---|---|
| 목표 | `SLOT-PURPOSE` · `SLOT-VERDICT` · `SLOT-QUALITY` | 누가 쓰고 틀리면 무슨 일이 생기는가 · "옳다"가 무슨 뜻인가 · 100건 중 몇 건까지 버티는가 |
| 아는 것 | `SLOT-PROVENANCE` | 지금 정책이 어디에 있고 누가 정했는가 |
| 정책 | `SLOT-SCOPE` · `SLOT-LABELS` · `SLOT-ABSTAIN` · `SLOT-PRIORITY` · `SLOT-BLAME` | 대상·값·판정 불가·근거 순서·귀책 |
| 판례 | `SLOT-PRECEDENT` · 열린 판례 | 이미 답한 경계가 정책에 연결됐는가 |

목표를 건너뛰고 값부터 정하면, 목표가 정해지는 순간 값이 전부 뒤집힌다.
아는 것을 세지 않고 물으면 이미 답이 있는 걸 다시 묻는다.

## 2. 질문 하나를 만든다

`catalog-interviewer` 서브에이전트에 프로필 경로와 `slots.json` 경로를 넘긴다.
질문은 `nextSlot` 하나만 다루고, 선택지·대가·권고·영향 건수·반례 쌍 2건을 함께 낸다.
반례와 영향 건수는 큐의 실제 상품으로 든다 — "이미 이런 상품 n건이 애매하다고 잡혀 있고,
이 답이면 이 상품은 이렇게 됩니다". "애매합니다"로 끝내지 않는다.

## 3. 답을 검사한다

관찰 가능 · 재현 가능 · 닫힘. 셋 중 하나라도 떨어지면 후속 질문 한 개를 만든다.
같은 슬롯에서 3회 되묻지 않는다. 못 닫히면 `OPEN`으로 내린다.

## 4. 사람이 확정한 답만 기록한다

```bash
python3 .claude/os/interview/scripts/record_interview_answer.py \
  --profile '<profile.json>' --slot '<SLOT-ID>' \
  --question '<물은 것>' --answer '<사람이 확정한 규칙 문장>' \
  --answered-by '<이름>' --status RESOLVED \
  --observable --closed \
  --counter-example '<사례 A> => <값>' --counter-example '<사례 B> => <다른 값>' \
  --source OWNED --confidence DECIDED --owner '<확정할 수 있는 사람>' \
  --applies-to '<답이 들어갈 파일>'
```

`--option`은 사람 앞에 놓였던 선택지, `--reason`은 왜 이 답인지, `--session`은 ADR 한 장의 단위다.
자료에서 온 답은 `--source DOCUMENT --cite '<자료ID>#<위치>'`다. 인용 없는 문서 근거는 거절된다.
`--source`는 이 규칙이 어디에 있었는지(`OWNED`·`SNAPSHOT`·`TACIT`·`NEW`),
`--confidence`는 누가 정했는지(`DECIDED`·`CUSTOM`·`GUESS`)다. **`GUESS`는 `RESOLVED`가
될 수 없다.** 추측을 정책에 넣으면 다음 사이클에서 근거 없는 일치로 되돌아온다.

AI가 만든 질문·선택지·권고는 기록 대상이 아니다. 판정 원장과 같은 규칙이다.
세 검사를 못 넘으면 스크립트가 거절한다. 기준을 바꿀 때는 `--supersedes`로 이전 `answerId`를 남긴다.

## 5. ADR로 남긴다

```bash
python3 .claude/os/interview/scripts/render_interview_adr.py --profile '<profile.json>'
```

세션 하나가 `attributes/<id>/adr/ADR-<NNNN>-<세션>.md` 한 장이다. 질문·선택지·답·이유·반례·출처·적용처가
Q&A로 남는다. 이미 있는 ADR은 덮어쓰지 않는다.

## 6. 적용하고 다시 센다

답을 `attributes/<id>/goal.md` 또는 `policy/policy.md`·`policy/precedents/<ID>.md`로 옮긴다.
파일 수정은 사용자 승인 뒤에 한다. 옮긴 뒤 스캐너를 다시 돌려 슬롯이 `FILLED`로 바뀌는지 본다.
안 바뀌었으면 그 답은 아직 문장이 아니다.

## 완료 조건

1. `<outputRoot>/interview/slots.json`의 `empty`가 0
2. 남은 `THIN`마다 `OPEN` 판례가 하나씩 있다
3. `RESOLVED`로 기록된 답마다 `appliesTo` 파일에 실제 문장이 들어갔다
4. `build_policy_index.py`의 `BLOCKING` 위반이 0
5. 목표 슬롯의 판정 한 문장으로 상품 하나를 실제로 판정해봤고, 두 사람이 같은 답을 냈다
6. 세션의 ADR이 렌더됐고, 반례로 든 큐 상품이 다음 사이클에서 큐에서 빠졌다
