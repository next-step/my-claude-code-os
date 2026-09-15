---
month: 2026-09
team_maint_mm:
  total: 3.0        # 이번 달 팀에 배정된 유지보수 공수 (M/M)
  used: 1.8
vendors:
  테크브릿지: { contracted_mm: 2.0, used_mm: 1.7 }  # 범용 외주 — 특정 시스템 전담 아님 (knowledge/vendors/테크브릿지.md)
  회사A: { contracted_mm: 4.0, used_mm: 2.2 }       # 정산시스템 전담 (knowledge/vendors/회사A.md)
updated: 2026-09-15
---

# 이번 달 유지보수 캐파

> **성격**: 라이브 데이터. 규칙이 아니다 — 판단 규칙은
> [`.claude/context/classification-policy.md`](../.claude/context/classification-policy.md) §2 에 있다.
> **변경 주기**: 매달 1일 갱신 (+ 큰 건 완료 시 수시).
> **읽는 쪽**: `classifier` — §2 캐파 기반 라우팅의 조건 평가

## 쓰는 법

- 위 frontmatter 숫자만 고치면 된다. 본문은 설명용.
- `vendors` 는 시스템별 담당 외주사의 **이번 달 계약 M/M** 과 소진량.
  잔여율 = `(contracted_mm - used_mm) / contracted_mm`
- **`updated` 를 반드시 같이 고칠 것.** 14일 이상 지나면 `classifier` 가
  이 숫자를 믿지 않고 "사람 확인 필요"로 넘긴다.

## 현재 값 (샘플)

- 팀 유지보수 공수: 3.0 M/M 중 1.8 사용 — 잔여 40%.
- `테크브릿지`: 계약 2.0 M/M 중 1.7 사용 — 잔여율 **15%** (< 20%). 담당 시스템 없이 범용 외주로 사용.
  §2 캐파 룰 발동 조건을 충족 — "잔여 20% 미만 + 단순 수정/쿼리 추출"이면 벤더 대신 internal 처리.
- `회사A`: 계약 4.0 M/M 중 2.2 사용 — 잔여율 **45%**. `정산시스템` 전담 — §0 선판정으로 이 시스템
  요청은 캐파와 무관하게 바로 outsource 확정 (§2 룰은 잔여율이 20% 밑으로 떨어져야 의미가 생김).

## 갱신 이력

- 2026-09-02 파일 생성 (값 미입력)
- 2026-09-15 샘플 값 입력 (팀 공수·`테크브릿지`·`회사A` 계약분) — Step 3 시스템 루프를 의미 있는
  데이터로 검증하기 위한 표본
