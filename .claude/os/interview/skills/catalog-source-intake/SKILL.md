---
name: catalog-source-intake
description: 어떤 카탈로그 속성이든 PRD·LLD·가이드·티켓 같은 자료를 골라 프로필 참조로 등록하고, 스냅샷을 뜨고, 슬롯별 인용 커버리지 표를 만들어 인터뷰가 확인 질문으로 시작하게 한다. "자료 등록해", "PRD 넣어줘", "참조 자료 접수", "이 문서들 읽고 시작해" 요청에서 사용한다.
---

# 카탈로그 자료 접수

인터뷰의 0단계다. 자료가 있으면 질문이 백지 질문에서 **확인 질문**으로 바뀐다 —
"PRD 3.2절은 사용처를 검색 필터라고 합니다. 추천에도 쓰나요?" 확인은 생성보다 싸다.

자료는 **답이 아니라 답의 후보**다. 자료 문장도 사람 답과 똑같이 세 관문을 지난다.
이 경계가 무너지면 자료의 모호함이 그대로 정책이 된다.

## 1. 후보 위치를 모은다

폴더·파일 경로를 받는다. Confluence·Jira는 먼저 로컬 파일로 만든다(`wiki-to-md` 등).
자료가 프로젝트 밖(`../다른-레포/docs/...`)이어도 된다. 스냅샷을 뜨므로 원본은 읽기만 한다.

## 2. 큐레이터에게 고르게 한다

`catalog-source-curator` 서브에이전트에 프로필 경로, 후보 위치, `slots.json` 경로를 넘긴다.
돌아오는 것은 셋 — `references` 제안, 제외 목록과 이유, 슬롯별 인용 `candidates`.

## 3. 사람이 확인한 것만 프로필에 넣는다

제안 목록을 사용자에게 보여주고, 확인된 항목만 프로필 `references` 배열에 쓴다.
프로필은 유일한 플러그이고 손으로 소유하는 파일이다. AI 제안을 자동으로 넣지 않는다.

```json
"references": [
  {"id": "lld", "kind": "LLD", "path": "../repo/docs/x-lld.md", "note": "정책·스코프 정본"}
]
```

## 4. 스냅샷을 뜬다

```bash
python3 .claude/os/interview/scripts/import_interview_sources.py --profile '<profile.json>'
```

`runs/<id>/interview/sources/<id>.<ext>`와 `manifest.json`(sha256)이 생긴다. 없는 자료는 경고만 남기고 계속한다.

## 5. 커버리지 표를 저장한다

큐레이터의 `candidates`를 `runs/<id>/interview/coverage.json`으로 쓴다. `basedOn`에 manifest의
`{자료ID: sha256}`을 그대로 넣는다. 자료가 바뀌면 스캐너가 이 해시로 `STALE`을 알린다.

```json
{"schemaVersion": "catalog-interview-coverage-v1", "profileId": "<id>", "generatedAt": "<시각>",
 "basedOn": {"lld": "<sha256>"},
 "candidates": [{"slot": "SLOT-PURPOSE", "sourceId": "lld", "cite": "§스코프", "quote": "…", "note": "…"}]}
```

이 파일은 AI 산출물이고 재생성 가능하다. 원장이 아니다.

## 6. 다시 센다

```bash
python3 .claude/os/interview/scripts/scan_ambiguity.py --profile '<profile.json>'
```

"자료가 답하지 못하는 빈 열"이 곧 진짜 인터뷰 대상이다. 나머지는 확인 질문으로 빠르게 지나간다.
자료에서 온 답을 기록할 때는 `--source DOCUMENT --cite '<자료ID>#<위치>'`를 쓴다. 인용 없는 문서 근거는 거절된다.

## 완료 조건

1. 프로필 `references`의 항목마다 사람이 확인했다
2. `sources/manifest.json`이 있고 누락 자료가 0이거나 이유가 있다
3. `coverage.json`이 있고 스캐너가 `FRESH`라고 한다
4. 빈 열 목록을 사용자에게 보여줬다 — 이것이 인터뷰의 첫 질문 목록이다
