/**
 * yt-dlp 실행 인자를 만드는 순수 함수. **명령을 실행하지 않는다.**
 *
 * `ffmpeg-cmd.js` 와 같은 이유로 배열을 돌려준다 — 검색어와 영상 제목에 따옴표나
 * 달러 기호가 섞여도 셸이 해석하지 않아야 하기 때문이다.
 *
 * 왜 이 모듈이 계획에 없다가 생겼는가: 유튜브가 2025-07-21 에 인기 급상승 페이지를
 * 폐지했다. 공식 API 의 `chart=mostPopular` 는 이제 음악·영화·게임 차트만 돌려주므로
 * 상품이 등장하는 영상을 찾는 데 쓸 수 없다. 그래서 소재를 키워드 검색으로 찾기로
 * 했고, 그 검색을 yt-dlp 가 맡는다.
 */
"use strict";

/** 필드 구분자. 영상 제목에 탭이 들어가는 일은 사실상 없다. */
const FIELD_SEP = "\t";

/** 검색·조회에서 받아 올 항목. 순서가 `discover.js` 의 파싱 순서와 짝을 이룬다. */
const FIELDS = ["id", "duration", "view_count", "channel", "upload_date", "title"];

/** yt-dlp 가 알아듣는 출력 템플릿. */
function printTemplate() {
  return FIELDS.map((f) => `%(${f})s`).join(FIELD_SEP);
}

/**
 * 키워드로 영상을 검색하는 인자.
 * @param {string} keyword 검색어
 * @param {number} limit 가져올 개수
 */
function buildSearchArgs(keyword, limit = 10) {
  if (!keyword || !String(keyword).trim()) throw new Error("검색어가 필요하다");
  const n = Math.max(1, Math.min(50, Math.floor(limit)));
  return [
    "--skip-download",
    "--no-warnings",
    "--no-progress",
    "--ignore-errors",
    "--print", printTemplate(),
    `ytsearch${n}:${String(keyword).trim()}`,
  ];
}

/** 영상 하나의 히트맵만 뽑는 인자. */
function buildHeatmapArgs(videoId) {
  검사(videoId);
  return [
    "--skip-download",
    "--no-warnings",
    "--no-progress",
    "--print", "%(heatmap)j",
    `https://www.youtube.com/watch?v=${videoId}`,
  ];
}

/** 자막(있으면 자동 생성 자막까지)을 내려받는 인자. */
function buildSubtitleArgs(videoId, outputPath, lang = "ko") {
  검사(videoId);
  if (!outputPath) throw new Error("outputPath 가 필요하다");
  return [
    "--skip-download",
    "--no-warnings",
    "--no-progress",
    "--write-subs",
    "--write-auto-subs",
    "--sub-langs", lang,
    "--sub-format", "vtt",
    "-o", outputPath,
    `https://www.youtube.com/watch?v=${videoId}`,
  ];
}

/**
 * 구간만 잘라 내려받는 인자.
 *
 * 영상 전체를 받지 않는 이유는 용량과 시간 때문이다. 10분짜리를 통째로 받으면
 * 수백 MB 인데 실제로 쓰는 것은 1분이 안 된다.
 *
 * `--force-keyframes-at-cuts` 가 없으면 잘린 구간 앞부분이 깨진 화면으로 시작한다.
 */
function buildSectionDownloadArgs({ videoId, startSec, endSec, outputPath, maxHeight = 1080, padSec = 1 }) {
  검사(videoId);
  if (!outputPath) throw new Error("outputPath 가 필요하다");
  if (!Number.isFinite(startSec) || !Number.isFinite(endSec)) throw new Error("startSec 과 endSec 은 숫자여야 한다");
  if (endSec <= startSec) throw new Error("endSec 이 startSec 보다 커야 한다");

  // 앞뒤로 조금 더 받는다. 키프레임 정렬 때문에 경계가 몇 프레임 밀릴 수 있어서다.
  const from = Math.max(0, startSec - padSec);
  const to = endSec + padSec;

  return [
    "-f", `bv*[height<=${maxHeight}]+ba/b[height<=${maxHeight}]`,
    "--download-sections", `*${round3(from)}-${round3(to)}`,
    "--force-keyframes-at-cuts",
    "--merge-output-format", "mp4",
    "--no-warnings",
    "--no-progress",
    "-o", outputPath,
    `https://www.youtube.com/watch?v=${videoId}`,
  ];
}

function 검사(videoId) {
  // 유튜브 영상 ID 는 11자의 영숫자·하이픈·밑줄이다. 형식을 확인해 URL 조작을 막는다.
  if (typeof videoId !== "string" || !/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
    throw new Error(`유튜브 영상 ID 형식이 아니다: ${videoId}`);
  }
}

function round3(n) {
  return Math.round(n * 1000) / 1000;
}

module.exports = {
  buildSearchArgs,
  buildHeatmapArgs,
  buildSubtitleArgs,
  buildSectionDownloadArgs,
  printTemplate,
  FIELD_SEP,
  FIELDS,
};
