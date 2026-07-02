# 작업 규칙 (실습 메타)

1. 클로드 OS 관련 모든 파일(예. .claude 하위 md)은 반드시 프로젝트 안에 만들 것
2. 클로드 OS 만들기 실습 중이기 때문에 대화 과정에서 AI와의 협업을 배울 수 있도록 양질의 설명 제공할 것

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
- **스킬**: `commit` · `orchestrate` · `handoff` · `contract-check` · `skill-stat`
- **훅**: `skill-usage-log`(Pre, 스킬 통계) · `decision-log`(Post, OS.md 변경 → `DECISIONS.md`)

## 어디를 읽을지 (컨텍스트 이정표)

- **지금 뭘 해야 하나(현황·다음 할 일·블로킹) → `STATUS.md`** (작업 시작 시 먼저 확인, 끝나면 갱신)
- **청사진이 언제 바뀌었나(결정 이력) → `DECISIONS.md`** (기획 결정 전 확인, "왜"는 OS.md 본문·커밋 참조)
- 계약·구현 규약 → **OS.md 12장**
- 백엔드(시스템 구성·수집 폴백) → **OS.md 7·12장**
- 프론트(핵심 기능·사용자 흐름) → **OS.md 5·6·12장**
