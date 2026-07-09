---
name: coverage-loop
description: |
  목표 테스트 커버리지(goal=N)를 파라미터로 받아,
  목표에 도달할 때까지 backend-dev 에이전트를 반복 실행하는 랄프 루프 스킬.
  각 이터레이션은 독립 컨텍스트(Agent 호출)로 실행되며, 학습 내용은 파일로 누적된다.

  다음 표현에 반드시 사용한다:
  - "/coverage-loop goal=80"
  - "/coverage-loop goal=70 max=3"
  - "커버리지 루프 실행해줘 goal=..."
  - "테스트 커버리지 목표까지 자동으로 올려줘"
---

# Coverage Loop 스킬

JaCoCo 라인 커버리지가 `goal`%에 도달할 때까지 `backend-dev` 에이전트를 반복 실행한다.

**핵심 설계 원칙:**
- 각 이터레이션 = 독립 Agent 호출 → 이전 컨텍스트 없음
- 이터레이션 간 정보 전달 = 오직 learnings 파일 경유
- 종료 조건 = 목표 달성 OR max 초과 (숫자 비교, AI 판단 없음)

---

## Step 0: 파라미터 파싱

args 문자열에서 추출한다.

| 파라미터 | 패턴 | 기본값 |
|---------|------|--------|
| `goal` | `goal=(\d+)` | **필수** — 없으면 중단 |
| `max` | `max=(\d+)` | `5` |

goal이 없으면 사용자에게 아래 메시지를 출력하고 종료한다:
```
goal 파라미터가 필요합니다. 예: /coverage-loop goal=80
```

---

## Step 1: 사전 준비

### 1-1. git 루트 확인

```bash
git rev-parse --show-toplevel
```

이 결과를 `{ROOT}`로 저장한다. 이후 모든 경로는 이 값 기준이다.

### 1-2. habit-tracker 존재 확인

```bash
ls {ROOT}/habit-tracker/build.gradle
```

없으면 "habit-tracker 디렉토리를 찾을 수 없습니다"라고 안내하고 중단한다.

### 1-3. learnings 파일 초기화

```bash
date +%Y-%m-%d-%H-%M
```

경로: `{ROOT}/.claude/logs/loop/{YYYY-MM-DD-HH-MM}-coverage-loop.md`

Write 도구로 파일을 생성한다:

```markdown
# Coverage Loop 학습 기록

- 목표: {goal}%
- 시작: {YYYY-MM-DD HH:MM}
- 최대 이터레이션: {max}

---
```

### 1-4. 초기 커버리지 측정

루프 시작 전 현재 상태를 기록하기 위해 아래 명령을 실행한다:

```bash
cd {ROOT}/habit-tracker && ./gradlew test jacocoTestReport -q 2>&1 | tail -5
```

그 다음 커버리지를 파싱한다:

```bash
python3 -c "
import xml.etree.ElementTree as ET, sys
try:
    tree = ET.parse('{ROOT}/habit-tracker/build/reports/jacoco/test/jacocoTestReport.xml')
    root = tree.getroot()
    for c in reversed(root.findall('./counter[@type=\"LINE\"]')):
        missed = int(c.get('missed', 0))
        covered = int(c.get('covered', 0))
        total = missed + covered
        if total > 0:
            print(f'{covered/total*100:.1f}')
            sys.exit(0)
    print('0.0')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    print('0.0')
"
```

파싱에 실패하면 `0.0`으로 간주하고 루프를 시작한다.
이미 `{goal}%` 이상이면 루프 없이 바로 최종 보고로 이동한다.

---

## Step 2: 이터레이션 루프

`i = 1`부터 `{max}`까지 반복한다. 매 이터레이션:

### A. backend-dev 에이전트 호출 (독립 컨텍스트)

Agent 도구로 `backend-dev` 에이전트를 아래 프롬프트로 호출한다.
**이 호출은 이전 이터레이션과 컨텍스트를 공유하지 않는다.**
이전 이터레이션 정보는 반드시 learnings 파일을 읽어서만 얻어야 한다.

---
**에이전트 프롬프트 템플릿:**

```
[Coverage Loop — 이터레이션 {i}/{max}]

목표 커버리지: {goal}%
learnings 파일 경로: {learnings_path}
프로젝트 루트: {ROOT}

────────────────────────────────
네 역할: 이 이터레이션에서 테스트 커버리지를 높여라.
컨텍스트가 없는 상태에서 시작하므로 반드시 아래 순서를 따라라.
────────────────────────────────

## 1. learnings 파일 읽기 (필수 첫 번째 단계)

{learnings_path} 를 Read 도구로 읽어라.
- 이전 이터레이션에서 어떤 클래스를 다뤘는지 파악
- 발견된 패턴이나 주의사항 파악
- 파일이 없거나 비어있으면 첫 이터레이션으로 간주

## 2. 현재 커버리지 측정

```bash
cd {ROOT}/habit-tracker
./gradlew test jacocoTestReport -q 2>&1 | tail -5
```

커버리지 수치 파싱:
```bash
python3 -c "
import xml.etree.ElementTree as ET, sys
try:
    tree = ET.parse('{ROOT}/habit-tracker/build/reports/jacoco/test/jacocoTestReport.xml')
    root = tree.getroot()
    for c in reversed(root.findall('./counter[@type=\"LINE\"]')):
        missed = int(c.get('missed', 0))
        covered = int(c.get('covered', 0))
        total = missed + covered
        if total > 0:
            print(f'{covered/total*100:.1f}')
            sys.exit(0)
    print('0.0')
