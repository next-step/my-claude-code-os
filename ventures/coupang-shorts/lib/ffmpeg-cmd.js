/**
 * ffmpeg 실행 계획을 만드는 순수 함수. **명령을 실행하지 않는다.**
 *
 * 왜 문자열이 아니라 배열로 돌려주는가: 인자를 한 줄짜리 문자열로 만들면 셸이 한 번 더
 * 해석한다. 영상 제목이나 채널명에 따옴표·달러 기호가 섞여 들어오면 명령이 깨지거나
 * 최악의 경우 의도치 않은 명령이 돌아간다. 배열로 넘기면 셸을 거치지 않으므로 그 종류의
 * 사고가 원천적으로 없고, 테스트에서 인자 하나하나를 그대로 비교할 수 있다.
 *
 * 왜 `sidecarFiles` 를 함께 돌려주는가: ffmpeg 의 drawtext 필터에 한글 문구를 직접 넣으면
 * 콜론·따옴표·백슬래시를 전부 이스케이프해야 하는데, 이 이스케이프 규칙이 필터 그래프
 * 안에서 중첩되어 매우 깨지기 쉽다. 그래서 문구를 파일에 적고 `textfile=` 로 가리킨다.
 * 파일을 실제로 쓰는 일은 부작용이라 이 모듈이 하지 않고, "무엇을 써야 하는지"만 알려 준다.
 */
"use strict";

const DEFAULTS = Object.freeze({
  width: 1080,
  height: 1920,
  fps: 30,
  crf: 20,
  preset: "medium",
  audioBitrate: "128k",
  /** "blur" 는 흐린 배경 위에 원본을 얹는다. "crop" 은 가운데를 잘라낸다. */
  mode: "blur",
  blurSigma: 25,
  /**
   * 자막 크기와 위치를 **화면 픽셀로** 적는다. 실제 ASS 값으로는 아래에서 환산한다.
   * 쇼츠 UI가 하단 200픽셀쯤을 가리므로 자막을 그보다 위에 둔다.
   */
  subtitleFontSizePx: 46,
  subtitleMarginBottomPx: 300,
  subtitleFont: "Apple SD Gothic Neo",
  attributionFontSize: 34,
  /** 출처 문구를 화면 아래에서 얼마나 띄울지. */
  attributionMarginBottom: 120,
  /**
   * drawtext 에 쓸 폰트 파일. **비워 두면 한글이 두부 글자로 깨진다.**
   * 정적 ffmpeg 빌드에는 fontconfig 설정이 없어 기본 폰트를 찾지 못하고,
   * 그러면 ASCII 만 찍히고 한글 자리에 네모가 들어간다. 실제로 렌더해 보고서야
   * 발견한 문제라 기본값으로 못박아 둔다 (macOS 기본 탑재 폰트).
   */
  fontFile: "/System/Library/Fonts/AppleSDGothicNeo.ttc",
  /** 화면 상단에 박는 타이틀. 픽셀로 적고 아래에서 쓰인다. */
  titleFontSizePx: 64,
  /** 화면 위에서 얼마나 내려온 곳에 둘지. 16:9 원본이면 위 여백이 656픽셀쯤 된다. */
  titleTopPx: 220,
  /** 몇 초 동안 보여 줄지. 쓸지 말지는 처음 몇 초 안에 결정된다. */
  titleDurationSec: 3,
  /** 한 줄에 몇 글자까지 둘지. drawtext 는 자동 줄바꿈을 하지 않는다. */
  titleCharsPerLine: 13,

  /**
   * 유료광고 배지. **빼면 안 된다.**
   *
   * 쿠팡 파트너스 가이드는 설명란 고지만으로 부족하다고 못박는다. "설명란 또는 댓글에서
   * 대가성 문구와 링크를 적절히 기재했지만 영상 제목 또는 영상 내에 광고 표시를 하지
   * 않은 경우" 를 반려 사례로 든다. 제시한 세 방법 중 배지를 골랐다 — 영상 내내 보여
   * 가장 안전하고, 작아서 화면을 거의 가리지 않으며, 제목의 훅을 건드리지 않는다.
   */
  adBadgeFontSizePx: 34,
  adBadgeMarginPx: 40,
});

/** 배지 문구. 쿠팡 가이드의 예시 표기를 그대로 쓴다. */
const AD_BADGE_TEXT = "유료광고 포함";

/**
 * libass 가 쓰는 기본 좌표계의 높이.
 *
 * 자막 파일에 PlayResY 가 없으면 libass 는 이 값을 기준으로 좌표를 잡고, 실제 영상
 * 높이에 맞춰 통째로 확대한다. 1920 세로 영상이면 배율이 5배다. 이것을 모르고
 * FontSize=18, MarginV=260 을 주었더니 글자가 90픽셀로 커지고 자막이 화면 맨 위에
 * 붙었다 — 렌더 결과를 눈으로 보고서야 드러났다. 그래서 픽셀로 적고 여기서 환산한다.
 */
