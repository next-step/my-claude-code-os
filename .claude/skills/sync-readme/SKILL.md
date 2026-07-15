---
name: sync-readme
description: 현재 프로젝트의 실제 상태(스킬·에이전트·디렉터리 구조)를 스캔해 README.md를 최신화한다.
user-invocable: true
allowed-tools: Read Glob Bash Agent
---

# /sync-readme 스킬 — README 최신화 오케스트레이터

`.claude/` 파일시스템의 **현재 실제 상태**를 스캔해서, 낡은 `README.md`를
실제 구현과 일치하도록 갱신한다.

스킬을 추가/삭제하거나 디렉터리 구조를 바꾼 뒤 실행하면, README의 스킬 표·
에이전트 표·디렉터리 트리·상태 흐름 설명을 한 번에 맞춰준다.

## 사용법

```
/sync-readme        ← 변경분을 반영한 README 갱신안을 만들고 diff로 보여준다
```

---

## 실행 절차

> **설계 포인트 — 정본(source of truth)을 읽는다**
> README는 사람이 손으로 쓰는 문서라 코드/스킬이 바뀌면 금세 낡는다.
> 이 스킬은 README의 *옛 내용을 믿지 않고*, 항상 실제 파일시스템을 스캔해
> 거기서 사실을 다시 길어 올린다. ([[remind-when]]이 crontab 정본을 직접
> 읽는 것과 같은 철학.)
>
> **오케스트레이터 패턴 포인트 — 단일 서브에이전트 위임**
> 스캔·비교·갱신을 하나의 서브에이전트([[readme-sync-agent]])에 통째로 위임한다.
> 그 서브에이전트의 독립 창에서 트리·README 전문을 흡수하고, 메인엔 **변경 요약만**
> 돌아온다. 메인은 원자료를 흡수하지 않아 가볍게 유지된다.

### Step 1: readme-sync-agent 공유 에이전트에 스캔·갱신 위임

`_shared/readme-sync-agent` 공유 서브에이전트에 위임한다. Agent 도구를 **한 번** 호출하며
아래 입력 계약을 채워 전달한다. 스캐너와 작가를 나누지 않고 **한 번의 위임으로** 스캔 →
README 읽기 → 갱신 → 요약까지 끝낸다.

- **스캔 지시**: 아래 Bash 레시피로 실제 사실을 수집하라고 전달한다.

  ```bash
  echo "=== 스킬 목록 + 각 description ===" && \
  for f in .claude/skills/*/SKILL.md; do
    name=$(awk -F': ' '/^name:/{print $2; exit}' "$f")
    desc=$(awk -F': ' '/^description:/{print $2; exit}' "$f")
    printf -- "- /%s — %s\n" "$name" "$desc"
  done && \
  echo "" && echo "=== _shared / 로컬 에이전트 파일 ===" && \
  ls -1 .claude/skills/_shared/*.md 2>/dev/null && \
  find .claude/skills -name '_*.md' 2>/dev/null && \
  echo "" && echo "=== 디렉터리 구조 ===" && \
  ( command -v tree >/dev/null && tree -a -I '.git' .claude || find .claude -not -path '*/.git/*' | sort )
  ```

- **대상 파일 경로**: `README.md`
- **도메인 특화 제약 (README 전용)**:
  - 기존 README의 **구성·말투·한국어 톤을 유지**한다 (전면 재작성 금지, 어긋난 부분만 고친다)
  - 스킬 표·"에이전트 종류" 표·"디렉터리 구조" 트리·빠른 시작 예시·상태 흐름 다이어그램을
    스캔한 실제 사실에 맞춘다
  - 새로 추가된 스킬은 표와 디렉터리 트리 양쪽에 빠짐없이 등록, 사라진 스킬/파일은 제거
  - data/ 같은 비밀값 파일은 **존재 여부만** 확인하고, 토큰 등 값은 README·요약에 절대 옮기지 않는다

### Step 2: 결과 확인

에이전트가 갱신을 마치면 `git diff README.md`로 변경분을 사용자에게 보여준다.
커밋은 사용자가 원할 때만 한다. (이 OS의 커밋은 사용자 결정 사항)

---

## 설계 노트 — 왜 이렇게 만들었나

- **AI 협업 학습 포인트 — 위임은 공짜가 아니다**: 큰 검색·리뷰의 토큰을 서브에이전트가 흡수하면
  메인은 가벼워지지만(README 13.7KB가 메인에 안 쌓임), 그 대가로 **서브에이전트 창을 통째로 연다**.
  그래서 위임은 **메인이 큰 파일을 Read할 때만** 이득이다. sync-readme는 README 전문을 다루므로
  이득이고, grep-only인 [[sync-test]]는 스캔이 작아 위임하지 않는다.
- **스캔과 작성을 한 에이전트로 합친 이유**: 처음엔 scanner→writer 두 서브에이전트로 나눴다가,
  서브에이전트를 **두 번** 열어 총 토큰이 오히려 늘는 걸 확인하고 하나로 합쳤다. README 갱신은
  "스캔한 사실을 그대로 문서에 옮기는" 단순 전사라, 수집과 작성을 나눌 실익이 없다. 하나로
  합쳐 서브에이전트를 **한 번만** 열고, 사실을 메인으로 중계하는 손실도 없앴다.
  (사람이 "자동 채움/보고만"을 중간에 결정해야 하는 [[sync-test]]는 분리를 유지 — [[state-sync-writer]].)
- README가 곧 이 레포의 "사용 설명서"이자 OS 설계의 거울이므로, 새 스킬을 추가할 때마다
  `/sync-readme` 한 번이면 문서가 따라오도록 한 것이 목적이다.
