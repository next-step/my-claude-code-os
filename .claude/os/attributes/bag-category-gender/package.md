# bag-category-gender

가방 상품의 대상 고객 성별만 아는 속성 팩. 이 폴더를 지우면 이 속성이 사라지고,
엔진은 그대로 돈다.

이름은 `<대상>-<속성>`이다 — **가방 카테고리**의 상품에 붙는 **대상 고객 성별** 라벨.
가방의 성별도, 사람의 성정체성도 아니다. 쇼핑에서 상품을 거르기 위한 분류 라벨이고
그 경계는 [goal.md](goal.md)가 정한다. `engine`·`interview`가 역할 이름인 것과 달리
이 폴더는 **인스턴스** 이름이라 `attributes/` 아래에 산다. 속성이 늘면 옆으로 늘어난다.

## 소유

| 종류 | 파일 |
|---|---|
| 선언 | `profile.json` — 라벨·신호 11종·어댑터 경로 |
| 목표 | `goal.md` — 정책과 골든셋이 충돌할 때의 귀책 원칙 |
| 소유 정책 | `policy/policy.md` + `policy/precedents/BG-*.md` |
| 어댑터 | `adapters/import_bag_category_gender_sources.py` · `adapters/audit_bag_category_gender.py` · `adapters/arbiter_bag_category_gender.py` |
| 진입점 | `run.sh` |
| 테스트 | `tests/test_bag_policy_evidence.py` · `tests/test_arbiter.py` |
| 스킬 | `skills/` — `bag-category-gender-os` · `bag-policy-import` · `bag-golden-import` · `bag-policy-golden-audit` · `bag-policy-question` · `bag-golden-decision` · `bag-review-progress` · `bag-ambiguity-review` · `bag-category-gender-interview` |
| 에이전트 | 없다. 상품 판정과 인터뷰는 공유 `catalog-*` 에이전트에 `profile.json`을 넘긴다 |
| 진입점 링크 | `.claude/skills/<이름>` → 여기. 실체는 이 패키지가 소유한다 |
| 산출물 | `.claude/os/runs/bag-category-gender/` (재생성 가능, 소유가 아니라 출력) |

## 규칙

- 어댑터는 **통역사**다. 원본이 `productGender`든 무엇이든 큐로 나올 때는
  `referenceLabel`·`observedLabel`로 맞춘다. 원본 필드명이 엔진에 새어 나가면 경계가 무너진다.
- `adapters/arbiter_bag_category_gender.py`는 `policy/policy.md`의 근거 우선순위를 옮긴 것이다.
  **정책이 바뀌면 여기도 같이 바뀌어야 한다.** 새 판단을 어댑터에서 만들지 않는다.
- 정책 원본은 `policy/`에 있고, `runs/bag-category-gender/policy/`에 있는 것은 외부에서 가져온
  읽기 전용 스냅샷이다. 둘이 다르면 `policy/`가 옳다.

## 실행

```bash
.claude/os/attributes/bag-category-gender/run.sh
```

`run.sh`는 두 패키지를 잇는 자리다 — 엔진 사이클을 돌리고, 끝나면 `review`에 심사를 넘긴다.
넘기는 것은 프로필이 아니라 **산출물 폴더 하나**다. 엔진은 심사를 모르고 심사는 속성을 모르므로,
둘을 아는 유일한 곳이 이 파일이다.

## 검증

```bash
python3 -m pytest .claude/os/attributes/bag-category-gender/tests -q
```
