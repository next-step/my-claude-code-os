# Plan — 사용자 텍스트 메모 (Quick Notes)

> 상태: 샘플 · 미구현 · 2026-07 (스냅샷 — 최신화 안 함)

## 재활용할 기존 코드 (조사 결과: 파일/스킬과 어떻게 쓸지)

이 저장소는 애플리케이션 소스 코드가 전혀 없는 **문서·스킬 기반 "개발 OS"** 다(`README.md`, `OS.md`, `.claude/skills/*/SKILL.md`, `docs/prd/`). `package.json`·빌드 도구·테스트 러너도 없다. 따라서 "기존 비즈니스 로직 재활용"은 없고, **재활용 대상은 이 OS의 규약·인프라·패턴**이다.

- **저장 위치·파일 구조 패턴 (`.claude/skill-usage.log`, `.gitignore`)**: 기존 OS는 "한 줄 = 레코드 1건, `값<TAB>값` TSV" 형식 로컬 로그를 `.claude/` 아래에 두고 `.gitignore`로 개인 데이터를 제외한다(`.claude/settings.json` 훅, `skill-stat/SKILL.md`). 메모 저장소도 **같은 철학**으로 한 곳(단일 데이터 파일)에 모은다. 단, 메모는 줄바꿈을 포함할 수 있어 TSV/줄단위로는 깨지므로 **JSON 파일**(JSON array)을 채택한다. 위치는 사용자 개인 데이터이므로 `.claude/skill-usage.log`와 동일하게 **gitignore 대상 로컬 파일**로 둔다.
- **CLI 구현 패턴 (`skill-stat/SKILL.md`)**: 인자 유무로 분기(`$ARGUMENTS`), 데이터 파일 존재 확인(`test -f`) 후 없으면 빈 상태 안내, 표 형태 출력 — 이 "조회 명령" UX를 메모 `list` 출력과 빈 상태 안내에 그대로 차용한다.
- **OS 개발 흐름·테스트 필수 원칙 (`OS.md` 원칙 3, §2 ③, `CLAUDE.md` 규칙 3)**: 구현에 단위/통합 테스트가 필수. 런타임은 **Node.js v22**(이미 설치됨, nvm)로 고정 — 표준 라이브러리만으로 영속화와 `node --test`(내장 테스트 러너) 사용이 가능해 **외부 의존성 0**을 만족하고 PRD의 "복잡한 외부 의존성 없이"에 정합한다.
- **컨벤션 (`OS.md` §6)**: 한국어 출력, 커밋 접두사 — 구현 산출물의 사용자 메시지·문서를 한국어로 작성.

## 열린 질문에 대한 가정 (저장소 정합성 기준)

1. **실행 형태 → CLI.** 이 OS는 전부 터미널/Bash 기반이고 웹·데스크톱 스택이 없다. CLI가 가장 가볍고 자족적이다.
2. **저장 방식 → 로컬 JSON 파일** `.claude/quick-notes.json`(없으면 `[]`로 자동 생성). `skill-usage.log`와 같은 "개인 데이터는 `.claude/` + gitignore" 패턴.
3. **길이 제한 → 1,000자.** 빈 내용 거부(PRD 필수) + 과도 입력 방지 최소 가드.
4. **시각 형식 → ISO 8601(UTC)로 저장, 표시 시 로컬 `YYYY-MM-DD HH:MM`** (절대 시각). `skill-stat`의 `date '+%Y-%m-%d %H:%M:%S'` 표기와 결.
5. **삭제 확인 → 즉시 삭제** (단일 사용자·로컬·범위 단순화). 단 존재하지 않는 id 삭제 시 명확한 에러.
6. **언어/런타임 → Node.js v22 + 내장 모듈만**(`node:fs`, `node:crypto`, `node:test`). 설치된 환경 사용, 의존성 0.

## 손댈 파일 (신규/수정)

신규:
- `src/quick-notes/store.js` — 영속화 계층(순수 로직). `loadNotes()`, `saveNotes()`, `addNote(content)`, `deleteNote(id)`, `listNotes()`. 저장 경로는 인자/환경변수로 주입 가능하게 해 테스트에서 임시 파일을 쓰게 한다(파일 미수정 가능, 테스트 격리).
- `src/quick-notes/cli.js` — CLI 진입점. `add <내용>`, `list`, `delete <id>` 서브커맨드 파싱 → `store.js` 호출 → 한국어 출력/빈 상태 안내/에러 메시지. 종료코드(성공 0, 사용자 오류 1).
- `test/quick-notes/store.test.js` — `node:test` 단위 테스트(아래 전략).
- `test/quick-notes/cli.test.js` — CLI 통합 테스트(`child_process`로 실제 실행).
- `.claude/skills/note/SKILL.md` — `/note add|list|delete` 슬래시 스킬. 내부에서 `node src/quick-notes/cli.js ...`를 호출하는 얇은 래퍼. `allowed-tools: Bash(node:*)`. 기존 스킬과 동일한 frontmatter·한국어 안내 패턴.
- `docs/plan/quick-notes.md` — (이 Plan 문서. `/feature` 흐름 산출물 경로 §0.)

수정:
- `.gitignore` — `.claude/quick-notes.json` 추가(개인 데이터 제외, `skill-usage.log`와 동일 정책).
- `OS.md` §4 도구 표 — `/note` 스킬을 "이 OS 흐름으로 만든 첫 end-to-end 기능 예시"로 한 줄 추가(청사진과 어긋나면 함께 갱신: 원칙 5/CLAUDE.md 규칙 3).
- `package.json` — (선택) 의존성 없이 `"scripts": { "test": "node --test" }`만 둔 최소 파일. 테스트 실행 표준화용. 없어도 `node --test test/`로 동작.

