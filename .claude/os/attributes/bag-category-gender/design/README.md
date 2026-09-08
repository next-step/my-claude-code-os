# GT 정정 후보 — 디자인 캔버스 작업 파일

무신사 스토어프론트 톤(순흑백·큰 타이포·라운딩 0·액센트 하나)으로 다시 짠 GT 정정 후보
리포트의 **작업 파일**이다. 발행된 캔버스는 이 파일들에서 매번 새로 씨앗을 심어 만든다.

| 파일 | 무엇 |
|---|---|
| `build_artboard.py` | `gt-rows.json`을 읽어 `Main.dc.html`을 짓는다. 손으로 고치는 것은 이쪽 |
| `Main.dc.html` | 생성물. 아트보드 한 장 (필터·검색·사진 확대 동작) |
| `canvas.json` | 캔버스 배치. 아트보드 하나, `expand: fill`, `print: flow` |
| `gt-rows.json` | `reports/gt-fixes.html`의 임베드 데이터에서 뽑은 제안 11건 |

## 고치고 다시 올리는 법

```bash
python3 build_artboard.py && \
node "<design skill 경로>/seed-canvas.mjs" \
  --template "<design skill 경로>/payload.template.html" \
  --out gt-jeongjeong-hubo.html --title "GT 정정 후보" \
  --artboard Main.dc.html --canvas canvas.json \
  $(for f in small/*.jpg; do printf -- "--image %s " "$f"; done)
```

**증거 사진은 여기 없다.** 캔버스는 외부 이미지를 못 불러와 전부 안에 박아야 하는데
48장이 1.1MB라 저장소에 두지 않았다. `gt-rows.json`의 `plate[].url`에서 다시 받아
`sips -s format jpeg -s formatOptions 68 -Z 560`으로 줄이면 같은 것이 나온다.
받은 것은 `role == "TARGET"`이거나 `cited == true`인 것만이다 — 113장 전부는 너무 무겁다.

## 머리에 아무것도 두지 않는다

제목 다음이 바로 필터이고, 그 다음이 제안이다. 사용자가 2026-09-06 편집기에서 두 번에
걸쳐 지웠다.

| 저장 | 지운 것 |
|---|---|
| 1차 | 눈썹 라벨 `GT REVIEW — 가방 · 대상 고객 성별`, 상단 요약 4칸(고치자는 제안·인용된 장면·현재 GT 출처·소스가 갈린 건) |
| 2차 | 머리말 문단 전체 ("원장에 반영하지 않았다 … 이 화면은 GT만 묻는다 … 근거 표시가 붙은 장면이 …") |

이유는 한 마디였다 — **"쓸데없는 정보"**. 이 화면이 묻는 것은 **"이 GT가 틀렸나" 하나뿐**이고,
리포트 자신을 설명하는 말과 리포트 자신을 세는 숫자는 그 답에 기여하지 않는다.

남은 것: 필터 칩의 개수(무엇을 먼저 볼지 고르는 데 쓰인다)와 「근거」 표시(뜻풀이 문장은
함께 사라졌지만 표시 자체로 읽힌다).

되돌리지 마라. 다시 넣고 싶으면 먼저 "이것이 어떤 판정을 바꾸는가"에 답해야 한다.

## 이 톤을 고른 이유와 대가

사용자가 사내 CUVE Admin 대신 커머스 브랜드 톤을 골랐다. 대가는 하나다 —
`products-cuve/admin`의 `review-hub`(사람 판정 UI)와 나란히 놓으면 다른 제품처럼 보인다.
어드민 안에 넣을 계획이 생기면 그때 다시 정해야 한다. 사내 시스템의 토큰과 원칙은
`core-catalog-platfom/products-cuve/admin/design.md`에 있다.
