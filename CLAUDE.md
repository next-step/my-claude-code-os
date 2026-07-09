# 작업 규칙 (실습 메타)

1. 클로드 OS 관련 모든 파일(예. .claude 하위 md)은 반드시 프로젝트 안에 만들 것
2. 클로드 OS 만들기 실습 중이기 때문에 대화 과정에서 AI와의 협업을 배울 수 있도록 양질의 설명 제공할 것
3. 사용자에게 하는 설명은 짧고 쉽게 할 것 — 약어·전문용어를 피하고, 꼭 필요하면 한 번 풀어서 알려준다. 너무 길거나 어려운 설명은 오히려 이해를 방해하므로 핵심만 간결하게 전한다.

---

> 이 파일은 **매 세션·모든 서브에이전트에 자동 로드**되는 유일한 컨텍스트 슬롯이다.
> 그래서 여기에는 *항상 참인 사실*과 *어디를 더 볼지 이정표*만 담고, 세부는 `OS.md`로 넘긴다.
> 단일 진실 출처(SSOT)는 `OS.md`이며, 계약이 바뀌면 OS.md 12장을 먼저 갱신한 뒤 구현한다.

## 이 프로젝트

취업 준비생용 **채용 리서치 웹 서비스 (M1)** — 채용 공고 모아보기 + (이후) 회사 리서치.
전체 청사진: `OS.md`. `.claude/` OS 구성 상세: `README.md`.

## 기술 스택 (OS.md 12.1)

Next.js(App Router) + TypeScript + Prisma + SQLite(M1, 이후 Postgres). 수집은 TS 모듈(`fetch`).

## 실행 명령

```bash
npm run dev        # http://localhost:3000
npm run db:push    # Prisma 스키마 → SQLite 반영
npm run db:seed    # mock 데이터 적재
npm run collect    # 수집 스텁(현재 MockAdapter)
```

## 계약 (가장 중요)

- **공유 타입 단일 출처 = `src/types/contract.ts`**. 프론트는 `@/types/contract` 만 import.
- 계약 세부(Job/JobDTO·Bookmark·UserPreference 스키마, API 8종, 정렬·필터 규약) = **OS.md 12장**.
- 계약을 바꿔야 하면 **OS.md 12장 갱신이 선행**(기획자 권한). 코드가 계약을 벗어났으면 `/contract-check`.

## 현재 상태·제약

- **사람인 공개 API 미승인** → `MockAdapter`로 진행. 이용신청→승인 후 실수집 교체.
- 쿼터: 하루 500콜, 요청당 count ≈ 110. 약관: 재판매·대가 수취 금지(M1 로컬·비상업은 무방).
- 사람인 API는 공고 본문 미제공 → `description`은 보통 null, 프론트는 원문 URL 폴백을 1급 요소로.

## .claude OS 구성 (상세 = README.md)

- **공유 서브에이전트**: `product-planner` / `backend-developer` / `frontend-developer` (셋 다 작업 전 OS.md 확인)
- **스킬·에이전트 목록은 여기 적지 않는다.** `skill-context` 훅이 `.claude/` 를 실시간으로 읽어 주입하므로 손으로 옮겨 적으면 어긋난다.
- **훅**:
  - `status-context`(SessionStart) — `STATUS.md` 전문 자동 주입. **그래서 STATUS.md 는 따로 읽지 않아도 이미 컨텍스트에 있다.**
  - `skill-context`(PreToolUse `Skill` + SubagentStart) — 스킬·에이전트 카탈로그 자동 주입
  - `contract-context`(SubagentStart) — `src/types/contract.ts` 전문을 **개발 에이전트(backend/frontend)에만** 주입(`agent_type` 으로 분기). 그래서 그 둘은 계약 파일을 따로 열 필요가 없다.
  - `decision-log`(PostToolUse `Edit|Write`) — OS.md 변경 → `DECISIONS.md` 에 **바뀐 절 이름**까지 기록. 직전본 스냅샷(`.claude/.os-snapshot.md`, git 무시)과 비교해 알아낸다.
  - `skill-usage-log`(PreToolUse `Skill`) — 스킬 호출을 `.claude/skill-usage.log` 에 한 줄씩 append. `skill-stat` 이 이걸 awk 로 집계한다.
- 이 환경엔 **`jq` 가 없다.** 훅은 `sed` 만으로 작성할 것(`skill-context.sh`·`status-context.sh` 참고).

## 어디를 읽을지 (컨텍스트 이정표)

- **지금 뭘 해야 하나(현황·다음 할 일·블로킹) → `STATUS.md`** (SessionStart 훅이 자동 주입하므로 읽을 필요 없음. **작업이 끝나거나 막히면 갱신할 것.**)
- **청사진이 언제 바뀌었나(결정 이력) → `DECISIONS.md`** (기획 결정 전 확인, "왜"는 OS.md 본문·커밋 참조)
- 계약·구현 규약 → **OS.md 12장**
- 백엔드(시스템 구성·수집 폴백) → **OS.md 7·12장**
- 프론트(핵심 기능·사용자 흐름) → **OS.md 5·6·12장**