## 구현 단계 (순서대로)

1. **저장 계층 골격**: `store.js`에 경로 주입형 `loadNotes/saveNotes` 구현(파일 없으면 `[]` 반환, 디렉토리 자동 생성, JSON 파싱 실패 시 명확 에러).
2. **도메인 연산**: `addNote(content)` — trim 후 빈 문자열 거부(에러), 1,000자 초과 거부, `id`(`crypto.randomUUID()`)·`content`·`createdAt`(ISO) 부여, **배열 앞에 unshift**(최신순 PRD 시나리오 1). `listNotes()` — 저장된 순서(최신순) 그대로 반환. `deleteNote(id)` — 없으면 에러, 있으면 제거 후 저장.
3. **단위 테스트 작성**(2와 나란히, OS.md §2.4): store 동작 검증(아래 전략). 임시 파일 경로 사용.
4. **CLI 계층**: `cli.js`에서 `process.argv` 파싱 → 서브커맨드 분기 → store 호출 → 한국어 출력. `list`는 빈 상태면 "아직 메모가 없습니다." 안내, 아니면 `[#1] 내용 (작성: YYYY-MM-DD HH:MM)` 형태 목록. `add` 빈 입력/초과 시 안내 + 종료코드 1.
5. **통합 테스트 작성**: `child_process.execFileSync('node', ['src/quick-notes/cli.js', ...])`로 add→list→delete→list 시나리오와 빈 입력 거부, 영속성(재실행 후 잔존)을 임시 데이터 파일(`QUICK_NOTES_PATH` 환경변수 주입)로 검증.
6. **슬래시 스킬**: `.claude/skills/note/SKILL.md` 작성 — 기존 스킬 frontmatter/한국어 안내 패턴 차용, `node src/quick-notes/cli.js`를 호출.
7. **문서/설정 정리**: `.gitignore`·`OS.md` 표·(선택)`package.json` 갱신.
8. **수동 검증**: `node src/quick-notes/cli.js add "..."` → `list` → `delete <id>` → `list`, 재실행 영속성 확인.

## 테스트 전략 (단위/통합 — OS.md 원칙 3, 필수)

러너: **Node 내장 `node:test` + `node:assert`** (의존성 0). 실행: `node --test test/`.

단위 테스트 (`store.test.js`) — 각 테스트는 격리된 임시 파일 경로 사용:
- 빈 저장소 `listNotes()` → `[]`.
- `addNote("안녕")` 후 목록에 1건, `id`/`createdAt`/`content` 존재.
- 여러 건 추가 시 **최신이 배열 맨 앞**(최신순 보장).
- 빈 문자열·공백만·`""` 추가 → **에러(저장 거부)**, 저장소 불변.
- 1,000자 초과 → 에러.
- `deleteNote(존재 id)` → 해당 건만 제거. `deleteNote(없는 id)` → 에러.
- **영속성**: `saveNotes` 후 새로 `loadNotes` 하면 동일 데이터(직렬화 왕복).
- 손상된 JSON 파일 로드 → 명확한 에러(조용한 데이터 유실 방지).

통합 테스트 (`cli.test.js`) — 실제 프로세스 실행, 임시 데이터 경로 주입:
- `add "메모"` → 종료코드 0 + 성공 메시지.
- `list` → 추가한 내용·작성 시각 표시, 최신순.
- 빈 상태 `list` → "아직 메모가 없습니다." 안내.
- `add ""`(빈 입력) → 종료코드 1 + 내용 필요 안내, 파일 미변경.
- `delete <id>` → 제거 후 `list`에서 사라짐.
- `delete 없는id` → 종료코드 1 + 에러.
- **영속성 통합**: add 후 별도 프로세스로 재실행한 `list`에 잔존.

## 위험 요소 / 롤백

- **런타임 도입의 정합성**: 지금까지 순수 문서/Bash OS였는데 Node 소스가 처음 들어온다. 완화 — 외부 의존성 0(내장 모듈만), `package.json`은 test 스크립트만, 슬래시 스킬로 OS 흐름에 흡수. PRD의 "복잡한 외부 의존성 없이"와 일치.
- **JSON 동시 쓰기/경합**: 단일 사용자·로컬 가정이라 락 미구현. 동시 실행 시 마지막 쓰기 우선(범위 밖). 향후 필요 시 임시파일+rename 원자적 쓰기로 확장(현재도 rename 패턴 채택 권장).
- **개인 데이터 커밋 사고**: `.claude/quick-notes.json`을 깜빡 커밋. 완화 — `.gitignore` 선반영(`skill-usage.log`와 동일 정책)을 1단계 전에 처리.
- **시간대 혼동**: UTC 저장 + 로컬 표시. 표시값과 저장값 불일치 오인 가능 → 저장은 ISO(UTC), 표시는 로컬임을 스킬 문서에 명기.
- **롤백**: 전부 신규 파일/추가 라인이라 영향 격리. 되돌리려면 `src/quick-notes/`·`test/quick-notes/`·`.claude/skills/note/` 삭제, `.gitignore`/`OS.md`/`package.json`의 추가분만 되돌리면 됨. 기존 스킬·훅·문서에 파괴적 수정 없음.
