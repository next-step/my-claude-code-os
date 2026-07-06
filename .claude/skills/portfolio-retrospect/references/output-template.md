# portfolio-retrospect — 출력 템플릿 상세

> SKILL.md 4단계에서 참조하는 출력 골격. 스킬 본문에는 요지만 두고,
> 회고 리포트를 만들 때(실행 시점)만 이 파일을 읽어 형식을 확정한다 — 점진적 공개.

## 4단계 사용자 출력 골격

```
# 📒 회고 리포트  (기준일: YYYY-MM-DD)

## 성적표 (사실)
- 평가 N건: 목표달성 x · 손절 y · 관찰중 z · 평균 실현수익률 ±%
- (종목별 status·실현수익률 표)

## 전문가 토론 요약
- 총 R라운드 (수렴 종료 / 5R 미합의)
- 핵심 쟁점과 어떻게 결론났나 (실력 vs 운 등)

## 합의된 결론
- ...

## 미해결 쟁점 (있으면 — 다음 회고로 이월)
- ...

## 튜닝 제안 (다음 추천/분석 반영 — ⚠️ 실제 수정은 사람 승인)
- [대상 스크립트/문서] 무엇을 어떻게 — 왜

## ⚠️ 유의
- 회고는 과거 예측을 평가할 뿐, 원본 분석의 가격대·근거는 수정하지 않는다.
- 튜닝안은 제안이며, 스크립트 상수/OS.md 의 실제 변경은 사람이 승인 후 반영한다.
```

## 기록 저장 스키마 상세

### (a) 원본 status 갱신 — update_status.py
```
echo '{"updates":[{"file":"data/analyses/...","status":"hit_target"}, ...]}' \
  | python3 .claude/skills/portfolio-retrospect/scripts/update_status.py
```
- 원본 분석파일의 **frontmatter `status:` 줄만** 바뀐다. 진입/목표/손절·근거·본문은 **건드리지 않는다**(예측 박제).
- status_changes(1단계에서 바뀐 종목만)를 넘긴다.

### (b) 회고 리포트 저장 — save_retro.py
```
echo '<조립한 JSON>' | python3 .claude/skills/portfolio-retrospect/scripts/save_retro.py
```
- `data/retros/YYYY-MM-DD-retro.md` 로 append-only 저장(같은 날 재실행은 `-2`,`-3`…).
- JSON 스키마는 `scripts/save_retro.py` 상단 docstring 참고.
- `rounds`·`converged`·`open_issues` 에 토론이 몇 라운드 돌았고 수렴했는지, 미해결 쟁점이 뭔지 정확히 담는다.