const test = require("node:test");
const assert = require("node:assert");

const { extractWriteTargets, stripHeredocs } = require("../lib/write-targets.js");

test("AC-1: `>` 리다이렉션 대상을 뽑는다", () => {
  assert.deepStrictEqual(extractWriteTargets("echo hi > out.txt"), ["out.txt"]);
});

test("AC-2: `>>` 추가 리다이렉션도 뽑는다", () => {
  assert.deepStrictEqual(extractWriteTargets("echo hi >> log.md"), ["log.md"]);
});

test("AC-3: 히어독 본문은 무시한다 (마크다운 인용부호 오인 방지)", () => {
  const command = ["cat > guide.md <<'EOF'", "> 인용문입니다", "cmd > 가짜.txt", "EOF"].join("\n");
  assert.deepStrictEqual(extractWriteTargets(command), ["guide.md"]);
});

test("AC-4: fd 리다이렉션(`2>&1`, `>&2`)은 파일로 보지 않는다", () => {
  assert.deepStrictEqual(extractWriteTargets("node x.js 2>&1"), []);
  assert.deepStrictEqual(extractWriteTargets("echo err >&2"), []);
});

test("AC-5: /dev/* 경로는 충돌 대상이 아니다", () => {
  assert.deepStrictEqual(extractWriteTargets("cmd > /dev/null"), []);
});

test("AC-6: 글롭과 변수가 든 경로는 해석하지 않고 버린다", () => {
  assert.deepStrictEqual(extractWriteTargets("rm *.tmp"), []);
  assert.deepStrictEqual(extractWriteTargets("cat x > $OUT"), []);
});

test("AC-7: rm/touch/tee는 평문 인자 전부를 대상으로 본다", () => {
  assert.deepStrictEqual(extractWriteTargets("rm -f a.md b.md"), ["a.md", "b.md"]);
  assert.deepStrictEqual(extractWriteTargets("tee -a log.txt"), ["log.txt"]);
});

test("AC-8: cp/mv는 마지막 인자만 대상으로 본다 (원본은 읽기)", () => {
  assert.deepStrictEqual(extractWriteTargets("cp src.md dst.md"), ["dst.md"]);
  assert.deepStrictEqual(extractWriteTargets("mv a.md b.md"), ["b.md"]);
});

test("AC-9: `sed -i`는 첫 평문 인자(치환식)를 건너뛰고 나머지를 대상으로 본다", () => {
  assert.deepStrictEqual(extractWriteTargets("sed -i.bak 's/a/b/' c.md d.md"), ["c.md", "d.md"]);
});

test("AC-10: `-i` 없는 sed는 파일을 쓰지 않으므로 대상이 없다", () => {
  assert.deepStrictEqual(extractWriteTargets("sed -n '1,5p' c.md"), []);
});

test("AC-11: 같은 경로가 여러 번 나와도 한 번만 돌려준다", () => {
  assert.deepStrictEqual(extractWriteTargets("echo a > x.md && echo b >> x.md"), ["x.md"]);
});

test("AC-12: 빈 입력과 비문자열은 빈 배열", () => {
  assert.deepStrictEqual(extractWriteTargets(""), []);
  assert.deepStrictEqual(extractWriteTargets(null), []);
  assert.deepStrictEqual(extractWriteTargets(undefined), []);
});

test("AC-13: `dd of=` 대상을 뽑는다", () => {
  assert.deepStrictEqual(extractWriteTargets("dd if=a of=b.img"), ["b.img"]);
});

test("AC-14: 따옴표로 감싼 경로는 따옴표를 벗겨 돌려준다", () => {
  assert.deepStrictEqual(extractWriteTargets('echo x > "공백 있는.md"'), ["공백 있는.md"]);
});

test("AC-15: `&&`·`;`·`|`로 이어진 여러 명령을 각각 검사한다", () => {
  assert.deepStrictEqual(extractWriteTargets("cp a.md b.md && rm c.md ; echo z > d.md"), [
    "b.md",
    "c.md",
    "d.md",
  ]);
});

test("AC-16: 읽기 전용 명령에서는 아무 대상도 나오지 않는다", () => {
  assert.deepStrictEqual(extractWriteTargets("grep -c foreignObject *.svg"), []);
  assert.deepStrictEqual(extractWriteTargets("git status --porcelain"), []);
  assert.deepStrictEqual(extractWriteTargets("node --test .claude/tests/x.test.js"), []);
});

test("AC-17: stripHeredocs는 종료 구분자와 본문을 모두 제거한다", () => {
  const command = ["cat > f <<'EOF'", "본문", "EOF", "echo done"].join("\n");
  assert.strictEqual(stripHeredocs(command), ["cat > f <<'EOF'", "echo done"].join("\n"));
});

test("AC-18: 화살표 함수 `=>`를 리다이렉션으로 오인하지 않는다", () => {
  // 실제로 세션 보드에 `f.path`가 쌓여서 발견한 결함(2026-09-07).
  assert.deepStrictEqual(extractWriteTargets('node -e "a.map(f=>f.path)"'), []);
  assert.deepStrictEqual(extractWriteTargets('node -e "x.filter(t=>t.ok)" > out.json'), ["out.json"]);
});
