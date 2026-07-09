---
name: m-tdd
description: 파이프라인 외부 독립 TDD 진입점 — 언어·런너를 자동 감지한 뒤 tdd 오케스트레이터 에이전트에 위임해 Red-Green-Refactor 사이클을 완주한다. 기존 /m-* 파이프라인과 별개로 빠른 TDD가 필요할 때 사용.
---

# /m-tdd — 독립 TDD 사이클

기존 `/m-spec → /m-plan → /m-build` 파이프라인의 축소판. 스펙 문서나 phase 마커 없이, 요구사항 한 줄에서 바로 Red-Green-Refactor 사이클을 돌린다.

## 실행 순서

1. **언어·런너 자동 감지** — 프로젝트 루트를 살펴 런너를 결정한다.
   | 신호 파일 | 언어 | 런너 |
   |-----------|------|------|
   | `build.gradle(.kts)`, `pom.xml` | Kotlin/Java | `./gradlew test` |
   | `pytest.ini`, `pyproject.toml`, `setup.py` | Python | `pytest -v` |
   | `package.json` (test 스크립트) | TS/JS | `npm test` |

   감지 실패 또는 모호 시 사람에게 런너를 물어본다.

2. **tdd 오케스트레이터 스폰** — 요구사항 + 감지된 런너 + 인터페이스 스케치(있으면)를 전달한다. 오케스트레이터가 내부적으로:
   - `tdd-test-writer` → RED 확인 (러너 출력 전문)
   - `tdd-implementer` → GREEN 확인 (러너 출력 전문)
   - `tdd-refactor` → GREEN 유지 리팩터

3. **결과 보고** — 오케스트레이터의 최종 출력(RED/GREEN/REFACTOR 요약 + 러너 출력 전문)을 사람에게 전달한다.

## 헌법 요약

- H1: 러너 출력 전문만이 검증 근거. 각 단계는 러너 출력 없이 완료 선언 불가.
- H2: tdd-test-writer 는 프로덕션 코드를 보지 않고, tdd-implementer 는 test-writer 컨텍스트를 참조하지 않는다.
- H3: RED 테스트는 implement·refactor 동안 read-only.

## 파이프라인과의 차이

- `/m-build` 는 phase 마커·test-guard 훅·verifier 감사·커밋 게이트를 포함한 **정식 파이프라인 출구**다.
- `/m-tdd` 는 그런 게이트 없이 빠르게 사이클만 도는 **경량 진입점**이다. 커밋은 사람이 직접 판단한다.
