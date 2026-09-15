/** 실행: node --test ventures/coupang-shorts/tests/ffmpeg-cmd.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { buildRenderPlan, escapeFilterValue, wrapTitle } = require("../lib/ffmpeg-cmd.js");

const 기본입력 = {
  inputPath: "/tmp/source.mp4",
  outputPath: "/tmp/short.mp4",
  startSec: 184.5,
  endSec: 232.5,
  // 유료광고 배지는 생략할 수 없으므로 기본입력에 둔다 (AC-41).
  adBadgeTextPath: "/tmp/adbadge.txt",
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
  assert.ok(sidecarFiles.some((f) => f.path === "/tmp/attr.txt" && f.content === "원본: 어떤채널 https://youtu.be/abc"));
  // 유료광고 배지는 늘 함께 나온다 (AC-41).
  assert.ok(sidecarFiles.some((f) => f.path === "/tmp/adbadge.txt"));
});

test("AC-24b: 자막 스타일의 쉼표에 백슬래시를 덧붙이지 않는다 — 덧붙이면 뒤 속성이 무시된다", () => {
  const { filterGraph } = buildRenderPlan({ ...기본입력, subtitlePath: "/tmp/seg.srt" });
  const style = filterGraph.match(/force_style='([^']*)'/)[1];
  assert.doesNotMatch(style, /\\,/, "쉼표를 이스케이프하면 안 된다");
  // 값 자체는 AC-24d 가 본다. 여기서는 속성이 살아남았는지만 확인한다.
  assert.match(style, /FontSize=\d+/);
  assert.match(style, /MarginV=\d+/);
  assert.match(style, /FontName=Apple SD Gothic Neo/);
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

test("AC-24d: 자막 크기와 위치를 libass 좌표계로 환산한다 — 안 하면 글자가 5배로 커지고 화면 위에 붙는다", () => {
  // 실제 렌더 결과를 보고서야 드러난 문제다. libass 는 자막 파일에 PlayResY 가 없으면
  // 높이 384 기준으로 좌표를 잡고 영상 높이에 맞춰 통째로 확대한다.
  const { filterGraph } = buildRenderPlan({ ...기본입력, subtitlePath: "/tmp/seg.srt" });
  const style = filterGraph.match(/force_style='([^']*)'/)[1];

  const fontSize = Number(style.match(/FontSize=(\d+)/)[1]);
  const marginV = Number(style.match(/MarginV=(\d+)/)[1]);

  // 1920 세로에서 배율이 5배이므로, 46픽셀 글자는 ASS 값으로 9 안팎이어야 한다.
  assert.ok(fontSize < 20, `환산하지 않으면 글자가 5배로 커진다 (FontSize=${fontSize})`);
  assert.ok(marginV < 100, `환산하지 않으면 자막이 화면 위로 올라간다 (MarginV=${marginV})`);
  assert.match(style, /Alignment=2/, "하단 가운데 정렬이어야 한다");
});

test("AC-24e: 화면 높이가 달라지면 환산 값도 따라 달라진다", () => {
  const 세로 = buildRenderPlan({ ...기본입력, subtitlePath: "/tmp/s.srt" });
  const 작은화면 = buildRenderPlan({ ...기본입력, subtitlePath: "/tmp/s.srt", width: 540, height: 960 });

  const 크기 = (g) => Number(g.match(/FontSize=(\d+)/)[1]);
  assert.ok(크기(작은화면.filterGraph) > 크기(세로.filterGraph), "작은 화면일수록 ASS 값이 커야 실제 픽셀이 같다");
});

test("AC-24f: 자막을 끄면 subtitles 필터를 넣지 않는다 — 원본에 이미 자막이 박힌 영상이 있다", () => {
  const { filterGraph } = buildRenderPlan({ ...기본입력, subtitlePath: undefined });
  assert.doesNotMatch(filterGraph, /subtitles=/);
});

test("AC-40: 화면 타이틀을 상단에 박고 문구는 파일로 넘긴다", () => {
  const { filterGraph, sidecarFiles } = buildRenderPlan({
    ...기본입력,
    titleText: "락앤락 꿀템 14개",
    titleTextPath: "/tmp/title1.txt",
  });

  assert.match(filterGraph, /textfile='\/tmp\/title1\.txt'/);
  assert.match(filterGraph, /text_align=C/, "여러 줄일 때 가운데 정렬이어야 한다");
  assert.match(filterGraph, /fontfile='[^']*AppleSDGothicNeo[^']*'/, "한글 폰트를 지정해야 한다");

  // 출처 표기와 같은 이유로 문구를 필터에 직접 박지 않는다.
  assert.doesNotMatch(filterGraph, /락앤락/, "문구가 필터 그래프에 직접 들어가면 안 된다");
  assert.ok(sidecarFiles.some((f) => f.path === "/tmp/title1.txt" && f.content.includes("락앤락")));
});

test("AC-40b: 지정한 초 동안만 보이게 한다", () => {
  const { filterGraph } = buildRenderPlan({
    ...기본입력, titleText: "훅 문구", titleTextPath: "/tmp/t.txt", titleDurationSec: 3,
  });
  assert.match(filterGraph, /enable='lt\(t\\,3\)'/, "첫 3초만 띄워야 한다");

  // 0 이하면 조건 없이 끝까지 보인다.
  const 내내 = buildRenderPlan({
    ...기본입력, titleText: "훅 문구", titleTextPath: "/tmp/t.txt", titleDurationSec: 0,
  });
  assert.doesNotMatch(내내.filterGraph, /enable=/);
});

test("AC-40c: 긴 문구를 낱말 경계에서 줄바꿈한다 — drawtext 는 자동 줄바꿈을 안 한다", () => {
  assert.equal(wrapTitle("락앤락 꿀템 14개", 11), "락앤락 꿀템 14개");
  assert.equal(wrapTitle("에어프라이어 유료 광고에 지친 당신을 위해", 11), "에어프라이어 유료\n광고에 지친 당신을\n위해");

  // 낱말 하나가 한 줄보다 길면 그것만 강제로 자른다.
  assert.equal(wrapTitle("가".repeat(25), 10), `${"가".repeat(10)}\n${"가".repeat(10)}\n${"가".repeat(5)}`);

  for (const 줄 of wrapTitle("아주 긴 훅 문구를 여러 낱말로 늘어놓은 경우입니다", 11).split("\n")) {
    assert.ok(줄.length <= 11, `${줄.length}자로 한 줄을 넘겼다: ${줄}`);
  }
});

test("AC-40d: 타이틀을 끄면 타이틀 필터만 빠진다 — 배지는 남는다", () => {
  const { filterGraph, sidecarFiles } = buildRenderPlan({ ...기본입력, titleText: undefined });

  assert.doesNotMatch(filterGraph, /title\d*\.txt/, "타이틀 문구 파일이 없어야 한다");
  // 배지는 규정상 생략할 수 없으므로 drawtext 가 하나 남는다 (AC-41).
  assert.equal((filterGraph.match(/drawtext/g) || []).length, 1);
  assert.deepEqual(sidecarFiles.map((f) => f.path), ["/tmp/adbadge.txt"]);
});

test("AC-40e: 문구만 주고 파일 경로를 빠뜨리면 막는다", () => {
  assert.throws(() => buildRenderPlan({ ...기본입력, titleText: "훅" }), /titleTextPath/);
});

test("AC-40f: 출처·타이틀·배지를 함께 쓰면 파일 세 개를 알려 준다", () => {
  const { sidecarFiles, filterGraph } = buildRenderPlan({
    ...기본입력,
    attributionText: "원본: 어떤채널", attributionTextPath: "/tmp/attr.txt",
    titleText: "훅 문구", titleTextPath: "/tmp/title.txt",
  });
  assert.deepEqual(sidecarFiles.map((f) => f.path), ["/tmp/attr.txt", "/tmp/title.txt", "/tmp/adbadge.txt"]);
  assert.equal((filterGraph.match(/drawtext/g) || []).length, 3);
});

test("AC-41: 유료광고 배지를 영상 내내 띄운다 — 쿠팡 가이드가 요구하는 표기다", () => {
  // 가이드: "설명란 또는 댓글에서 대가성 문구와 링크를 적절히 기재했지만
  // 영상 제목 또는 영상 내에 광고 표시를 하지 않은 경우" 는 반려 사례다.
  const { filterGraph, sidecarFiles } = buildRenderPlan({
    ...기본입력, adBadgeTextPath: "/tmp/adbadge.txt",
  });

  const 배지 = sidecarFiles.find((f) => f.path === "/tmp/adbadge.txt");
  assert.ok(배지, "배지 문구 파일을 알려 줘야 한다");
  assert.equal(배지.content, "유료광고 포함");
  assert.match(filterGraph, /textfile='\/tmp\/adbadge\.txt'/);

  // 타이틀과 달리 enable 조건이 없어야 한다. 첫 몇 초만 보이면 표기로 부족하다.
  const 배지필터 = filterGraph.split(";").find((f) => f.includes("adbadge.txt"));
  assert.doesNotMatch(배지필터, /enable=/, "배지는 영상 내내 보여야 한다");
});

test("AC-41b: 배지가 맨 마지막에 얹혀 무엇에도 가리지 않는다", () => {
  const { filterGraph } = buildRenderPlan({
    ...기본입력,
    subtitlePath: "/tmp/seg.srt",
    attributionText: "원본: 어떤채널", attributionTextPath: "/tmp/attr.txt",
    titleText: "훅 문구", titleTextPath: "/tmp/title.txt",
    adBadgeTextPath: "/tmp/adbadge.txt",
  });

  const 단계들 = filterGraph.split(";");
  assert.ok(단계들[단계들.length - 1].includes("adbadge.txt"), "배지가 마지막 단계여야 한다");
  assert.match(filterGraph, /\[ad\]$/, "마지막 출력 꼬리표가 배지여야 한다");
});

test("AC-41c: 배지 경로를 빠뜨리면 렌더 계획 자체를 만들지 않는다 — 생략할 수 없는 표기다", () => {
  assert.throws(() => buildRenderPlan({ ...기본입력, adBadgeTextPath: undefined }), /adBadgeTextPath/);
});

test("AC-41d: 배지 문구는 설정으로 바꿀 수 있되 비울 수는 없다", () => {
  const { sidecarFiles } = buildRenderPlan({
    ...기본입력, adBadgeTextPath: "/tmp/ad.txt", adBadgeText: "광고 포함",
  });
  assert.equal(sidecarFiles.find((f) => f.path === "/tmp/ad.txt").content, "광고 포함");

  // 빈 문자열을 주면 기본 문구로 되돌아간다.
  const 빈값 = buildRenderPlan({ ...기본입력, adBadgeTextPath: "/tmp/ad.txt", adBadgeText: "" });
  assert.equal(빈값.sidecarFiles.find((f) => f.path === "/tmp/ad.txt").content, "유료광고 포함");
});
