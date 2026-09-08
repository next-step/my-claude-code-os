---
month: 2026-09
team_maint_mm:
  total: 0.0        # 이번 달 팀에 배정된 유지보수 공수 (M/M)
  used: 0.0
vendors: {}         # 예: { 회사A: { contracted_mm: 2.0, used_mm: 1.7 } }
updated: 2026-09-02
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

## 아직 비어 있음

`total` / `vendors` 가 0 또는 비어 있으면 캐파 룰(§2)은 적용되지 않고
분류는 스택·규모 기준으로만 이뤄진다. 실제 숫자를 채우면 그때부터 룰이 살아난다.

## 갱신 이력

- 2026-09-02 파일 생성 (값 미입력)
