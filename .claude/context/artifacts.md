# 산출물 스키마 (artifacts) — 스킬 간 데이터 계약

모든 산출물은 `demo-app/screenshots/<target>/` 아래. 스킬들은 이 스키마로 읽고 쓴다(임의 필드 추가 금지 — 갤러리 빌더가 파싱한다).

```
screenshots/<target>/
  <id>.png              변형 스크린샷 (capture-variants)
  measurements.json     코드 사실 측정 (capture-variants)
  ai-notes.json         AI 판정 기록 (visual-check 작성, visual-confidence 가 다수결로 level 갱신)
  confidence.json       반복 판정 안정성 결과 (visual-confidence 작성)
  lens.json             관점별(레이아웃·색대비·타이포) 정밀 진단 결과 (visual-lens 작성)
  index.html            검증 갤러리 (build-gallery)
  baseline/             기준선 스냅샷 (snapshot-baseline; <id>.png + measurements.json)
  diff/<id>.png         바뀐 변형의 픽셀 diff (regress-diff)
  regress.json          회귀 결과 (regress-diff 작성, 스킬이 verdict 머지)
```

## measurements.json — 배열, 변형당 1객체
`id`·`label`·`expected`(채점용 정답, 판정에겐 블라인드)·`image`·`overflowY/X`·`opacity`·`rootBg`(hex)·`minContrast`·`anyOverImage`·`anyTruncated`·`texts[]`(text·truncated·fontSize·color·bg·overImage·contrast)·`flags[]`(코드가 단정한 깨짐 — overflow만)·`notes[]`(사실 메모)·`level`(코드 판정 — overflow 없으면 항상 ok)

## ai-notes.json — 변형 id → 판정
```json
{ "<id>": { "level": "ok|warn|error", "note": "<visual-judge 한 줄 근거>" } }
```

## lens.json — 변형 id → 관점별 판정 (visual-lens)
```json
{ "<id>": { "lenses": { "layout": {"level":"ok|warn|error","note":"<근거>"},
                        "color":  {"level":"…","note":"…"},
                        "typo":   {"level":"…","note":"…"} },
            "overall": "ok|warn|error" } }
```
- `overall` = 세 렌즈 중 **최악**(error>warn>ok). 렌즈는 공유 `visual-judge` 를 각도만 좁혀 재사용한 결과다(블라인드·독립).
- 색 렌즈는 대비·가독성까지만 — 고립·균일 절대 색차는 못 잡음(measurements.json 몫).

## regress.json
```json
{ "target", "total", "changedCount",
  "results": [ { "id", "changed", "dimensionMismatch", "diffPixels", "diffPercent", "diffImage",
                 "newVariant?", "reason?" } ] }
```
- `visual-regress` 스킬이 changed 항목에 `verdict`(same|expected|unexpected)·`note`를 **머지**해 다시 쓴다.
- `newVariant: true` = baseline 이후 추가된 변형(비교 불가) → comparator 가 아니라 **visual-judge 절대 판정**으로 라우팅, verdict 대신 level 을 머지.
- 노이즈 문턱(diffPercent) 미만은 changed=false — 안티앨리어싱 수준은 회귀 아님.

## 원칙
- 코드 층은 **사실만** 적는다(판정 금지, overflow 단정만 예외). 판정은 ai-notes/verdict 필드에만 산다.
- 산출물은 재생성 가능(레지스트리+무대에서 다시 촬영) — 지워도 복구된다. 유일한 예외는 baseline(과거 시점 기록).
