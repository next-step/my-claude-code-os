/**
 * Bash 명령 문자열에서 "이 명령이 쓰거나 지울 파일 경로"를 뽑아낸다.
 *
 * 왜 필요한가: `session-conflict-warn.js` 훅은 `PreToolUse(Edit|Write)`에만 걸려 있었다.
 * 그런데 파일을 만드는 경로는 둘이다 — 전용 도구와 Bash(히어독·리다이렉션)다. 2026-09-07에
 * 실제로 Bash 히어독으로 다른 세션의 지침 파일을 덮어썼는데 훅이 발동하지 않았다.
 * 훅이 지키는 문이 하나뿐이면 다른 문으로 들어온 변경은 그냥 통과한다.
 *
 * **완전한 셸 파서가 아니다.** `dom-lite.js`와 같은 태도로, 이 저장소에서 실제로 쓰는
 * 형태만 정규식으로 다룬다. 변수 확장(`$VAR`), 명령 치환(`$(...)`), 글롭(`*.md`),
 * 서브셸은 해석하지 않는다. 놓치는 쪽(false negative)은 경고가 안 뜰 뿐이고,
 * 잘못 잡는 쪽(false positive)은 아무도 만지지 않은 경로라 경고가 안 뜬다 —
 * 어느 쪽도 편집을 막지 않으므로 정확도보다 단순함을 택했다.
 *
 * 순수 함수만 담는다(fs 접근 없음). .claude/tests/write-targets.test.js 가 검증한다.
 */

/** 인자를 파일 대상으로 해석하는 명령들. 여기 없는 명령은 리다이렉션만 본다. */
const MULTI_TARGET = new Set(["rm", "touch", "truncate", "unlink", "tee", "shred"]);
const LAST_TARGET = new Set(["cp", "mv", "install", "ln", "rsync"]);

/** 실제 파일이 아니어서 충돌 대상이 될 수 없는 경로. */
const NON_FILES = new Set(["/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "-"]);

/**
 * 히어독 본문을 지운다. 본문에는 마크다운 인용부호(`> …`)나 예시 명령이 들어 있어
 * 그대로 두면 리다이렉션으로 오인된다. 이 저장소는 히어독으로 문서를 쓰므로 필수다.
 */
function stripHeredocs(command) {
  const lines = String(command).split(/\r?\n/);
  const out = [];
  let delimiter = null;

  for (const line of lines) {
    if (delimiter === null) {
      out.push(line);
      // `<<EOF`, `<<-EOF`, `<<'EOF'`, `<<"EOF"` 모두 받는다. 한 줄에 여러 개면 첫 번째만.
      const open = line.match(/<<-?\s*(?:'([^']+)'|"([^"]+)"|([A-Za-z_][A-Za-z0-9_]*))/);
      if (open) delimiter = open[1] || open[2] || open[3];
      continue;
    }
    if (line.trim() === delimiter) delimiter = null; // 종료 구분자 자체도 버린다
  }

  return out.join("\n");
}

/** 따옴표를 존중하며 토큰으로 자른다. 따옴표는 벗겨서 돌려준다. */
function tokenize(segment) {
  const tokens = [];
  const pattern = /"([^"]*)"|'([^']*)'|([^\s]+)/g;
  let match;
  while ((match = pattern.exec(segment)) !== null) {
    const value = match[1] !== undefined ? match[1] : match[2] !== undefined ? match[2] : match[3];
    if (value !== "") tokens.push(value);
  }
  return tokens;
}

/** `;` `&&` `||` `|` 개행으로 명령을 나눈다. 서브셸 괄호는 구분자로만 취급한다. */
function splitSegments(command) {
  return String(command)
    .split(/(?:\|\||&&|[;|\n()])/)
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

/**
 * 리다이렉션(`>`, `>>`) 대상만 뽑는다. `2>&1`·`>&2`는 파일이 아니므로 제외한다.
 * `=>`(화살표 함수)도 제외한다 — 2026-09-07에 세션 보드의 recentFiles에 `f.path` 같은
 * 쓰레기가 쌓인 것을 보고 발견했다. `node -e "...map(f=>f.path)"` 같은 명령에서 나온다.
 * 테스트가 아니라 **실제로 쌓인 데이터를 눈으로 보고** 잡은 결함이라 AC-18로 못박는다.
 */
function redirectTargets(segment) {
  const targets = [];
  const pattern = /(?<![0-9&>=])>{1,2}(?!&)\s*("[^"]*"|'[^']*'|[^\s;|&<>()]+)/g;
  let match;
  while ((match = pattern.exec(segment)) !== null) {
    targets.push(match[1].replace(/^["']|["']$/g, ""));
  }
  return targets;
}

/** 명령 이름 앞의 `VAR=값` 환경 할당과 `sudo`/`command` 접두어를 걷어낸다. */
function commandName(tokens) {
  let index = 0;
  while (index < tokens.length && /^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[index])) index += 1;
  while (index < tokens.length && ["sudo", "command", "env", "nohup"].includes(tokens[index])) index += 1;
  return { name: tokens[index] ? tokens[index].split("/").pop() : null, argsFrom: index + 1 };
}

/**
 * 명령 하나가 쓰는 파일 경로를 뽑는다.
 * @returns {string[]}
 */
function segmentTargets(segment) {
  const targets = redirectTargets(segment);
  const tokens = tokenize(segment);
  const { name, argsFrom } = commandName(tokens);
  if (!name) return targets;

  const args = tokens.slice(argsFrom);
  const flags = args.filter((a) => a.startsWith("-"));
  const plain = args.filter((a) => !a.startsWith("-"));

  if (MULTI_TARGET.has(name)) {
    targets.push(...plain);
  } else if (LAST_TARGET.has(name)) {
    if (plain.length >= 2) targets.push(plain[plain.length - 1]);
  } else if (name === "sed" && flags.some((f) => /^-[a-zA-Z]*i/.test(f))) {
    // `sed -i '치환식' 파일…` — 첫 평문 인자는 스크립트이므로 건너뛴다.
    targets.push(...plain.slice(1));
  } else if (name === "dd") {
    for (const arg of args) if (arg.startsWith("of=")) targets.push(arg.slice(3));
  }

  return targets;
}

/**
 * Bash 명령이 쓰거나 지우는 파일 경로 목록을 돌려준다. 중복과 비파일 경로는 제거한다.
 * @param {string} command
 * @returns {string[]}
 */
function extractWriteTargets(command) {
  if (typeof command !== "string" || command.trim() === "") return [];

  const stripped = stripHeredocs(command);
  const found = [];
  for (const segment of splitSegments(stripped)) found.push(...segmentTargets(segment));

  const seen = new Set();
  const result = [];
  for (const raw of found) {
    const value = raw.replace(/^["']|["']$/g, "").trim();
    if (value === "" || NON_FILES.has(value) || value.startsWith("/dev/")) continue;
    if (value.includes("*") || value.includes("$")) continue; // 글롭·변수는 해석하지 않는다
    if (seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
}

module.exports = { extractWriteTargets, stripHeredocs, tokenize, splitSegments, redirectTargets };
