# 쇼츠 자동 편집 파이프라인

유튜브 영상에서 시청자가 가장 많이 다시 본 구간을 찾아 세로형 쇼츠로 편집하고, 쿠팡 파트너스 제휴 링크가 담긴 업로드용 문구까지 만듭니다. 업로드는 사람이 직접 합니다.

외부 자격을 발급받는 방법은 [SETUP.md](SETUP.md)에 있습니다. **쿠팡 API 키는 가입만으로 받을 수 없습니다.** 그 사정도 SETUP.md에 적어 두었습니다.

## 사전 준비

```bash
brew install yt-dlp                      # 검색·히트맵·자막·구간 다운로드
```

ffmpeg는 Homebrew 것을 쓰지 않습니다. Homebrew의 ffmpeg 9.0.1에는 `drawtext`와 `subtitles` 필터가 없어 자막과 출처 표기를 입힐 수 없습니다. 대신 정적 빌드를 프로젝트 안에 둡니다.

```bash
mkdir -p ventures/coupang-shorts/tools
cd ventures/coupang-shorts/tools
curl -L -o ffmpeg.zip https://evermeet.cx/ffmpeg/ffmpeg-9.0.1.zip
unzip -o ffmpeg.zip && rm ffmpeg.zip && chmod +x ffmpeg
./ffmpeg -filters | grep -E " (drawtext|subtitles|ass) "   # 세 줄이 나와야 합니다
```

## 실행

기본이 dry-run입니다. 실제로 돌리려면 `--go`를 붙입니다.

```bash
# 전체 (설정된 검색어로 하루치)
node ventures/coupang-shorts/bin/run.js --go

# 한 편만
node ventures/coupang-shorts/bin/run.js --go --video 5GTAp_RMEHc

# 단계별로
node ventures/coupang-shorts/bin/collect.js  --go --keyword "무선청소기 추천"
node ventures/coupang-shorts/bin/analyze.js  --go --video <영상ID>
node ventures/coupang-shorts/bin/monetize.js --go --video <영상ID>
node ventures/coupang-shorts/bin/render.js   --go --video <영상ID>
```

결과는 `runs/<날짜>/<영상ID>/`에 쌓입니다. `short1.mp4`부터 `short3.mp4`까지가 업로드할 영상이고, `meta.json`에 제목과 설명이 들어 있습니다. 이 디렉터리는 커밋되지 않습니다.

## 네 단계

| 단계 | 스크립트 | 하는 일 | 산출물 |
|---|---|---|---|
| 1 | `collect.js` | 키워드로 검색해 후보를 거르고 점수를 매깁니다 | `candidates.json` |
| 2 | `analyze.js` | 히트맵과 자막을 받아 구간을 고릅니다 | `plan.json`, `seg*.srt` |
| 3 | `monetize.js` | 검색어를 뽑아 상품을 찾고 제목·설명을 만듭니다 | `meta.json` |
| 4 | `render.js` | 구간만 내려받아 세로형으로 렌더합니다 | `short*.mp4` |

수익화가 렌더보다 먼저입니다. 화면에 박을 타이틀 문구를 수익화 단계가 만들기 때문입니다.

## 구조

판정과 계산은 `lib/`의 순수 함수가 하고, 파일과 네트워크와 외부 명령은 `bin/`이 맡습니다. 이 저장소의 기존 관례(`.claude/lib`와 `.claude/tests`)를 그대로 따릅니다.

```
lib/         순수 함수 — 부작용 없음, 시간과 네트워크를 주입받음
  discover.js      검색 결과를 후보로 거르고 점수를 매김
  heatmap.js       yt-dlp 히트맵 정규화, 결측 판정
  segment.js       쇼츠 구간 선정 (핵심 알고리즘)
  subtitle.js      자막 파싱, 구간 잘라내기, 경계 스냅
  keyword.js       상품 검색어 추출
  coupang.js       HMAC 서명, 검색 응답 파싱
  budget.js        시간당 호출 한도와 캐시 판정
  ytdlp-cmd.js     yt-dlp 인자 생성
  ffmpeg-cmd.js    ffmpeg 실행 계획 생성
  publish-meta.js  설명·고지·출처 생성
  shorts-title.js  원본 제목에서 훅을 뽑아 쇼츠 제목 생성
bin/         실행 계층 — 여기서만 부작용을 냄
config/      설정 (커밋됨)
tests/       모듈 하나당 테스트 하나
fixtures/    실제 응답을 한 번 떠서 고정한 표본 (커밋됨)
runs/        실행 산출물 (커밋 안 됨)
tools/       정적 ffmpeg (커밋 안 됨)
```

