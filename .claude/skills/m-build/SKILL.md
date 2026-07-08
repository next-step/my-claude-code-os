---
name: m-build
description: 파이프라인 3단계 — implementer 가 테스트를 통과시키고 verifier 가 러너 출력 전문을 감사한다. build 동안 테스트는 read-only(H3). 사람 최종 승인 후 커밋. OS.md §3-3.
---

# /m-build — 테스트를 통과시키고 감사받기

파이프라인 마지막 단계. OS.md §3-3 을 실행한다. **선행 조건: 대응표가 확인되었을 것.**

## 실행 순서

1. **phase 설정 (H3 발동)** — `.claude/phase` 에 `build` 를 쓴다. 이 순간부터 test-guard 훅이 `src/test/**` 쓰기를 차단한다.
   ```bash
   echo "build" > .claude/phase
   ```
2. **implementer 스폰** — 태스크 목록 + 테스트(read-only)를 전달한다. implementer 는 내부 루프로:
   - 구현 → 러너 즉시 실행 → 실패 시 프로덕션 코드만 수정.
   - **동일 실패에 러너 3회 연속 전체 통과 실패 시 → 사람에게 에스컬레이션** (아래 에스컬레이션 처리).
   - 전체 통과(GREEN) 시 러너 출력 전문과 함께 반환.
3. **verifier 스폰** — GREEN 보고를 받아 독립 감사:
   - ① 실행된 테스트 수 = 대응표 테스트 수
   - ② `src/test/**` diff 없음
   - ③ 러너 출력 전문 첨부
   감사 실패 시 사유를 사람에게 보고하고 멈춘다 (H5: 테스트 통과 ≠ 완료).

## 게이트: 사람 최종 승인 (개입 3/3) → 커밋
verifier 감사 통과 + 사람 명시 승인 후에만 커밋한다.

4. **phase 해제** — 커밋 직전에 `.claude/phase` 를 비운다. (commit-guard 가 build phase 커밋을 차단하므로 반드시 해제)
   ```bash
   echo "" > .claude/phase
   ```
5. **커밋** — conventional 형식(`feat: ...` 등). commit-guard 가 형식을 검문한다.

## 에스컬레이션 처리
implementer 가 3회 연속 실패로 멈추거나 verifier 감사가 실패하면:
- `.claude/phase` 를 비운다.
- 실패 상황(러너 출력 포함)을 사람에게 보고한다.
- 사람 지시를 기다린다. 임의로 테스트를 고치거나 하드코딩하지 않는다.

## 헌법 요약
- H1: 러너 출력 전문만이 검증 근거. "통과했습니다" 금지.
- H3: build 중 `src/test/**` read-only (test-guard 강제).
- H5: verifier 감사 통과가 build 출구.
