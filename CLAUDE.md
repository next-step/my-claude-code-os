# my-claude-code-os

Assignment repository for the 4-week course "나만의 Claude OS 만들기" (Build Your Own Claude OS). Each week: build skills, subagents, hooks, and orchestrators, then open a PR from a personal branch for review.

## This repository is public

The course is unrelated to the company. The OS is meant to be published; company code is not.

`php_legacy/`, `cs-system/`, and `cs-e2e/` live inside this directory and are gitignored. They must stay that way — the first two are company repositories, and `cs-e2e/` is a local repository this OS owns whose config carries internal hostnames.

- Never move content from those three into a tracked file of this repository. This covers code as well as internal domains, issue IDs, and people's names.
- Never commit logs or reports produced by running the OS against company code.

The rule in full, and what a placeholder looks like instead, is `.claude/context/team-boundary.md`.

## Working rules

1. Every Claude OS file (e.g. markdown under `.claude/`) must live inside this project.
2. Write skills (`SKILL.md`) in English. The frontmatter `description` stays Korean — it carries the Korean phrases that trigger the skill.
3. This is a hands-on course. Explain the reasoning while working, so the collaboration itself is something to learn from.

## The OS in this repository

A migration OS: it moves the backend half of a legacy PHP service into Spring/Kotlin one page at a time, and proves two separate things about each page — that behavior did not change, and that the domain logic actually moved.

Those need two different checks. An equivalence check answers the first. It cannot answer the second, because when PHP still computes a rule and the backend is never asked, the observable outcome is identical and every check stays green. So a page is done only when equivalence is green **and** a completeness pass says every domain rule left PHP.

두 검증을 같은 높이에 두는 것이 **페이지마다 하나인 교체 지점 함수**다. 동등성은 그 함수 안의 **이중 실행**(레거시 본문과 새 백엔드를 둘 다 실행해 비교하고, 화면에는 언제나 레거시 값을 돌려준다)과 PHP 내부 리팩터를 지키는 **기준 캡처**가 답한다. 완전성은 **구조 린트 · 본문 해시 고정 · 호출자 전수 · 필드 대조**가 먼저 답하고, 배치 판정자에게는 분류와 배치의 판단만 남는다. e2e 는 스모크다.

정적 검사는 각각 한 층만 보므로 층이 하나 생기면 사각지대가 하나 생긴다. v1 은 규칙이 교체 지점 위에 있어서, v2 는 규칙이 백엔드에 있는데 어댑터가 그 필드를 요청하지 않아서 실패했다. **v3 는 층에 무관한 검사를 더한다** — `migrated` 모드에서 래퍼의 레거시 반환값을 가짜값으로 바꿔도 화면이 그대로면 그 값은 백엔드에서 왔다.

Both checks point at the same **behavior rules**: 페이지가 지키는 규칙의 목록이고, v3 부터 **JSONL 한 줄이 규칙 하나**다. 행마다 분류(도메인 / 화면 / 경계)·출처·줄 범위·필요 입력·관찰·이관 상태·승인이 있고 **열마다 주인이 하나**다. 계약은 `.claude/context/rules-contract.md`, 포맷 정본은 `.claude/skills/legacy-migrate/references/rules-format.md`. 도메인 문서도 이 규칙 목록에서 나온다 — 그래서 그 문서가 계속 참인 것이고, 그것이 별도 프로젝트가 아니라 작업의 부산물인 이유다.

**v3 는 축소다(2026-09-11).** 축소된 것은 저장소가 아니라 **모델이 매 턴 읽는 지시문의 중심**이다 — 오케스트레이터 스킬이 323줄에서 159줄로 줄고, 그 자리를 결정적 코드와 그 코드의 자기검사가 받았다(실측은 설계 문서 1.6장). 회차 길이의 원인이 페이지 크기가 아니라 Phase 일정에 박힌 고정 비용임을 확인하고, 작업 단위를 **교체 지점 함수 하나(페이지 하나)** 로 내렸다. 비싼 산출물(설계·도메인 문서)은 **영역 단위 살아있는 문서**가 되어 여러 페이지가 나눠 쓰고, 기계 절차는 `pagecheck` 와 `state.json` 이 진다. 그리고 회차가 회차를 가르치는 장치가 들어왔다 — **근거를 인용한 역할별 학습 기록**과 **사람이 diff 로 승인하는 컨텍스트 변경분**. 근거 없는 자기 반성은 작업 환경을 나쁘게 만든다는 측정이 그 규칙의 이유다. **그 장치의 단위를 페이지 완주에서 추가 회차 하나로 내린 것이 원인 루프다(D-38, 2026-09-15)** — 다섯 루프 중 하나가 한 바퀴 더 돌 때마다 닫힌 어휘에서 이유를 하나 받고(`pagecheck --round`), `causestats` 가 같은 이유 3회를 찾으면 상한·지시문·검사 중 하나의 변경분이 나온다. 회차 하나가 12시간이라, 페이지 완주에 묶인 장치는 설계 나흘째까지 한 번도 돌지 않았다. 검토 근거는 `docs/reviews/2026-09-11-os-shape-review.md`, 설계는 `docs/legacy-migration-os.md` 1.6장.