## 테스트

파일을 직접 지정해 돌립니다.

```bash
node --test ventures/coupang-shorts/tests/segment.test.js
for f in ventures/coupang-shorts/tests/*.test.js; do node --test "$f"; done
```

네트워크와 파일 시스템을 주입으로 대체하므로 외부 자격 없이 전부 통과합니다.

## 실제로 돌려 보고 알게 된 것

계획 단계의 전제 가운데 여러 개가 틀렸고, 전부 코드를 돌려 보고서야 드러났습니다. 같은 함정을 다시 밟지 않도록 적어 둡니다.

- **인기 급상승 페이지는 없어졌습니다.** 유튜브가 2025년 7월 21일에 폐지했고, 공식 API의 `chart=mostPopular`는 이제 음악·영화·게임 차트만 돌려줍니다. 상품이 등장하는 영상을 거기서 찾을 수 없어 키워드 검색으로 바꿨습니다.
- **히트맵은 공식 API에 없습니다.** yt-dlp가 플레이어 내부 응답에서 긁어 오는 값이라 유튜브가 구조를 바꾸면 사라집니다. 값이 나오지 않는 영상도 있어서, 그때는 이유를 적고 건너뜁니다.
- **유튜브 자동 생성 자막은 평범한 VTT가 아닙니다.** 큐마다 앞 줄이 통째로 반복되고 10밀리초짜리 빈 큐가 끼어 있습니다. 그대로 파싱하면 같은 문장이 세 번씩 찍힙니다. 실제 파일에서 큐 817개가 409개로 정리됩니다.
- **한글 폰트를 지정하지 않으면 글자가 깨집니다.** `drawtext`에 `fontfile`을 주지 않으면 ASCII만 찍히고 한글 자리에 네모가 들어갑니다. 종료 코드는 0이라 렌더된 화면을 눈으로 보기 전까지 드러나지 않습니다.
- **libass는 화면 픽셀이 아니라 자체 좌표계를 씁니다.** 자막 파일에 `PlayResY`가 없으면 높이 384를 기준으로 잡고 영상 높이에 맞춰 통째로 확대합니다. 1920 화면이면 5배입니다. 이것을 모르고 값을 주면 글자가 5배로 커지고 자막이 화면 맨 위에 붙습니다.
- **쿠팡 API 키는 가입만으로 받을 수 없습니다.** 누적 판매 15만 원을 넘겨 최종 승인을 받아야 발급 버튼이 열립니다. 그전까지는 링크를 손으로 만들어야 합니다.

## 쿠팡 파트너스 표기 규정

공식 안내 「[초보자 활동 가이드] 유튜브 활동 시 유의사항」이 요구하는 세 가지입니다. 지키지 않으면 최종 승인에서 반려됩니다. 자세한 내용은 [SETUP.md](SETUP.md)에 있습니다.

| 규정 | 파이프라인이 하는 일 |
|---|---|
| 설명란에 대가성 문구 | `publish-meta.js`가 자동으로 넣습니다 |
| 문구가 '더보기'에 가려지지 않게 | 고지를 설명 **맨 앞**에 둡니다 |
| 영상 제목이나 영상 안에도 광고 표시 | 화면 좌측 상단에 '유료광고 포함' 배지를 영상 내내 띄웁니다 |

세 번째가 가장 놓치기 쉽습니다. 가이드가 반려 사례로 드는 것이 정확히 "설명란에는 적었지만 영상에는 표시하지 않은 경우"입니다. 배지는 설정으로 끌 수 없게 만들어 두었고, 경로를 빠뜨리면 렌더 계획 자체가 만들어지지 않습니다.

**업로드할 때 유튜브의 '유료 프로모션 포함' 체크박스는 직접 켜 주셔야 합니다.** 파이프라인이 대신 할 수 없습니다.

## 위험

이 파이프라인은 **다른 사람의 영상을 잘라 재업로드합니다.** 사용자가 위험을 인지하고 선택한 방식입니다.

유튜브의 재사용 콘텐츠 정책은 2025년 7월부터 강화되어 단순 편집물의 수익 창출을 거부하며, 저작권 경고가 3회 누적되면 채널이 삭제됩니다. 파이프라인에 넣은 완화 장치는 출처 표기 번인, 자막 추가, 타이틀 번인뿐이고, 이것들이 위험을 없애지는 못합니다.
