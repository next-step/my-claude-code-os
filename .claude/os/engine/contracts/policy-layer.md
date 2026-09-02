# 소유 정책 레이어 계약

이 OS에는 정책이 두 벌 있다. 섞으면 안 된다.

| 구분 | 위치 | 누가 쓰는가 | 재생성 |
|---|---|---|---|
| **소유 정책** | `.claude/os/attributes/<프로필ID>/policy/` | 사람이 직접 쓴다 | 안 됨. 지우면 끝 |
| **가져온 스냅샷** | `.claude/os/runs/<프로필ID>/policy/` | import 어댑터가 쓴다 | 매 사이클 덮어씀 |

`runs/`는 언제든 지우고 다시 만들 수 있어야 한다. 그래서 손으로 쓴 정책을 거기 두지 않는다.
스냅샷은 "지금 프로덕션이 실제로 쓰는 문장"이고, 소유 정책은 "우리가 옳다고 정한 문장"이다.
둘이 다르면 그 차이가 곧 개선 대상이다.

## 디렉터리 구조

```
.claude/os/
  engine/templates/
    policy.md              새 속성 정책의 뼈대
    precedent.md           새 판례의 뼈대
  attributes/<프로필ID>/
    policy/
      policy.md            정책 원본 (사람 소유)
      precedents/
        <판례ID>.md        경계 판정 1건 = 파일 1개
```

## policy.md 계약

프론트매터에 `id`(프로필 ID와 같아야 함), `version`, `owner`, `updatedAt`을 둔다.
본문에는 아래 네 개의 `##` 섹션이 **반드시** 있어야 한다. 하나라도 없으면 사이클이 실패한다.

| 섹션 | 내용 | 없으면 생기는 일 |
|---|---|---|
| `## 허용값` | 닫힌 목록. `` - `LABEL` — 설명 `` 형식 | 열린 목록이면 평가가 불가능하다 |
| `## 근거 우선순위` | 근거가 충돌할 때의 결정 규칙 | 같은 입력에 다른 답이 나온다 |
| `## 판정 불가 조건` | 언제 판정 불가 값을 내는가 | 억지 추출이 가장 흔한 오류원이다 |
| `## 판례` | 경계 판정 파일 링크 | 같은 질문을 두 번 묻게 된다 |

허용값은 `` - `MALE` — 설명 `` 처럼 첫 백틱 토큰을 라벨로 읽는다.

## 판례 계약

판례는 **사람이 한 번 답하면 닫히는 경계 질문 하나**를 담는다. 케이스 라벨이 아니다.

| 프론트매터 | 필수 | 값 |
|---|---|---|
| `id` | 예 | 파일명과 같아야 한다 |
| `profile` | 예 | 프로필 ID |
| `status` | 예 | `OPEN` · `DECIDED` · `SUPERSEDED` |
| `answers` | 아니오 | 닫는 정책 질문 ID (쉼표 구분) |
| `acknowledges` | 아니오 | 알고도 남겨둔 위반 코드 (쉼표 구분) |
| `decision` | `DECIDED`일 때 예 | 확정된 판정 |
| `decidedBy` / `decidedAt` | `DECIDED`일 때 예 | 누가 언제 |
| `supersedes` | 아니오 | 대체한 이전 판례 ID |

`OPEN`은 질문만 있고 답이 없는 상태다. 이걸 파일로 남기는 이유는, 답하지 않은 질문의
개수가 곧 **이 속성의 정책이 얼마나 미완성인지를 보여주는 지표**이기 때문이다.

## 검증과 위반 등급

`build_policy_index.py`가 매 사이클마다 검사하고 `runs/<프로필ID>/policy/policy-index.json`과
`runs/<프로필ID>/reports/policy-status.md`를 만든다.

| 등급 | 뜻 | 사이클 |
|---|---|---|
| `BLOCKING` | 계약 위반. 파일이 없거나 형식이 깨졌다 | 중단 (exit 1) |
| `REVIEW` | 정책과 프로필·질문이 어긋난다 | 계속. 다만 기록에 남는다 |

`REVIEW` 위반은 어떤 판례가 `acknowledges`로 그 코드를 선언하면 `tracked`가 된다.
tracked는 "알고 남겨둔 것", untracked는 "아무도 모르는 것"이다. 이 둘을 구분하는 것이
이 레이어의 핵심이다. 정책 공백 자체는 죄가 아니지만, 추적되지 않는 공백은 죄다.

| 코드 | 등급 | 언제 |
|---|---|---|
| `POLICY_FILE_MISSING` | BLOCKING | `policy.owned` 경로에 파일이 없다 |
| `POLICY_ID_MISMATCH` | BLOCKING | 프론트매터 `id`가 프로필 ID와 다르다 |
| `POLICY_SECTION_MISSING` | BLOCKING | 필수 `##` 섹션이 없다 |
| `POLICY_LABELS_EMPTY` | BLOCKING | 허용값을 하나도 못 읽었다 |
| `PRECEDENT_MALFORMED` | BLOCKING | 판례 프론트매터가 계약을 어겼다 |
| `LABEL_NOT_IN_PROFILE` | REVIEW | 정책 허용값이 프로필 `labels`에 없다 |
| `LABEL_NOT_IN_POLICY` | REVIEW | 프로필 `labels`가 정책 허용값에 없다 |
| `QUESTION_WITHOUT_PRECEDENT` | REVIEW | 정책 질문에 답할 판례 파일이 없다 |
| `UNKNOWN_QUESTION` | REVIEW | 판례가 존재하지 않는 질문을 가리킨다 |

## 새 속성에 정책 레이어 붙이기

1. `.claude/os/attributes/<프로필ID>/policy/`를 만들고 `engine/templates/policy.md`를 복사한다.
2. 프로필 JSON에 `policy` 블록(`owned`, `precedents`, `imported`)을 추가한다.
3. `attributes/<프로필ID>/run.sh`를 돌린다. 위반 목록이 곧 첫 할 일 목록이다.

`policy` 블록이 없는 프로필은 이 단계를 건너뛴다. 정책 레이어는 선택이지, 강제가 아니다.
