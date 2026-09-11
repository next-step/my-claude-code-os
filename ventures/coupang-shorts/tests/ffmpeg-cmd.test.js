/** 실행: node --test ventures/coupang-shorts/tests/ffmpeg-cmd.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { buildRenderPlan, escapeFilterValue } = require("../lib/ffmpeg-cmd.js");

const 기본입력 = {
  inputPath: "/tmp/source.mp4",
  outputPath: "/tmp/short.mp4",
  startSec: 184.5,
  endSec: 232.5,
};

/** 인자 배열에서 플래그 바로 뒤 값을 꺼낸다. */
function 값(args, flag) {
  const i = args.indexOf(flag);
  return i === -1 ? null : args[i + 1];
}

test("AC-22: 구간 시작과 끝이 인자에 그대로 들어간다", () => {
  const { args } = buildRenderPlan(기본입력);
  assert.equal(값(args, "-ss"), "184.5");
  assert.equal(값(args, "-to"), "232.5");
  // -ss 가 -i 보다 앞에 와야 빠르게 탐색한다.
  assert.ok(args.indexOf("-ss") < args.indexOf("-i"), "-ss 는 -i 보다 앞에 와야 한다");
  assert.ok(args.includes("-accurate_seek"), "정확한 탐색 옵션이 있어야 한다");
});

test("AC-23: 블러 패딩 필터 체인이 1080x1920 을 만든다", () => {
  const { filterGraph } = buildRenderPlan(기본입력);
  assert.match(filterGraph, /split=2/, "원본을 배경과 전경으로 나눠야 한다");
  assert.match(filterGraph, /gblur=sigma=25/, "배경을 흐리게 해야 한다");
  assert.match(filterGraph, /crop=1080:1920/, "배경을 세로 규격으로 잘라야 한다");
  assert.match(filterGraph, /overlay=\(W-w\)\/2:\(H-h\)\/2/, "전경을 가운데 얹어야 한다");
  assert.match(filterGraph, /setsar=1/, "화소 종횡비를 1로 고정해야 한다");
});

test("AC-23b: crop 모드는 배경을 만들지 않고 가운데만 잘라낸다", () => {
  const { filterGraph } = buildRenderPlan({ ...기본입력, mode: "crop" });
  assert.doesNotMatch(filterGraph, /gblur/, "crop 모드에는 블러가 없어야 한다");
  assert.match(filterGraph, /crop=1080:1920/);
});

test("AC-24: 자막 파일과 출처 문구가 필터에 포함된다", () => {
  const { filterGraph, sidecarFiles } = buildRenderPlan({
    ...기본입력,
    subtitlePath: "/tmp/seg.srt",
    attributionText: "원본: 어떤채널 https://youtu.be/abc",
    attributionTextPath: "/tmp/attr.txt",
  });

  assert.match(filterGraph, /subtitles=filename='\/tmp\/seg\.srt'/);
  assert.match(filterGraph, /drawtext=/);
  assert.match(filterGraph, /textfile='\/tmp\/attr\.txt'/);

  // 출처 문구는 필터에 직접 박지 않고 파일로 넘긴다 — 이스케이프 사고를 피하기 위해서다.
  assert.doesNotMatch(filterGraph, /어떤채널/, "문구가 필터 그래프에 직접 들어가면 안 된다");
  assert.deepEqual(sidecarFiles, [
    { path: "/tmp/attr.txt", content: "원본: 어떤채널 https://youtu.be/abc" },
  ]);
});

test("AC-24b: 자막 스타일의 쉼표에 백슬래시를 덧붙이지 않는다 — 덧붙이면 뒤 속성이 무시된다", () => {
  const { filterGraph } = buildRenderPlan({ ...기본입력, subtitlePath: "/tmp/seg.srt" });
  const style = filterGraph.match(/force_style='([^']*)'/)[1];
  assert.doesNotMatch(style, /\\,/, "쉼표를 이스케이프하면 안 된다");
  assert.match(style, /FontSize=18/);
  assert.match(style, /MarginV=260/);
});

test("AC-25: 인자를 배열로 돌려주어 셸 해석을 거치지 않는다", () => {
  // 파일명에 셸 메타문자가 섞여 있어도 인자 하나로 그대로 유지되어야 한다.
  const 위험한이름 = "/tmp/a b; rm -rf $HOME/'x'.mp4";
  const { command, args } = buildRenderPlan({ ...기본입력, outputPath: 위험한이름 });

  assert.equal(command, "ffmpeg");
  assert.ok(Array.isArray(args), "인자는 배열이어야 한다");
  assert.equal(args[args.length - 1], 위험한이름, "이름이 쪼개지지 않고 인자 하나로 남아야 한다");
  assert.ok(args.every((a) => typeof a === "string"), "모든 인자가 문자열이어야 한다");
});

test("AC-25b: 잘못된 입력은 실행 계획을 만들지 않고 즉시 막는다", () => {
  assert.throws(() => buildRenderPlan({ ...기본입력, endSec: 100 }), /endSec/);
  assert.throws(() => buildRenderPlan({ ...기본입력, startSec: -5 }), /startSec/);
  assert.throws(() => buildRenderPlan({ ...기본입력, mode: "이상한모드" }), /mode/);
  assert.throws(() => buildRenderPlan({ ...기본입력, inputPath: "" }), /inputPath/);
  // 출처 문구만 주고 파일 경로를 빠뜨린 경우
  assert.throws(() => buildRenderPlan({ ...기본입력, attributionText: "원본" }), /attributionTextPath/);
});

test("AC-25c: 값 이스케이프는 백슬래시와 작은따옴표만 처리한다", () => {
  assert.equal(escapeFilterValue("a'b"), "a\\'b");
  assert.equal(escapeFilterValue("a\\b"), "a\\\\b");
  assert.equal(escapeFilterValue("a,b:c[d]"), "a,b:c[d]", "따옴표가 보호하는 문자는 건드리지 않는다");
});

test("AC-24c: 출처 표기에 한글 폰트 파일을 반드시 지정한다 — 없으면 한글이 두부 글자로 깨진다", () => {
  // 실제로 렌더해 보고 발견한 문제다. 정적 ffmpeg 빌드에는 fontconfig 설정이 없어
  // fontfile 을 주지 않으면 ASCII 만 찍히고 한글 자리에 네모가 들어간다.
  const { filterGraph } = buildRenderPlan({
    ...기본입력,
    attributionText: "원본: 어떤채널",
    attributionTextPath: "/tmp/attr.txt",
  });
  assert.match(filterGraph, /fontfile='[^']+'/, "폰트 파일이 지정되어야 한다");
  assert.match(filterGraph, /AppleSDGothicNeo/, "기본값으로 한글 폰트가 들어가야 한다");
});
