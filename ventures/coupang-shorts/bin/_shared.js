/**
 * 실행 계층이 함께 쓰는 부분. **여기서만 부작용을 낸다** — 파일을 읽고 쓰고,
 * 외부 명령을 띄우고, 시계를 본다. 판정과 계산은 전부 `lib/` 의 순수 함수가 한다.
 *
 * 자격 로드 순서는 환경변수가 먼저이고 그다음이 gitignore 된 파일이다.
 * `.claude/mcp-servers/notion-min/server.js:44-52` 가 노션 토큰을 다루는 방식과 같다.
 * 이 저장소는 공개 커밋되므로 자격이 커밋 대상 파일에 들어가서는 안 된다.
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const ROOT = path.join(__dirname, "..");
const REPO_ROOT = path.join(ROOT, "..", "..");

/** 설정 파일을 읽는다. 주석용 `_` 키는 그대로 둔다 — 읽는 쪽이 무시하면 된다. */
function loadConfig(name) {
  const p = path.join(ROOT, "config", `${name}.json`);
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch (e) {
    throw new Error(`설정 파일을 읽지 못했다 (${p}): ${e.message}`);
  }
}

/**
 * 외부 API 자격을 읽는다. 없으면 빈 값을 돌려주고, 부르는 쪽이 가짜 모드로 넘어간다.
 * **읽은 값을 로그에 찍지 않는다.**
 */
function loadCredentials() {
  const 파일 = path.join(ROOT, ".credentials.json");
  let 파일값 = {};
  if (fs.existsSync(파일)) {
    try {
      파일값 = JSON.parse(fs.readFileSync(파일, "utf-8"));
    } catch (_) {
      log("경고: .credentials.json 을 읽지 못했다. 환경변수만 쓴다");
    }
  }

  return {
    youtubeApiKey: (process.env.YOUTUBE_API_KEY || 파일값.youtubeApiKey || "").trim(),
    coupangAccessKey: (process.env.COUPANG_ACCESS_KEY || 파일값.coupangAccessKey || "").trim(),
    coupangSecretKey: (process.env.COUPANG_SECRET_KEY || 파일값.coupangSecretKey || "").trim(),
  };
}

/** 쿠팡을 실제로 부를 수 있는 상태인지. 아니면 가짜 응답으로 돈다. */
function hasCoupangCredentials(creds) {
  return Boolean(creds.coupangAccessKey && creds.coupangSecretKey);
}

/**
 * 이 영상의 실행 디렉터리. `runs/` 는 gitignore 된다.
 *
 * 이미 만들어 둔 디렉터리가 있으면 날짜가 달라도 그것을 쓴다. 오늘 날짜로만 계산하면
 * 어제 분석한 영상을 오늘 다시 렌더하거나 문구만 다시 뽑는 일이 안 된다 — 실제로
 * 제목 규칙을 고치고 지난 영상들의 문구를 다시 만들려다 "분석 결과가 없다" 로 막혔다.
 */
function runDir(videoId, now = new Date()) {
  const 이름 = videoId || "_";
  const 뿌리 = path.join(ROOT, "runs");

  if (fs.existsSync(뿌리)) {
    // 최근 날짜부터 본다. 같은 영상을 여러 날 다뤘다면 마지막 것이 맞다.
    const 날짜들 = fs.readdirSync(뿌리).filter((n) => /^\d{4}-\d{2}-\d{2}$/.test(n)).sort().reverse();
    for (const 날짜 of 날짜들) {
      const 후보 = path.join(뿌리, 날짜, 이름);
      if (fs.existsSync(후보)) return 후보;
    }
  }

  const d = path.join(뿌리, now.toISOString().slice(0, 10), 이름);
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function readJson(p, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch (_) {
    return fallback;
  }
}

function writeJson(p, value) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, `${JSON.stringify(value, null, 2)}\n`, "utf-8");
  return p;
}

/** 쿠팡 호출 예산 상태. 영상별이 아니라 저장소 전체에서 하나다. */
function budgetStatePath() {
  return path.join(ROOT, "runs", ".coupang-budget.json");
}

/**
 * 외부 명령을 띄운다. **인자는 반드시 배열로 받는다** — 셸을 거치지 않기 위해서다.
 * @returns {{ok: boolean, stdout: string, stderr: string, status: number|null}}
 */
function run(command, args, { timeoutMs = 600000, cwd = REPO_ROOT } = {}) {
  if (!Array.isArray(args)) throw new Error("인자는 배열이어야 한다 — 문자열로 넘기면 셸이 해석한다");

  const r = spawnSync(command, args, {
    encoding: "utf-8",
    timeout: timeoutMs,
    cwd,
    maxBuffer: 64 * 1024 * 1024,
  });

  return {
    ok: r.status === 0,
    status: r.status,
    stdout: r.stdout || "",
    stderr: r.stderr || "",
    error: r.error ? r.error.message : null,
  };
}

/** 설정에 적힌 ffmpeg 경로를 절대 경로로 바꾼다. 없으면 그대로 둬서 PATH 에서 찾게 한다. */
function resolveFfmpeg(config) {
  const p = config && config.render && config.render.ffmpegPath;
  if (!p) return "ffmpeg";
  const abs = path.isAbsolute(p) ? p : path.join(REPO_ROOT, p);
  return fs.existsSync(abs) ? abs : "ffmpeg";
}

/** 명령줄 인자를 읽는다. `--go` 가 없으면 dryRun 이다. */
function parseArgs(argv = process.argv.slice(2)) {
  const out = { go: false, fake: false, video: null, keyword: null, limit: null, _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--go") out.go = true;
    else if (a === "--fake") out.fake = true;
    else if (a === "--video") out.video = argv[++i];
    else if (a === "--keyword") out.keyword = argv[++i];
    else if (a === "--limit") out.limit = Number(argv[++i]);
    else out._.push(a);
  }
  out.dryRun = !out.go;
  return out;
}

function log(...args) {
  console.log(...args);
}

/** 단계 제목. 어디까지 갔는지 눈으로 좇을 수 있게 한다. */
function step(n, 제목) {
  log(`\n[${n}] ${제목}`);
}

module.exports = {
  ROOT, REPO_ROOT,
  loadConfig, loadCredentials, hasCoupangCredentials,
  runDir, readJson, writeJson, budgetStatePath,
  run, resolveFfmpeg, parseArgs, log, step,
};