| 스킬 | |
|---|---|
| `legacy-migrate` | 오케스트레이터. Phase 0–7, 루프 5개와 그 위의 원인 루프, 사람이 멈추는 곳 3개(추출 계획 승인 · **묻는 단계 2.5** · 설계 승인), 자동 검사 2개 |
| `page-picker` | 다음에 옮길 페이지 선정. **두 걸음** — 아홉 기준으로 순위를 내고 멈춘 뒤, 사람이 지목한 한둘에만 기능 설명서 (호출자 전수는 영역 API 설계의 입력이다) |
| `page-baseline` | 화면 HTML 기준 캡처·비교 |
| `dual-run` | 교체 지점 이중 실행 배선과 불일치 보고 |
| `domain-leftover` | 도메인 로직이 화면에 남아있는지 완전성 판정 (페이지별 / 표면 훑기) |
| `domain-doc` | 규칙 목록 → 기획자·운영자용 도메인 문서 |
| `local-stack` | 로컬 스택 기동과 마이그레이션 토글 제어 |
| `e2e-run` | 표면 스모크(페이지 기동·토글 되읽기). 동등성 판정은 `dual-run` 이 한다 |
| `php-legacy-io` | 레거시 파일 읽기·검색·편집·문법 검사 (인코딩이 파일마다 다르다) |
| `php-legacy-trace` | 이름이 어디서 정의되는지 추적 (이 언어에는 선언 문법이 없다) |
| `php-legacy-map` | 디렉터리·서비스·런타임 지도의 판독 규칙 |

| 서브에이전트 | Phase |
|---|---|
| `php-feature-explainer` | 선정 — 지목된 후보 하나의 기능 설명서. 문장마다 출처와 확인·추론 표시. **파일을 만들지 않는다** — 최종 응답이 곧 설명서이고, 그래서 300단어 상한에서 벗어나는 유일한 역할이다 |
| `php-swap-extractor` | 1 — 교체 지점 추출 (계획 / 추출 두 모드) |
| `php-behavior-analyst` | 2 — 규칙 목록(JSONL). 커버리지는 행의 `range` 열이다 |
| `php-rule-recheck` | 2 — 규칙 목록 반증. **v3 에서 기본 0 라운드**이고 근거가 있을 때 켠다 |
| `observation-author` | 2 — 행의 `fixture` → 기준 관찰 목록, 규칙 목록 `obs` 열 |
| `domain-scribe` | 2.5 · 7 — 규칙 목록을 도메인 문서로 옮긴다(**문장마다 규칙 행 하나, 예외 없음**). 질문 목록 초안도 여기서 나온다. 7 의 호출은 완전성 판정이 행을 실제로 고쳤을 때만 |
| `backend-designer` | 3 — 영역 설계에 대한 **변경분**. 규칙 배치·부재 점검·교정표 |
| `backend-test-author` | 4a — 승인된 행과 교정표만 보고 실패하는 테스트를 먼저 쓴다. 구현은 하지 않는다 |
| `backend-builder` | 4b — Kotlin/Spring 구현 + 실험 스위치·페이지 어댑터 배선 (v3 에서 둘을 합쳤다) |
| `domain-placement-checker` | 6 — 분류·배치 판정 (판정 어휘 여섯의 정본) |

Models are assigned by role: judgment-heavy roles (기능 설명·분석·반증·설계·완전성 판정·구현) run on opus, pattern-following roles (관찰 목록·문서) on sonnet. 오케스트레이터는 에이전트에게 산출물 파일명을 외우게 하지 않는다 — 절대경로를 프롬프트로 넘긴다.

**성장 규칙(v3).** 장치 하나는 관찰된 실패 하나에 대응하고, 설계 정본에 먼저 적히며, **그 장치가 대체하는 산문은 같은 변경에서 지운다.** 구속력 있는 상한은 주입 예산이고(`selftest_budget.py` 가 어떤 소비처도 90% 를 넘지 않는지 본다), 줄 수는 승인 지점이 아니라 냄새다. 상한을 조용히 넘기는 것은 제약을 풀어 green 을 만드는 것과 같으므로, 지울 것이 없으면 규칙을 정본에서 고친다.

The design and the reasoning behind it — decisions, loops, gates, open questions — live in `docs/legacy-migration-os.md`. That document is maintained as the design changes; edit it before changing the skills, not after.

## 목표 수렴 루프 (goal-loop)

마이그레이션 OS 와 별개로 도는 스킬 하나. 정량 목표 하나("E2E 전체 수행 시간을 5분 이하로")를 받아 달성될 때까지 서브에이전트를 라운드마다 교체하며 돌린다. 중심은 **작업하는 쪽과 재는 쪽의 분리**다 — 서브에이전트의 "완료했습니다"는 판정 근거가 아니고, 오케스트레이터가 라운드마다 판정 기준 명령을 자기 손으로 돌려 판정한다.

