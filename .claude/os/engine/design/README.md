# 메인 홈 — 디자인 캔버스 작업 파일

로컬 서버(레포 맨 위의 `serve.sh`)가 그리는 화면의 **작업 파일**이다. 발행된 캔버스는 이 파일들에서
매번 새로 씨앗을 심어 만든다. 실제로 도는 화면은 `engine/scripts/serve_reports.py`이고,
여기 있는 것은 그 화면을 손으로 만져 보기 위한 사본이다.

| 파일 | 무엇 |
|---|---|
| `Main.dc.html` | 홈. 배너 하나와 메뉴 셋 (GT 개선 · 정책 보기 · 정책 개선) |
| `Policy.dc.html` | 정책 보기. 보고서가 없던 자리라 이 캔버스에서 처음 그렸다 |
| `canvas.json` | 아트보드 둘의 배치 |

## 다시 올리는 법

```bash
node "<design skill 경로>/seed-canvas.mjs" \
  --template "<design skill 경로>/payload.template.html" \
  --out catalog-os-home.html --title "Catalog OS 홈" \
  --artboard Main.dc.html --artboard Policy.dc.html --canvas canvas.json
```

## 이 캔버스의 숫자는 표본이다

아트보드에 박힌 `26`·`93`·`12`는 2026-09-06 실행 하나에서 손으로 옮긴 값이고,
**다시 세지 않는다.** 진짜 화면은 요청마다 `run-summary.json`·`run-review.json`·
`policy-index.json`을 다시 읽는다. 캔버스에서 숫자를 고쳐도 서버는 바뀌지 않는다 —
반대도 마찬가지다. 형태를 정하는 것이 이 파일들의 일이고, 세는 것은 서버의 일이다.

## 톤을 여기서 가져왔다

`attributes/<속성>/design/`의 GT 정정 후보 캔버스와 같은 팔레트다 — 순흑백, 라운딩 0,
액센트 하나(`#D62300`), Archivo + Gothic A1 + IBM Plex Mono. 보고서 CSS에서 가져온 것은
**형태 마크**다. 귀책을 색이 아니라 형태로 구분하는 `.mark`(■ GT · □ 정책 · ◤ 열림)를
메뉴의 기호로 그대로 썼다. 색맹에도, 인쇄해도 남는다.

## 왜 엔진 아래에 있나

홈은 어느 속성에도 속하지 않는다 — 속성을 훑어서 목록을 만드는 화면이라 엔진의 것이다.
아트보드에 실린 속성 이름과 라벨은 표본 값일 뿐이고, 서버 코드에는 그 어휘가 없다.
`test_package_boundary`가 `engine/scripts`를, `test_serve`가 «이름 모르는 속성 하나로도
네 화면이 뜬다»를 확인한다.
