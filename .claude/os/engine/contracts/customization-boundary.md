# 카탈로그 데이터 감사 OS의 변경 경계

이 OS는 **공통 코어**와 **속성 프로필·어댑터**를 분리한다. 새 속성을 추가할 때 공통 코어를
복사하지 않는다. 콘센트는 그대로 두고, 새 가전제품의 플러그만 규격에 맞추는 방식이다.

## 변경하지 않는 부분

| 공통 코어 | 보장하는 것 |
|---|---|
| `run_catalog_cycle.py` | 가져오기 → 감사 → 정책 인덱스 → 진행률 → HTML의 실행 순서 |
| 큐 계약 | `signal`, `reason`, `productKey`, `referenceLabel`, `observedLabel` |
| 출처 manifest | 원본 경로·커밋·dirty 여부·SHA-256으로 재현 가능성 기록 |
| 사람 판정 원장 | AI 추천과 사람 확정을 분리하고, `supersedes`로 변경 이력 보존 |
| `build_review_progress.py` | 여러 큐의 같은 상품을 한 건으로 합쳐 진행률 계산 |
| `render_catalog_report.py` | 속성명과 신호 정의를 프로필에서 읽어 정적 HTML 세 장 생성 — 표지, 의심되는 GT 찾기, 빈 정책 찾기 |
| `build_policy_index.py` | 소유 정책·판례의 계약 검증과 정책 공백의 추적 여부 판정 |

공통 코어에는 `성별`, `MALE`, `가방` 같은 도메인 규칙을 넣지 않는다.

## 속성마다 변경하는 부분

| 교체 지점 | 가방 성별 예시 | 소재 속성이라면 |
|---|---|---|
| 프로필 | `attributes/bag-category-gender/profile.json` | `attributes/product-material/profile.json` |
| 소유 정책 | `attributes/bag-category-gender/policy/` | `attributes/product-material/policy/` |
| 가져오기 어댑터 | 가방 프롬프트와 상품 GT 추출 | 소재 정책과 소재 GT 추출 |
| 감사 어댑터 | `UNDETERMINED → UNISEX` 모순 탐지 | 혼용률 누락, 대표 소재 규칙 탐지 |
| 허용 라벨 | MALE/FEMALE/UNISEX/... | COTTON/WOOL/POLYESTER/... |
| 정책 질문 | 공용과 판단 불가의 경계 | 혼방에서 대표 소재를 정하는 기준 |

## 실행 순서

```
import 어댑터 → audit 어댑터 → build_policy_index → build_review_progress → render_catalog_report
```

정책 인덱스가 audit 뒤에 오는 이유는, audit이 만든 `reports/policy-questions.json`을 읽어
"이 질문에 답할 판례가 있는가"를 판정해야 하기 때문이다.

## 새 속성 추가 체크리스트

1. `attributes/<프로필ID>/profile.json`에 이름, 출력 폴더, 라벨, 신호 설명을 쓴다.
   신호마다 `lane`(`GT` · `POLICY` · `RUNTIME`)을 적어 두면, 심판 어댑터가 없어도 보고서가
   그 신호를 의심되는 GT·의심되는 정책·실행 결함 중 어디에 놓을지 안다. 심판이 있으면 심판의 귀책이 이긴다.
2. `attributes/<프로필ID>/policy/policy.md`를 만든다. 뼈대는 `engine/templates/policy.md`에 있다.
   프로필에 `policy` 블록(`owned`, `precedents`, `imported`)을 추가한다.
   자세한 계약은 [policy-layer.md](policy-layer.md)를 본다.
3. import 어댑터가 `runs/<프로필ID>/`에 `policy/`, `golden/`, `manifest.json`을 만든다.
   (선택) 상품별 이미지 목록을 `golden/` 아래 JSONL로 만들고 프로필 `gallery`에 경로를 적으면,
   사례 보고서가 상품마다 대표 이미지와 상세 타일을 밀집해 싣는다. 행 계약은
   `{productKey, thumbnails: [{url, label?, presence?, note?}], details: [{url, sceneId?, label?}]}`이고,
   `url`이 http가 아니면 run 폴더 기준 상대 경로다(로컬 파일은 `asset/`에 복사해 둔다).
   `sceneId`가 큐의 `policyEvidenceSceneIds`와 맞으면 그 타일을 근거 장면으로 강조한다.
4. audit 어댑터가 공통 큐 계약의 JSONL과 `runs/<프로필ID>/reports/policy-questions.json`을 만든다.
5. `run_catalog_cycle.py --profile <프로필>`을 실행한다.
6. HTML에서 속성명·신호·상품이 하드코딩 없이 보이는지 확인한다.
7. `runs/<프로필ID>/reports/policy-status.md`의 위반 목록이 곧 첫 할 일 목록이다.

2번은 건너뛸 수 있다. `policy` 블록이 없는 프로필은 정책 레이어 단계를 그냥 지나간다.
다만 그 속성은 "우리가 옳다고 정한 문장"을 갖지 못한 채, 가져온 스냅샷만으로 굴러간다.

## 입력과 산출물

| | 위치 | 지워도 되는가 |
|---|---|---|
| 입력 | `engine/contracts/` · `engine/scripts/` · `attributes/<프로필ID>/` | 아니오. 손으로 쓴 것이다 |
| 산출물 | `runs/<프로필ID>/` | 예. 사이클을 다시 돌리면 재생성된다 |

이 경계가 무너지는 가장 흔한 방식은 손으로 쓴 정책을 `runs/` 안에 두는 것이다.
`runs/`는 언제든 지울 수 있어야 하므로, 소유 정책은 반드시 `policy/`에 둔다.

어댑터는 원본 데이터를 공통 언어로 번역하는 통역사다. 원본 필드가 `productGender`든
`materialCode`든 큐로 나올 때는 `referenceLabel`과 `observedLabel`로 맞춘다.
