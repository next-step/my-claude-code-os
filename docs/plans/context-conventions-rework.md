---
topic: context-conventions-rework
status: 완료
source: docs/interviews/2026-07-08-os-docs-overhaul.md (Q9·I2·기계적 적용) + 2026-07-08-daily-trading-loop.md (F3)
---

# 컨텍스트 규약 재정비 (record-conventions 재작성 외)

## 목표
새 루프 기록물·데이터 소스·용어 기준을 컨텍스트 파일에 반영한다. 끝나면 record-conventions가
새 기록 토폴로지로 통째 다시 쓰였고, data-sources·market-glossary에 새 소스·용어가 더해졌고,
새 루프 회고용 빈 lessons 파일이 생겼고, check_context.py가 새 파일 집합을 검증한다.

## 범위
- 포함:
  - **record-conventions.md 재작성(I3·Q9)**: 옛 기록 3종(분석·선정·회고) 서술 폐기, 새 루프 기록물 기준으로 통째 재작성 — 아침 브리핑(append 로그)·투자계획서(살아있는 문서, 제자리 갱신)·포트폴리오 상태(상태 제자리 갱신)·위원회 회의록(append 로그, 긴급은 '긴급' 표기)·체결 로그(append). append-only 박제 / 상태(제자리 갱신) vs 사건(로그 append) 분리 공통 원칙은 계승(daily-trading-loop S3·Q11·Q17·Q20·Q27).
  - **data-sources.md 추가(기계적)**: 새 소스 — 뉴스/미국장/거시 웹검색 서브에이전트, 수급(외국인/기관 전일 매매동향), 지수 국면 스크립트. 정성=서브에이전트 / 정량=스크립트 규약은 유지. 공시/DART 제외 유지.
  - **market-glossary.md 추가(기계적)**: 국면 3축(추세·사이클 위치·변동성) 정의, KRX 가격대별 호가단위표.
  - **새 lessons 파일 신설(F3)**: 옛 retro-lessons 삭제(항목 3) 후, 새 루프 회고의 '표본 대기 교훈'을 축적할 **빈** lessons 파일을 신설(옛 교훈 미이관).
  - **check_context.py 갱신(기계적)**: 검증 대상 컨텍스트 파일 집합·소비자 연결을 새 집합으로 갱신. 새 스킬(항목 5~9) 소비자 링크는 존재 전이라 항목 10에서 최종 확인.
- 제외:
  - investor-profile·trading-principles(항목 2). 소비자 목록에서 옛 스킬 제거(항목 3에서 선행).
  - 새 스킬 자체(항목 5~9).

## 구현 단계
1. record-conventions.md를 새 기록 토폴로지로 통째 재작성(소비자=새 루프 스킬).
2. data-sources.md에 뉴스 서브에이전트·수급·국면 스크립트 소스 추가.
3. market-glossary.md에 국면 3축·KRX 호가단위표 추가.
4. 새 빈 lessons 파일 신설(경로·이름 구현 시 확정).
5. check_context.py를 새 파일 집합으로 갱신, 정적 검증 통과 확인(스킬 링크는 항목 10에서 마감).

## 건드릴 파일
- `.claude/context/record-conventions.md` — 통째 재작성.
- `.claude/context/data-sources.md` — 새 소스 추가.
- `.claude/context/market-glossary.md` — 국면 3축·호가단위 추가.
- `.claude/context/<새 lessons>.md` — 신설(빈 파일).
- `scripts/check_context.py` — 새 집합·소비자 연결로 갱신.