판정 기준은 다섯 값이다: 측정 명령 · 파싱 · 임계값과 방향 · **불변 조건 명령** · confirm 횟수. 불변 조건이 없는 판정 기준은 만들지 않는다 — 어떤 지표든 가장 싼 해법은 측정 자체를 약화시키는 것이고(스펙 삭제·skip·타임아웃 증가), 지표만 있는 루프는 반드시 그리로 수렴한다.

개선은 프롬프트가 아니라 **라운드 보고**에서 온다. 프롬프트는 라운드마다 동일하고 달라지는 것은 `.claude/loop/<작업>/` 에 쌓인 보고뿐이다. 흐름은 한쪽으로만 간다: 오케스트레이터가 쓴 `state.json` 을 서브에이전트가 읽고, 서브에이전트가 쓴 라운드 보고를 다음 서브에이전트가 읽는다. 오케스트레이터는 라운드 보고를 읽지 않는다. 멈추는 이유는 셋뿐이다(달성·상한·측정 불가 2회 연속). 정체와 회귀는 멈춤이 아니라 다음 라운드가 읽는 정보다.

`.claude/loop/` 는 대상이 회사 코드일 수 있으므로 추적하지 않는다. 오케스트레이터는 `goal-loop`, 서브에이전트는 `goal-criteria-author`(계측 한 번)와 `goal-loop-worker`(라운드마다 새로).

## 도구 · 훅 · 컨텍스트

`.claude/scripts/` 에 도구 열넷. 여섯은 레거시 트리를 답할 수 있게 만들고(읽기·검색·정의 조회·인덱스·왕복 편집·문법 검사), `phpstats` 는 그것들이 실제로 쓰였는지 보고하며, 넷은 v2 의 것이다 — `phpmove`(모양·본문 해시·호출자·**필드 대조**), `htmlsnap`(캡처·비교), `dualrun-report`(불일치 집계), `ctxstats`(주입 계측). 셋은 v3 의 것이다 — `pagecheck`(기계 절차 일곱 단계와 `state.json`·루프 회차·회차의 이유), `ctxevolve`(학습 기록 → 컨텍스트 개정), `causestats`(회차의 이유 → 반복 원인과 지표 셋). **뒤의 둘은 제안만 하고 적용하지 않는다.** 전부 같은 실패를 막으려고 있다: **답을 찾지 못한 도구가 "답이 없다"고 보고하는 것.** 무엇이고 왜인지는 `docs/php-legacy-tooling.md`, 어떻게 부르는지는 `php-legacy-io`·`php-legacy-trace`.

`.claude/scripts/selftest.py` 는 도구·훅·계측과 교차 검사(완전성 판정 어휘 ↔ 라우팅표, 산출물 표 ↔ `artifacts.json`, 실험 헬퍼 상수 ↔ 설정 키, 컨텍스트 주입 대상, 옛 이름 부재)를 한 번에 돌린다. 그중 하나라도 건드렸으면 돌린다. 인자가 없고 검사마다 걸린 시간을 찍는다 — 정확하지만 느린 도구는 우회되고, 그 우회는 로그에 설계 문제처럼 보인다. **설정 없이도 시작한다**: `workspace.json` 이 없으면 환경이 필요한 검사를 없는 키 이름과 함께 건너뛰고, 통과·실패·건너뜀을 세 숫자로 갈라 센다 — 건너뜀은 통과가 아니므로 돌아간 수가 줄면 그 숫자에서 보인다. **그 숫자를 읽는 것은 사람이다**: 이 저장소에 CI 는 없고, 조용히 사라진 검사에는 자기 빨간불이 없다(설계 정본 6장).

Skills and scripts contain no paths, hostnames, ports, table names, or service directory names: they read `.claude/config/workspace.json` (gitignored; `workspace.example.json` is the tracked skeleton), and every path in it points inside this directory, so the OS needs no `--add-dir`. 그 설정을 읽지 못하는 도구는 **좁은 답을 조용히 내지 않고 멈춰서 어느 키가 없는지 말한다.**

훅 다섯이 그 경계와 계측을 강제한다 — `guard-company-content.py`(회사 경로·내용의 스테이징 차단) · `php-encoding-guard.py`(편집 전후 인코딩 대조) · `php-tooling-hook.py`(전용 도구 대 우회, 역할 귀속) · `log-skill-usage.py` · `context-inject.py`(컨텍스트 결정적 주입). 상세는 `docs/legacy-migration-os.md` §6 과 `docs/context-system.md`.

`.claude/context/` 의 파일 일곱은 여러 소비자가 함께 쓰는 판정 규칙이다 — 팀 경계, 레거시 트리 읽는 법, 규칙 목록 계약, 교체 지점 모양, 동등성 검증, 백엔드 아키텍처, 조용한 실패 목록. 프론트매터가 대상 에이전트·스킬·경로를 적고 `context-inject.py` 가 그것을 보고 넣는다. 파일마다 "먼저 이것을 읽어라" 한 줄을 두는 방식과 다른 점은 하나다 — **읽으라는 지시는 읽었다는 보장이 아니다.**