const ASS_기준높이 = 384;

/**
 * 타이틀 문구를 줄바꿈한다.
 *
 * drawtext 는 자동 줄바꿈을 하지 않는다. 긴 훅을 그대로 넘기면 한 줄로 뻗어 나가
 * 화면 밖으로 잘린다. 낱말 경계에서 끊고, 낱말 하나가 한 줄보다 길면 그것만 강제로 자른다.
 */
function wrapTitle(text, charsPerLine) {
  const 한줄 = Math.max(4, Math.floor(charsPerLine));
  const 줄들 = [];
  let 현재 = "";

  for (const 말 of String(text).split(/\s+/).filter(Boolean)) {
    if (말.length > 한줄) {
      if (현재) { 줄들.push(현재); 현재 = ""; }
      for (let i = 0; i < 말.length; i += 한줄) 줄들.push(말.slice(i, i + 한줄));
      continue;
    }
    const 붙이면 = 현재 ? `${현재} ${말}` : 말;
    if (붙이면.length > 한줄) { 줄들.push(현재); 현재 = 말; }
    else { 현재 = 붙이면; }
  }
  if (현재) 줄들.push(현재);
  return 줄들.join("\n");
}

/** 화면 픽셀 값을 libass 좌표계 값으로 환산한다. */
function ass값(px, videoHeight) {
  const 배율 = videoHeight / ASS_기준높이;
  return Math.max(1, Math.round(px / 배율));
}

/**
 * ffmpeg 필터 그래프의 **작은따옴표 안에 들어갈 값**을 이스케이프한다.
 *
 * 백슬래시와 작은따옴표만 처리한다. 콜론·쉼표·대괄호는 감싸는 작은따옴표가 이미
 * 보호하므로 건드리지 않는다. 여기에 백슬래시를 더 붙이면 ffmpeg 가 그 백슬래시를
 * 글자 그대로 받아들여 값이 망가진다 — 예를 들어 자막 스타일의 `FontSize=18` 앞에
 * `\,` 가 붙으면 그 뒤 속성이 통째로 무시된다.
 */
