# Day2 과제 워크시트 — 내 OS에 컨텍스트 체계 심기

> 이 파일은 `/clear` 로 대화가 날아가도 작업을 이어갈 수 있게 **계획과 측정값을 박제**해 둔 것이다.
> 수업 자료: `Day2.pdf` (p.23 · p.35 실습 완료, p.47 실습 = 과제 도전 2로 흡수).

---

## 0. 현재 상태 (2026-09-07 확인)

- **p.23 실습 (컨텍스트 체계 설계)** — 설계·작성 완료. "실제 활용 확인"(A/B)만 미실행.
- **p.35 실습 (interview 스킬)** — 방법론(`interview-method.md`)·스킬(`skills/interview/`) 제작 완료. 실제 인터뷰 1회 미실행.
- **p.47 실습 (컨텍스트 최적화)** — 미실행. 과제 도전 2에서 진행.

staged 파일 12개 (아직 커밋 안 됨):

```
.claude/context/            README.md · team-capability.md · classification-policy.md · interview-method.md
.claude/skills/interview/    SKILL.md (신규)
.claude/skills/intake/       SKILL.md (수정 — 필수/선택/가정 처리)
.claude/agents/              classifier.md · intake-interview.md (판단기준 → context 파일 참조로 전환)
maintenance/                 capacity.md (신규) · README.md (수정)
CLAUDE.md                    규칙 4·5 추가 + @team-capability.md 항상 로드
.claude/README.md            context/ 항목 추가
```

---

## 1. before 지표 측정 (지금 할 것)

### 절차

1. 이 파일 저장 확인 → `/clear`
2. `/context` 실행 → **측정 1** 표에 숫자 기입
3. `CLAUDE.md` 마지막 줄 `@.claude/context/team-capability.md` 삭제(또는 `#` 주석)
4. `/clear` → `/context` → **측정 2** 표에 기입
5. `CLAUDE.md` 그 줄 **복구**
6. (선택) 측정 3 — 스킬 실행 후 발자국. 지금은 건너뛰고 도전 2에서.

> `/context` 출력은 항목별 토큰 수로 나온다. 아래 표의 항목명은 버전에 따라 조금 다를 수 있으니 비슷한 줄을 적으면 된다.

### 측정 1 — 클린 베이스라인 (`@team-capability.md` 포함)

| 항목 | 토큰 |
| --- | --- |
| System prompt | 4.5k tokens |
| System tools | 20.4k tokens |
| MCP tools | 30 tools · 0 tokens |
| Memory files (CLAUDE.md + @import) | 1.2k tokens |
| Custom agents |  agents · 645 tokens |
| **합계** | 30.7k/1m tokens |
| 남은 여유 | 936.3k |

측정일: 2026-09-07

### 측정 2 — `@team-capability.md` import 제거 후

| 항목 | 토큰 |
| --- | --- |
| Memory files | 259 tokens |
| **합계** | 29.8k/1m tokens |

측정일: 2026-09-07

**→ `@team-capability.md` import 비용 = 측정1 Memory files − 측정2 Memory files ≈ 1.2k − 259 ≈ 약 940 토큰**

> `team-capability.md` 원문은 1,115자(한글 위주). 세션 시작마다 무조건 이 ~940 토큰을 낸다.
> 이 파일을 자주 안 읽는 스킬까지 전부 부담하므로, Day2 도전 2(최적화)에서 "항상 로드" 대신
> Lazy Read 로 내릴지 판단할 후보 1순위.

### 측정 3 — 도전 2 최적화 전·후 (`@import` 제거)

**최적화 내용**: `CLAUDE.md` 의 `@import` 2줄 제거.
- `style.md` → PreToolUse 훅(`Write`/`Edit`, 세션당 1회) 주입
- `team-capability.md` → Lazy Read (소비자 classifier·intake-interview 가 직접 Read)

**측정 절차** (실제 숫자는 `/context` 로 채울 것):
1. 최적화 전 커밋(`4ae2cfd` 또는 그 이전)으로 `git switch --detach 4ae2cfd` → `/clear` → `/context` → "Memory files" 기록 = **before**
2. `git switch step2` (최적화 후) → `/clear` → `/context` → "Memory files" 기록 = **after**
3. 절감 = before − after

