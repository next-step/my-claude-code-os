# interview

모호한 요구를 **판정 가능한 문장**으로 바꾸는 절차. 엔진은 데이터가 있어야 돌지만
인터뷰는 데이터가 없어도 돈다. 그래서 별도 패키지다.

사이클이 시작되려면 세 가지가 이미 있어야 한다 — 허용값, 근거 우선순위, 판정 불가 조건.
이 셋을 누가 어떻게 채우는지는 지금까지 어디에도 없었다. 그 빈자리가 이 패키지다.

그리고 그 셋보다 먼저 정해져야 하는 것이 둘 더 있다.

- **목표** — "이 값이 옳다"가 무슨 뜻인가. 판정표의 ①은 사람만 채울 수 있고,
  사람은 이 문장을 읽고 채운다. 이 문장이 없으면 정책과 GT가 갈릴 때마다
  그 자리에 있던 사람의 취향이 결정한다.
- **아는 것** — 지금 정책이라 부르는 문장이 어디에 있고 누가 정했는가.
  정한 것과 그냥 해온 것을 섞으면, 나중에 왜 그런지 아무도 모르는 규칙이 정책에 남는다.

## 소유

| 종류 | 파일 |
|---|---|
| 분류 | `contracts/ambiguity-taxonomy.md` — 모호함의 종류와 각각을 푸는 도구 |
| 규약 | `contracts/interview-protocol.md` — 4단계 절차, 질문 5규칙, 검사 3관문 |
| 슬롯 계약 | `contracts/slots.json` — 질문이 나올 수 있는 유일한 출처 |
| 자료 접수 | `scripts/import_interview_sources.py` — 프로필 `references`를 스냅샷·해시로 |
| 스캐너 | `scripts/scan_ambiguity.py` — 빈칸·큐 상품·자료 커버리지를 세고 다음 질문 하나를 고른다 |
| 답변 원장 | `scripts/record_interview_answer.py` — 세 검사를 통과한 답만 받는다 |
| ADR | `scripts/render_interview_adr.py` — 세션 하나를 Q&A 문서 한 장으로 |
| 뼈대 | `templates/adr.md` — ADR 모양. 목표 뼈대는 `engine/templates/goal.md` |
| 테스트 | `tests/test_interview_contract.py` |
| 스킬 | `skills/catalog-source-intake` · `skills/catalog-interview` |
| 에이전트 | `agents/` — `catalog-source-curator` 자료 선별 · `catalog-interviewer` 질문 |
| 진입점 링크 | `.claude/skills/<이름>` · `.claude/agents/interview/<이름>.md` → 여기 |
| 산출물 | `.claude/os/runs/<프로필ID>/interview/` — `slots.json`·`sources/`·`coverage.json`은 재생성 가능, `answers.json`은 사람 원장 |
| 결정 | `.claude/os/attributes/<프로필ID>/adr/ADR-*.md` — 원장에서 렌더, 지우면 안 됨 |

## 규칙

- **슬롯이 질문을 만든다.** 도착지가 없는 질문은 하지 않는다. 답을 받아도 쌓을 곳이 없으면
  그 대화는 대화로 끝난다. 슬롯 목록은 전부 엔진이 이미 검증하는 빈칸이다.
- **세 검사를 통과하지 못한 답은 `RESOLVED`로 기록되지 않는다.** 규약을 문서에만 두면
  바쁠 때 가장 먼저 생략된다. 그래서 스크립트가 거절한다.
- **모른다는 답도 산출물이다.** `OPEN`으로 남기고 판례 파일로 옮긴다.
  추측으로 슬롯을 채우면 그 추측이 다음 사이클 전체의 기준이 된다.
- **답마다 출처와 확신도를 남긴다.** `GUESS`는 `RESOLVED`가 될 수 없다.
  확신도가 낮은 답이 아니라 아직 답이 아니기 때문이다.
- **자료는 답이 아니라 답의 후보다.** 자료가 있으면 질문이 확인 질문으로 짧아지지만,
  자료 문장도 세 관문을 지난다. 자료가 게이트를 우회하면 자료의 모호함이 정책이 된다.
- **반례는 큐에서 고른다.** 사이클이 이미 애매하다고 잡은 상품이 있는데 새로 지어내면,
  답이 맞았는지 다음 사이클에서 확인할 길이 없다.
- **세션 하나가 ADR 한 장이다.** 사람이 읽는 것은 원장이 아니라 Q&A다. 이미 있는 ADR은 덮어쓰지 않는다.
- **속성 이름을 모른다.** 엔진과 같은 규칙이고, `tests/test_interview_contract.py`가 확인한다.

## 의존 방향

```
interview  ──▶  engine        (프로필 해석기를 그대로 쓴다)
engine     ──✗  interview     (엔진은 인터뷰를 모른다)
```

인터뷰가 멈춰도 사이클은 돈다. 다만 빈칸이 빈 채로 돈다.

## 실행

```bash
python3 .claude/os/interview/scripts/scan_ambiguity.py --profile '<profile.json>'
```

## 검증

```bash
python3 -m pytest .claude/os/interview/tests -q
```
