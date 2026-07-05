---
topic: nextstep-start-skill-new
status: 완료
source: docs/interviews/2026-07-06-nextstep-start-skill.md
---

# nextstep-start 스킬 신설 (미션 최초 시작: fork → clone → 최초 브랜치)

## 목표
넥스트스텝 미션을 처음 시작할 때의 미커버 구간(fork → clone → 최초 작업 브랜치 생성)을 스킬 하나로 처리해, 기존 스킬들과 미션 라이프사이클을 완성한다: **nextstep-start(시작)** → nextstep-check(조건 확인) → commit → nextstep-pr(리뷰 요청) → nextstep-advance(다음 단계).

## 범위
- 포함: fork·clone·최초 브랜치 생성 실행 + 앞뒤 수작업 구간(미션 시작 버튼, IDE Import) 한 줄 안내 + gh 실패 시 브라우저 폴백 + 재실행 멱등성
- 제외: 커밋·push·PR(기존 commit/nextstep-pr 스킬), 이후 단계 브랜치(nextstep-advance), 미션 구현 자체

## 구현 단계
1. `.claude/skills/nextstep-start/SKILL.md` 작성. 인터뷰 확정 결정을 반영:
   - **머리말**: name/description(트리거 예: "미션 시작하려는데 저장소 세팅해줘", "fork부터 해줘", "nextstep-start") + `설계 근거: docs/interviews/2026-07-06-nextstep-start-skill.md` ref 한 줄 (Q1~Q8 결정 반영).
   - **0단계 — 사전 안내**: 넥스트스텝 사이트에서 미션 시작 버튼을 눌렀는지(리뷰어 배정·본인 아이디 브랜치 생성) 한 줄 확인 안내 (Q1).
   - **1단계 — 미션 저장소 확인**: 호출 시 URL·저장소명이 있으면 그대로 쓰고, 없으면 사용자에게 질문 (Q3).
   - **2단계 — fork + clone**: `gh repo fork {owner}/{repo} --clone`으로 **현재 디렉토리 바로 아래**(`{현재 위치}/{repo}`)에 클론 (Q2, Q4). 이미 fork가 있으면 gh가 기존 fork를 재사용, clone 디렉토리가 이미 있으면 새로 받지 않고 그 안에서 다음 단계로 진행 (Q8).
   - **gh 폴백**: gh 미설치·미인증이면 브라우저 Fork 버튼 URL(`https://github.com/{owner}/{repo}/fork`)을 안내하고, fork 완료 후 `git clone`부터 이어서 진행 (Q7).
   - **3단계 — upstream 확인·보장**: `git remote -v`로 origin(본인 fork)/upstream(next-step 원본) 둘 다 있는지 확인, 없으면 추가 — 어느 경로로 왔든 nextstep-advance가 바로 쓸 수 있는 상태로 마무리 (Q5).
   - **4단계 — 최초 작업 브랜치**: `git checkout -b step1`을 기본 제안하고 확인 후 실행(다르면 사용자가 수정) (Q6).
   - **5단계 — 마무리 안내**: 작업 위치·브랜치를 알리고, IDE Import 안내 한 줄 + 이후 흐름(구현 → nextstep-check → commit → nextstep-pr) 소개 (Q1).
   - **하지 말 것**: placeholder를 그대로 두지 않기(실제 값 채움), 기존 clone 디렉토리 덮어쓰지 않기, 미션 구현·커밋·PR까지 넘보지 않기 — 기존 nextstep 스킬 규약과 동일 톤.
2. 인터뷰 기록 frontmatter `artifact:`를 `(미구현)`에서 `.claude/skills/nextstep-start/SKILL.md`로 갱신.

## 건드릴 파일
- `.claude/skills/nextstep-start/SKILL.md` — 신설 (스킬 본체, 스크립트 없음)
- `docs/interviews/2026-07-06-nextstep-start-skill.md` — frontmatter `artifact:` 갱신