| 시점 | Memory files 토큰 | 합계 토큰 |
| --- | --- | --- |
| before (`@team-capability` + `@style` 항상 로드) | (기입) | (기입) |
| after (`@import` 0개) | (기입) | (기입) |
| **절감** | (기입) | (기입) |

**예상** (측정 1·2 기준 추정): `@team-capability` ≈ 940 토큰 + `@style`(원문이 team-capability 의 약 1.2배) ≈ 1,100 토큰
→ 세션 시작 baseline 에서 **약 2,000 토큰(≈ Memory files 의 88%) 감소** 예상. `CLAUDE.md` 본문이 설명 추가로 ~150 토큰 늘어 순감은 ~1,850.

**트레이드오프**: `style.md` 는 파일을 쓰는 세션에서 첫 `Write`/`Edit` 때 ~1,100 토큰이 한 번 들어옴(그 뒤 재주입 없음).
파일을 안 쓰는 세션(질문·조사·계획)은 0. `team-capability.md` 는 `classifier`/`intake-interview` 가 돌 때만 Read.

---

## 2. 과제 할 일 (순서)

Day2 과제 완료 조건 = 필수 3 + 도전 2.

| # | 구분 | 할 일 | 완료 조건 | 상태 |
| - | --- | --- | --- | --- |
| 0 | 준비 | `team-capability.md` 의 `(채울 것)` 를 `sandbox/board` 소유팀 값으로 교체 (첨삭 제출용이라 실회사 정보는 뺌 — 회사 전환 시 이 파일만 교체) | 플레이스홀더 0개 | ✅ |
| 1 | 필수 1 | 컨텍스트 md **5개 이상** + 스킬·서브에이전트 자동 주입 연결 | `.claude/context/` 실질 컨텍스트 5개, 각각 소비자에 연결(=@import / Read 지침 / 훅 트리거) | ✅ (6개, A/B 실증은 필수 2에서) |
| 2 | 필수 2 | 주입 O/X **A/B 동작 비교** (`skill-creator` 포함) | 같은 입력에 대해 컨텍스트 있을 때 vs 없을 때 스킬 출력 차이를 기록 | ✅ → [`day2-ab-injection-test.md`](./day2-ab-injection-test.md) |
| 3 | 필수 3 | 컨텍스트 체계 **도식화** 1P 파일 | `docs/` 에 다이어그램 파일 1개 (파일→트리거→소비자 관계) | ✅ → [`day2-context-map.md`](./day2-context-map.md) |
| 4 | 도전 1 | 주입 검증 **테스트** 제작 | 컨텍스트가 실제로 주입됐는지 확인하는 자동 검사 | ✅ → `.claude/scripts/check-context-wiring.sh` |
| 5 | 도전 2 | 컨텍스트 체계 **최적화 + 정량 비교** (= p.47) | 위 before 표 대비 after 표, 절감 토큰/% 기록 | ✅ (측정 3 절차, `/context` 숫자만 기입 대기) |

### 필수 1 — 컨텍스트 6개 + 주입 연결 (완료 2026-09-07, 도전 2에서 주입 방식 재배정)

| 파일 | 소비자 | 주입 방식 (도전 2 이후) |
| --- | --- | --- |
| `style.md` (신규) | 파일 쓰는 모든 스킬·에이전트 | **훅** — `Write`/`Edit` PreToolUse, 세션당 1회 |
| `team-capability.md` | `classifier`, `intake-interview` | **Lazy Read** (도전 2 전엔 `@import`) |
| `classification-policy.md` | `classifier`, `intake` | Lazy Read |
| `sizing.md` (신규) | `classifier`, `/spec` | Lazy Read — `classifier.md` "판단 전 Read 목록 5" |
| `dod-patterns.md` (신규) | `/spec`, `spec-reviewer` | Lazy Read — 두 소비자 공유 |
| `interview-method.md` | `/interview`, `intake-interview` | Lazy Read |

남은 후보(안 만듦): `priority.md`, `escalation.md`, `operator.md`.

### 자동 주입 방식 3가지 — 최종 (도전 2)