function escapeFilterValue(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

/**
 * 구간 하나를 세로형 쇼츠로 렌더하는 실행 계획을 만든다.
 *
 * @param {object} p
 * @param {string} p.inputPath 원본 영상 경로
 * @param {string} p.outputPath 결과 mp4 경로
 * @param {number} p.startSec 구간 시작 (초)
 * @param {number} p.endSec 구간 끝 (초)
 * @param {string} [p.subtitlePath] 자막 SRT 경로. 없으면 자막을 입히지 않는다
 * @param {string} [p.attributionText] 출처 표기 문구. 없으면 표기하지 않는다
 * @param {string} [p.attributionTextPath] 출처 문구를 적을 파일 경로 (attributionText 와 짝)
 * @param {string} [p.fontFile] drawtext 에 쓸 폰트 파일. 한글이 깨지면 이것을 지정한다
 * @returns {{command: string, args: string[], sidecarFiles: Array<{path: string, content: string}>, filterGraph: string}}
 */
function buildRenderPlan(p = {}) {
  const o = { ...DEFAULTS, ...p };
  const 오류 = 입력검사(o);
  if (오류) throw new Error(오류);

  const { width, height } = o;
  const sidecarFiles = [];
  const chain = [];

  if (o.mode === "crop") {
    // 가운데를 잘라낸다. 화면을 꽉 채우지만 가장자리의 인물과 자막이 잘린다.
    chain.push(
      `[0:v]scale=${width}:${height}:force_original_aspect_ratio=increase,` +
        `crop=${width}:${height},setsar=1[base]`
    );
  } else {
    // 흐린 배경 위에 원본을 통째로 얹는다. 잘리는 곳이 없어 기본값으로 쓴다.
    chain.push("[0:v]split=2[bg][fg]");
    chain.push(
      `[bg]scale=${width}:${height}:force_original_aspect_ratio=increase,` +
        `crop=${width}:${height},gblur=sigma=${o.blurSigma}[bgb]`
    );
    chain.push(`[fg]scale=${width}:-2[fgs]`);
    chain.push("[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[base]");
  }

  let label = "base";

  if (o.subtitlePath) {
    // 픽셀로 적은 값을 libass 좌표계로 환산한다. Alignment=2 는 하단 가운데다.
    const style =
      `FontName=${o.subtitleFont},FontSize=${ass값(o.subtitleFontSizePx, height)},` +
      `Outline=${ass값(6, height)},Shadow=0,` +
      `MarginV=${ass값(o.subtitleMarginBottomPx, height)},Alignment=2`;
    chain.push(
      `[${label}]subtitles=filename='${escapeFilterValue(o.subtitlePath)}':` +
        `force_style='${escapeFilterValue(style)}'[sub]`
    );
    label = "sub";
  }

  if (o.attributionText) {
    if (!o.attributionTextPath) {
      throw new Error("attributionText 를 주면 attributionTextPath 도 함께 주어야 한다");
    }
    // 문구는 파일로 넘긴다. 필터 그래프 안에서 한글과 특수문자를 이스케이프하지 않기 위해서다.
    sidecarFiles.push({ path: o.attributionTextPath, content: o.attributionText });

    const 폰트지정 = o.fontFile ? `fontfile='${escapeFilterValue(o.fontFile)}':` : "";
    chain.push(
      `[${label}]drawtext=${폰트지정}textfile='${escapeFilterValue(o.attributionTextPath)}':` +
        `x=(w-text_w)/2:y=h-${o.attributionMarginBottom}:` +
        `fontsize=${o.attributionFontSize}:fontcolor=white@0.85:` +
        `box=1:boxcolor=black@0.4:boxborderw=12[out]`
    );
    label = "out";
  }

  if (o.titleText) {
    if (!o.titleTextPath) {
      throw new Error("titleText 를 주면 titleTextPath 도 함께 주어야 한다");
    }
    const 줄바꾼문구 = wrapTitle(o.titleText, o.titleCharsPerLine);
    sidecarFiles.push({ path: o.titleTextPath, content: 줄바꾼문구 });

    const 폰트 = o.fontFile ? `fontfile='${escapeFilterValue(o.fontFile)}':` : "";
    // enable 로 첫 몇 초만 띄운다. 그 뒤에는 화면을 비워 영상에 집중하게 한다.
    const 조건 = Number.isFinite(o.titleDurationSec) && o.titleDurationSec > 0
      ? `:enable='lt(t\\,${round3(o.titleDurationSec)})'`
      : "";

    chain.push(
      `[${label}]drawtext=${폰트}textfile='${escapeFilterValue(o.titleTextPath)}':` +
        `x=(w-text_w)/2:y=${Math.round(o.titleTopPx)}:` +
        `fontsize=${Math.round(o.titleFontSizePx)}:fontcolor=white:` +
        `borderw=6:bordercolor=black@0.85:line_spacing=14:text_align=C` +
        `${조건}[title]`
    );
    label = "title";
  }

  // 배지는 마지막에 얹는다. 무엇에도 가리지 않아야 한다.
  if (o.adBadgeText !== null) {
    if (!o.adBadgeTextPath) {
      throw new Error("adBadgeTextPath 가 필요하다 — 유료광고 배지는 생략할 수 없다");
    }
    const 문구 = o.adBadgeText || AD_BADGE_TEXT;
    sidecarFiles.push({ path: o.adBadgeTextPath, content: 문구 });

    const 폰트 = o.fontFile ? `fontfile='${escapeFilterValue(o.fontFile)}':` : "";
    chain.push(
      `[${label}]drawtext=${폰트}textfile='${escapeFilterValue(o.adBadgeTextPath)}':` +
        `x=${Math.round(o.adBadgeMarginPx)}:y=${Math.round(o.adBadgeMarginPx)}:` +
        `fontsize=${Math.round(o.adBadgeFontSizePx)}:fontcolor=white:` +
        `box=1:boxcolor=black@0.6:boxborderw=14[ad]`
    );
    label = "ad";
  }

  const filterGraph = chain.join(";");

  const args = [
    "-hide_banner",
    "-loglevel", "error",
    "-y",
    // -ss 를 -i 앞에 두면 빠르지만 키프레임 단위로 어긋난다. -accurate_seek 로 정확도를 지킨다.
    "-accurate_seek",
    "-ss", String(round3(o.startSec)),
    "-to", String(round3(o.endSec)),
    "-i", o.inputPath,
    "-filter_complex", filterGraph,
    "-map", `[${label}]`,
    "-map", "0:a?",
    "-c:v", "libx264",
    "-preset", o.preset,
    "-crf", String(o.crf),
    "-pix_fmt", "yuv420p",
    "-r", String(o.fps),
    "-c:a", "aac",
    "-b:a", o.audioBitrate,
    "-movflags", "+faststart",
    o.outputPath,
  ];

  return { command: "ffmpeg", args, sidecarFiles, filterGraph };
}

function 입력검사(o) {
  if (!o.inputPath) return "inputPath 가 필요하다";
  if (!o.outputPath) return "outputPath 가 필요하다";
  if (!Number.isFinite(o.startSec) || !Number.isFinite(o.endSec)) return "startSec 과 endSec 은 숫자여야 한다";
  if (o.endSec <= o.startSec) return "endSec 이 startSec 보다 커야 한다";
  if (o.startSec < 0) return "startSec 은 0 이상이어야 한다";
  if (o.mode !== "blur" && o.mode !== "crop") return `mode 는 blur 또는 crop 이어야 한다 (받은 값: ${o.mode})`;
  return null;
}

function round3(n) {
  return Math.round(n * 1000) / 1000;
}

module.exports = { buildRenderPlan, escapeFilterValue, wrapTitle, ass값, ASS_기준높이, AD_BADGE_TEXT, DEFAULTS };
