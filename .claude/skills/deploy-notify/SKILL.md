---
name: deploy-notify
description: AWS CodePipeline 배포 진행 상황을 관찰해 PushNotification으로 알려주는 스킬. "/deploy-notify <파이프라인 이름> [주기 N분]"으로 실행하면 사전 검증 후 자동으로 /loop 관찰을 시작하고, 이후 N분마다 현재 스테이지를 알림으로 보낸다. "배포 알림", "파이프라인 관찰", "/deploy-notify" 요청 시 사용.
metadata:
  author: frontend-yoonseo
  version: "1.0.0"
  argument-hint: "[파이프라인 이름] [주기 N분, 기본 3분] (내부용: 관찰 반복 <파이프라인 이름>)"
---

# deploy-notify

AWS CodePipeline 스테이지 진행 상황을 N분마다 관찰해 PushNotification으로 알린다.
Slack/Notion 연동 없음 (OS.md Step 3 범위 — 완료 후 Slack/Notion 업데이트가 필요하면 별도 스킬로 다룬다).

---

## 0단계: 인자 파악

인자가 "관찰 반복"으로 시작하면 나머지를 파이프라인 이름으로 파싱하고 아래 단계를 모두 건너뛰어 [관찰 반복 실행](#관찰-반복-실행)으로 이동한다.

- 이름을 못 찾으면 `BLOCKED: 파이프라인 이름 누락`을 출력하고 종료한다 (루프가 이 메시지를 반복하지 않도록 재시도하지 않음).

그 외의 경우 인자에서 `<파이프라인 이름>`과 `[주기 N분]`(생략 시 기본 3)을 추출해 1단계로 진행한다.

- 파이프라인 이름이 없으면 사용자에게 되묻는다. 설정 단계는 1회성이라 질문 가능하다 (task-impl 랄프 모드가 "진입 전 점검에서만 질문 가능"으로 정한 것과 같은 이유 — 관찰 반복 중에는 새 컨텍스트라 되물을 수 없음).

---

## 1단계: 사전 검증

아래 명령 하나로 설치 여부·인증·권한·이름 오류를 한 번에 확인한다 (검증 전용 API를 별도로 부르지 않음 — 최소 호출):

```bash
aws codepipeline get-pipeline-state --name "<파이프라인 이름>" --output json
```

- 성공 → 2단계로 진행
- 실패 → [예외 처리](#예외-처리)의 해당 항목을 안내하고 **루프를 시작하지 않고 종료**

---

## 2단계: 관찰 루프 시작

검증 통과 시 Skill 도구로 `/loop Nm /deploy-notify 관찰 반복 <파이프라인 이름>`을 실행한다. (`N`은 1단계에서 파싱한 주기, 기본 3.)

호출 후 아래 형식으로 한 번만 출력하고 종료한다:

```
관찰을 시작했습니다: <파이프라인 이름> (N분 간격)
파이프라인이 종료 상태(성공/실패)에 도달하면 알림 후 자동으로 멈춥니다.
```

---

## 관찰 반복 실행

`/deploy-notify 관찰 반복 <파이프라인 이름>`으로 재호출됐을 때의 절차 (매 사이클마다 `/loop`가 새 컨텍스트로 호출). 이전 반복의 기억에 의존하지 않고 매번 AWS를 다시 조회해서 판단한다. 상태 파일은 두지 않는다 — 파이프라인 이름은 매 호출의 인자로 전달되고, 현재 스테이지는 매번 AWS 응답이 원본이라 영속화할 게 없다.

**1. 조회**

```bash
aws codepipeline get-pipeline-state --name "<파이프라인 이름>" --output json
```

조회 자체가 실패하면(네트워크 등 일시적 오류) 알림 없이 이번 사이클만 조용히 넘어간다 — `DONE`/`BLOCKED`가 아니라 루프는 그대로 유지한다 (일시적 오류로 관찰을 끊지 않기 위함).

**2. 스테이지 판정**

skill-stats와 동일하게 Python 헤레독으로 파싱한다:

```bash
export STATE_JSON="$(aws codepipeline get-pipeline-state --name "<파이프라인 이름>" --output json)"
python3 << 'EOF'
import json, os
from datetime import datetime

data = json.loads(os.environ["STATE_JSON"])
stages = data.get("stageStates", [])

def status_of(s):
    return s.get("latestExecution", {}).get("status")

in_progress = [s for s in stages if status_of(s) == "InProgress"]
failed = [s for s in stages if status_of(s) == "Failed"]
succeeded = stages and all(status_of(s) == "Succeeded" for s in stages)

now = datetime.now().strftime("%H:%M")

if in_progress:
    print(f"PROGRESS|{in_progress[0]['stageName']}|{now}")
elif failed:
    print(f"FAILED|{failed[0]['stageName']}|{now}")
elif succeeded:
    print(f"SUCCEEDED||{now}")
else:
    last = stages[-1] if stages else {}
    print(f"OTHER|{last.get('stageName', '?')}|{status_of(last)}|{now}")
EOF
```

판정 결과:

- `stageStates[].latestExecution.status`가 `InProgress`인 스테이지가 있으면 → 그 스테이지, 진행 중 (계속)
- 없고 하나라도 `Failed`면 → 그 스테이지, 실패 (종료 상태)
- 없고 전부 `Succeeded`면 → 전체 성공 (종료 상태)
- 그 외(`Stopped`/`Stopping`/`Cancelled`/`Superseded` 등) → 마지막 스테이지 상태 그대로, 종료 상태로 취급

**3. 알림 전송**

PushNotification으로 매 사이클 무조건 전송한다 (변경 여부 diff 없음 — 이미 합의된 사양). 메시지는 200자 미만, 마크다운 없이, 한 줄:

- 진행 중: `[deploy-notify] <파이프라인>: <스테이지> 진행 중 (HH:MM)`
- 전체 성공: `[deploy-notify] <파이프라인>: 전체 성공 — 모든 스테이지 완료 (HH:MM)`
- 실패: `[deploy-notify] <파이프라인>: <스테이지> 실패 — 콘솔 확인 필요 (HH:MM)`
- 기타 종료 상태: `[deploy-notify] <파이프라인>: <스테이지> 상태 <상태값> — 수동 확인 필요 (HH:MM)`

**4. 종료 판정 출력**

- 종료 상태(성공/실패/기타) 도달 → `DONE: <파이프라인> 관찰 종료 (<사유>)` 출력, 루프 정지
- 진행 중 → `[관찰] <파이프라인>: <스테이지> 진행 중` 한 줄 출력, 다음 사이클에서 계속

**5. 종료**

즉시 종료한다 (다음 사이클로 체이닝하지 않음). AskUserQuestion은 사용하지 않는다 — 모든 판단이 AWS 응답만으로 기계적으로 결정되므로 애초에 물어볼 게 없다.

---

## 예외 처리

1단계(사전 검증)에서만 적용된다. 관찰 반복 중 조회 실패는 위 "관찰 반복 실행 1. 조회"의 조용히 넘어가는 규칙을 따른다 — 최초 검증을 통과했다면 반복 중 실패 원인은 대부분 일시적 네트워크 문제이지, 권한이 도중에 사라지는 경우는 드물기 때문이다.

- **aws CLI 미설치** (`command not found: aws`): "AWS CLI가 설치되어 있지 않습니다. https://aws.amazon.com/cli/ 에서 설치 후 다시 시도해 주세요." 안내 후 종료
- **인증 실패** (예: `Unable to locate credentials`, `ExpiredToken`): 오류 메시지 그대로 출력 + "`aws configure`로 자격 증명을 설정해 주세요." 안내 후 종료
- **권한 부족** (`AccessDeniedException`): 오류 메시지 그대로 출력 + "이 계정에 codepipeline:GetPipelineState 권한이 있는지 확인해 주세요." 안내 후 종료
- **파이프라인 이름 오류** (`PipelineNotFoundException`): "파이프라인 '<파이프라인 이름>'을 찾을 수 없습니다. 이름을 확인해 주세요." 안내 후 종료

---

## 출력 예시

**1단계 통과 → 2단계 시작:**

```
관찰을 시작했습니다: my-service-pipeline (3분 간격)
파이프라인이 종료 상태(성공/실패)에 도달하면 알림 후 자동으로 멈춥니다.
```

**관찰 반복 중 (진행 중):**

```
[관찰] my-service-pipeline: Deploy 진행 중
```
(동시에 PushNotification: `[deploy-notify] my-service-pipeline: Deploy 진행 중 (14:32)`)

**관찰 반복 종료 (성공):**

```
DONE: my-service-pipeline 관찰 종료 (전체 성공)
```
(동시에 PushNotification: `[deploy-notify] my-service-pipeline: 전체 성공 — 모든 스테이지 완료 (14:41)`)

**1단계 실패 (파이프라인 이름 오류):**

```
파이프라인 'my-service-pipelin'을 찾을 수 없습니다. 이름을 확인해 주세요.
```

---

## 주의사항

- 세션(터미널)이 열려 있는 동안만 동작 — 상시 인프라 아님
- N분 간격 폴링이라 그만큼 지연 있음
- 실행한 사람에게만 알림 (Slack/Notion 연동은 범위 밖)
- 상태 파일 없음 — 매 사이클 AWS를 원본으로 다시 조회