| 방식 | 트리거 | 현재 적용 |
| --- | --- | --- |
| `CLAUDE.md` `@import` | 세션 시작 무조건 | **없음** (도전 2에서 제거 — baseline 토큰 절감) |
| 소비자가 `Read` (Lazy) | 그 스킬·에이전트가 돌 때 | `team-capability`, `classification-policy`, `sizing`, `dod-patterns`, `interview-method`, `capacity` |
| **훅 (PreToolUse additionalContext)** | `Write`/`Edit` 툴 실행 직전 (세션당 1회) | `style.md` (`.claude/hooks/inject-style-context.sh`) |

---

## 3. 커밋 계획

지금 staged 12개를 논리 단위로 나눠 커밋:

1. `feat: .claude/context/ 운영 지침 컨텍스트 레이어 신설` — context/ 4파일 + capacity.md
2. `refactor: classifier·intake-interview 판단기준을 context 파일 참조로 전환` — agents/ 2개 + intake/SKILL.md
3. `feat: /interview 스킬 추가` — skills/interview/
4. `docs: context 레이어 문서화` — CLAUDE.md · .claude/README.md · maintenance/README.md

---

## 갱신 이력

- 2026-09-07 워크시트 생성. before 측정 대기.
- 2026-09-07 측정 1·2 기입 완료. import 비용 ≈ 940 토큰 산출. `CLAUDE.md` `@import` 줄 복구 확인(step 5 완료).
- 2026-09-07 준비 #0 완료. `team-capability.md` 를 `sandbox/board` 소유팀(Python/Flask/pytest/SQL) 기준으로 채움.
  불일치 정리: `classification-policy.md` §2·§5, `classifier.md` 예시의 `Vue.js` → `Python/Flask` 로 교체.
- 2026-09-07 필수 1 완료. 컨텍스트 3 → 6개 (`sizing.md`·`dod-patterns.md`·`style.md` 신규).
  배선: `style.md` → `CLAUDE.md` `@import`. `sizing.md` → `classifier.md` Read 목록.
  `dod-patterns.md` → `spec/SKILL.md` §2 + `spec-reviewer.md` 절차·체크리스트 #1.
  `context/README.md` 의존 표 갱신.
- 2026-09-07 커밋 3개로 정리 후 `origin/step2` 푸시 (7925c7f·2edf42c·21fb5da).
- 2026-09-07 필수 2 완료. `classifier` A/B **3라운드** → `day2-ab-injection-test.md`.
  · 라운드 1·2 (모바일 포팅 / 사내 SSO): label 일치하나 신뢰도·인용·판단 경로·규모 차이.
  · 라운드 3 (React SPA 대시보드): **label 갈림** — A=outsource(team-capability "SPA 안 함"), B=internal(일반 상식).
  `sizing.md` 가 A·A2·A3 세 번 모두 `적용한 기준` 에 인용됨 → 필수 1 배선 실사용 확인.
- 2026-09-07 필수 3 완료. `day2-context-map.md` — Mermaid 도식(파일→주입방식→소비자) +
  트리거 표 + 활용 검증 루프 + 필수 2 검증 결과. 필수 3개 모두 완료 (도전 1·2 남음).
- 2026-09-07 필수 2 보강. `skill-creator@claude-plugins-official` 설치 후 `/spec ± dod-patterns.md`
  스킬 레벨 A/B: assertion 100% vs 95%, 블라인드 comparator **3/3 컨텍스트 O 승**(격차 +1~+3점),
  비용 실행당 토큰 +4.3k. `day2-ab-injection-test.md` 에 "스킬 레벨 정량 비교" 절 추가.
- 2026-09-07 도전 1 완료. `.claude/scripts/check-context-wiring.sh` — 의존 표 SSOT 기준
  파일 존재/@import/Lazy 참조/훅/고아 파일/죽은 지침 검사. 16건 PASS, WARN 1(§N 인용 0회).
- 2026-09-08 도전 2 완료. `CLAUDE.md` `@import` 2줄 제거 → `style.md` 는 PreToolUse(`Write`/`Edit`) 훅
  주입(`inject-style-context.sh`, 세션당 1회), `team-capability.md` 는 Lazy Read 로 전환.
  세션 시작 baseline 에서 운영 지침 @import 0. 예상 절감 ≈ 1,850 토큰/세션 (실측은 `/context` 로 기입).
  배선 검증 17건 PASS. 이제 자동 주입 3가지(항상로드 제외 → Lazy + 훅) 실증 완료.
  `day2-context-map.md` 도식·표 갱신.
