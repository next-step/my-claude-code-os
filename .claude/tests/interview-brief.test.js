/**
 * requirement-interview 산출물("인터뷰 브리프")의 형식·완결성 인수 테스트.
 *
 * 이 테스트가 검증하는 것은 **브리프의 형식과 완결성**이지 인터뷰의 품질이 아니다.
 * "좋은 질문을 했는가"는 자동 판정 대상이 아니며, 사람 승인(04단계)과
 * `policy-reviewer`의 몫으로 남긴다. 이 경계를 흐리면 "테스트가 초록불이니
 * 인터뷰가 잘 됐다"는 착각이 생기고, 그게 이 스킬의 가장 위험한 실패 모드다.
 *
 * 실행: node --test .claude/tests/*.test.js
 *        (Node 26에서는 디렉터리 인자 형태 `node --test .claude/tests/` 가 모듈 로딩 오류를 낸다)
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { REQUIRED_SLOTS, readBrief, validateBrief } = require("../lib/interview-brief.js");

const fixture = (name) => fs.readFileSync(path.join(__dirname, "fixtures", "interview", name), "utf-8");

test("AC-1: 6개 슬롯이 모두 채워지고 분류가 유효하면 통과한다", () => {
  const result = validateBrief(fixture("good.md"));

  assert.equal(result.ok, true, `통과해야 한다: ${JSON.stringify(result)}`);
  assert.deepEqual(result.missingSlots, []);
  assert.deepEqual(result.placeholders, []);
  assert.deepEqual(result.violations, []);
});

test("AC-2: 필수 슬롯 6개가 정의되어 있고 순서가 고정되어 있다", () => {
  assert.deepEqual(REQUIRED_SLOTS, ["목표", "현재 상태", "기대 동작", "완료 조건", "범위 밖", "미해결 가정"]);
});

test("AC-3: 슬롯 제목이 아예 없으면 missingSlots에 담긴다", () => {
  const result = validateBrief("# 인터뷰 브리프: 무언가\n\n- 분류: bounded\n\n## 목표\n한 문장이다.\n");

  assert.equal(result.ok, false);
  assert.ok(result.missingSlots.includes("범위 밖"), "없는 슬롯이 보고되어야 한다");
  assert.ok(result.missingSlots.includes("미해결 가정"));
  assert.equal(result.missingSlots.includes("목표"), false, "채워진 슬롯은 보고되지 않는다");
});

test("AC-4: 슬롯 제목만 있고 본문이 비면 missingSlots에 담긴다", () => {
  const result = validateBrief(fixture("missing-slots.md"));

  assert.equal(result.ok, false);
  assert.deepEqual(result.missingSlots, ["현재 상태"], "빈 본문만 결손으로 잡힌다");
});

test("AC-5: 본문에 남은 플레이스홀더(TBD/TODO/???/미정 등)를 슬롯 이름과 함께 보고한다", () => {
  const result = validateBrief(fixture("placeholder.md"));

  assert.equal(result.ok, false);
  assert.equal(result.placeholders.length, 1, `1건이어야 한다: ${JSON.stringify(result.placeholders)}`);
  assert.equal(result.placeholders[0].slot, "현재 상태");
  assert.equal(result.placeholders[0].token, "TBD");
});

test("AC-6: '미해결 가정' 슬롯의 미정 표현은 플레이스홀더로 잡지 않는다", () => {
  // 이 슬롯은 애초에 '아직 안 정한 것'을 적는 자리라서, 같은 어휘라도 결손이 아니라 산출물이다.
  const brief = fixture("placeholder.md");
  const result = validateBrief(brief);

  assert.equal(
    result.placeholders.some((item) => item.slot === "미해결 가정"),
    false,
    "미해결 가정 안의 '미정'은 정상이다"
  );
});

test("AC-7: 목표가 두 문장 이상이면 위반으로 잡는다", () => {
  const brief = fixture("good.md").replace(
    "skill-stat 출력에 가장 최근 사용한 스킬 이름과 시각을 함께 보여준다.",
    "최근 사용 스킬을 보여준다. 그리고 통계 화면도 새로 만든다."
  );
  const result = validateBrief(brief);

  assert.equal(result.ok, false);
  assert.ok(
    result.violations.some((message) => message.includes("목표")),
    `목표 위반이 보고되어야 한다: ${JSON.stringify(result.violations)}`
  );
});

test("AC-8: '범위 밖'이 '없음'뿐이면 위반으로 잡는다", () => {
  const result = validateBrief(fixture("missing-slots.md"));

  assert.ok(
    result.violations.some((message) => message.includes("범위 밖")),
    `범위 밖 위반이 보고되어야 한다: ${JSON.stringify(result.violations)}`
  );
});

test("AC-9: 분류가 없거나 허용되지 않은 값이면 위반으로 잡는다", () => {
  const missing = validateBrief(fixture("good.md").replace("- 분류: bounded\n", ""));
  assert.ok(missing.violations.some((message) => message.includes("분류")));

  const invalid = validateBrief(fixture("good.md").replace("- 분류: bounded", "- 분류: 대충"));
  assert.ok(invalid.violations.some((message) => message.includes("분류")));
});

test("AC-10: 완료 조건에 관측 가능한 표현이 없으면 경고만 하고 통과는 막지 않는다", () => {
  const brief = fixture("good.md").replace(
    /## 완료 조건\n[\s\S]*?\n\n## 범위 밖/,
    "## 완료 조건\n- 잘 동작한다\n\n## 범위 밖"
  );
  const result = validateBrief(brief);

  assert.equal(result.ok, true, "형식으로 확신할 수 없는 것은 실패시키지 않는다");
  assert.ok(result.warnings.length > 0, "대신 경고로 사람에게 넘긴다");
});

test("AC-11: 브리프 파일을 읽되 없으면 null을 돌려주고 파일은 수정하지 않는다", () => {
  const filePath = path.join(__dirname, "fixtures", "interview", "good.md");
  const before = fs.readFileSync(filePath, "utf-8");

  assert.equal(readBrief(path.join(__dirname, "fixtures", "interview", "없는파일.md")), null);
  assert.equal(typeof readBrief(filePath), "string");
  assert.equal(fs.readFileSync(filePath, "utf-8"), before, "읽기 전용이어야 한다");
});