except Exception as e:
    print('0.0')
"
```

측정값을 COVERAGE_BEFORE 로 기억한다.

## 3. 목표 달성 여부 확인

COVERAGE_BEFORE >= {goal}% 이면:
- 아래 출력 형식에서 GOAL_MET: true 로 출력하고 종료

## 4. 개선 대상 클래스 선정 (목표 미달 시)

learnings에서 이미 다룬 클래스 목록을 확인한다.
아직 다루지 않은 클래스 중 커버리지가 가장 낮은 것 1~2개를 선정한다.

클래스별 커버리지 확인:
```bash
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('{ROOT}/habit-tracker/build/reports/jacoco/test/jacocoTestReport.xml')
root = tree.getroot()
results = []
for pkg in root.findall('.//package'):
    for cls in pkg.findall('class'):
        name = cls.get('name', '').replace('/', '.')
        for c in cls.findall('counter[@type=\"LINE\"]'):
            missed = int(c.get('missed', 0))
            covered = int(c.get('covered', 0))
            total = missed + covered
            if total > 0:
                pct = covered / total * 100
                results.append((pct, name, missed, total))
results.sort()
for pct, name, missed, total in results[:10]:
    print(f'{pct:5.1f}%  {name}  (missed {missed}/{total})')
"
```

## 5. 테스트 작성

선정된 클래스에 대해 JUnit5 테스트를 작성한다.
- TDD 원칙: Red → Green → Refactor
- 경로: {ROOT}/habit-tracker/src/test/java/...
- 이미 learnings에 기록된 클래스는 건너뛴다
- @SpringBootTest 대신 단위 테스트(@ExtendWith(MockitoExtension.class)) 우선

## 6. 테스트 재실행 및 커버리지 재측정

```bash
cd {ROOT}/habit-tracker && ./gradlew test jacocoTestReport -q 2>&1 | tail -5
```

동일한 방법으로 커버리지를 파싱해 COVERAGE_AFTER 로 기억한다.

## 7. 결과 출력 (이 형식을 정확히 지켜라)

스킬이 아래 형식을 파싱한다. 줄 순서와 키 이름을 바꾸지 마라.

COVERAGE_BEFORE: {측정값}
COVERAGE_AFTER: {재측정값}
GOAL_MET: {true 또는 false}
CLASSES_ADDRESSED: {클래스명1}, {클래스명2}
TESTS_WRITTEN: {숫자}
LEARNED: {이 이터레이션에서 발견한 패턴이나 주의사항 1~2줄}
```
---

### B. Agent 결과 파싱

Agent 출력에서 정규식으로 아래 값을 추출한다:

| 변수 | 패턴 |
|------|------|
| `coverage_after` | `COVERAGE_AFTER:\s*([\d.]+)` |
| `goal_met` | `GOAL_MET:\s*(true\|false)` |
| `classes` | `CLASSES_ADDRESSED:\s*(.+)` |
| `tests_written` | `TESTS_WRITTEN:\s*(\d+)` |
| `learned` | `LEARNED:\s*(.+)` |

`COVERAGE_AFTER:` 라인이 없으면 해당 이터레이션을 오류로 처리하고 루프를 중단한다.

### C. learnings 파일 업데이트

Edit 도구로 learnings 파일 끝에 아래 내용을 추가한다:

```markdown
## 이터레이션 {i} — {HH:MM}

- 커버리지: {COVERAGE_BEFORE}% → {COVERAGE_AFTER}%
- 다룬 클래스: {CLASSES_ADDRESSED}
- 작성한 테스트: {TESTS_WRITTEN}개
- 학습: {LEARNED}

---
```

### D. 루프 종료 조건 확인

아래 중 하나라도 해당하면 루프를 종료한다:

1. `goal_met == true`
2. `i == max`
3. Agent 오류 (사용자에게 알림)

---

## Step 3: 최종 보고

루프 종료 후 아래 형식으로 보고한다.

```
✅ Coverage Loop 완료

목표: {goal}%
최종 커버리지: {coverage_after}%
결과: {달성 ✅ / 미달성 ⚠️ ({max}회 초과)}
총 이터레이션: {실제 실행 수}/{max}

─────────────────────────────
이터레이션 요약
─────────────────────────────
이터레이션 1: XX.X% → XX.X% | {클래스명}
이터레이션 2: XX.X% → XX.X% | {클래스명}
...

─────────────────────────────
누적 학습 기록
─────────────────────────────
{learnings_path}
```

---

## 운영 주의사항

- `./gradlew` 실행 권한 오류 시: `chmod +x {ROOT}/habit-tracker/gradlew` 후 재시도
- 빌드 실패 시(컴파일 에러): 오류 내용을 사용자에게 그대로 출력하고 루프 중단
- 이미 goal 달성 상태면 루프 없이 "이미 {현재}%로 목표 달성 상태입니다"를 출력
