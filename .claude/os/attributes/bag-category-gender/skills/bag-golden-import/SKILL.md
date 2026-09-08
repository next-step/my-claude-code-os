---
name: bag-golden-import
description: core-catalog-platfom의 상품 단위 가방 GT와 기존 가방 추론 결과를 가벼운 JSONL 스냅샷으로 가져온다. "가방 골든셋 가져와", "가방 GT 동기화" 요청에서 사용한다.
---

# 가방 골든셋 가져오기

상품 대상 성별 GT만 사용한다. `image-gender`의 이미지별 모델 외형 GT를 상품 GT로 오해하지 않는다.

```bash
python3 .claude/os/attributes/bag-category-gender/adapters/import_bag_category_gender_sources.py
```

## GT는 한 파일이 아니다

원본 저장소의 가방 GT는 두 계보로 갈라져 있고, **합쳐서 들이지 않는다.**

| 계보 | 파일 | 이 OS에서의 자리 |
|---|---|---|
| 검수 시트 | `bags-product-gt-<날짜>.jsonl` | 정본 GT 스냅샷. 검수 탭 라벨과 리뷰어 이름이 남는다 |
| 채점 | `bags-product-context-gt-<날짜>.jsonl` | 감사가 실행과 대조하는 GT. 하네스가 정확도를 재는 라벨 |
| 정정 이력 | `bags-product-gt-user-corrections-<날짜>.jsonl` | 두 계보에 얹힌 사람 정정. 출처 기록용 |

둘 중 하나를 골라 덮으면 `GOLDEN_SOURCE_CONFLICT`가 사라진다. 두 사람이 같은 상품을
다르게 봤다는 사실이 곧 산출물이므로, 어댑터는 양쪽을 각각 스냅샷으로 남기고
어긋난 건을 큐에 올린다. 어느 쪽을 정본으로 삼을지는 판례 `BG-0003`이 답한다.

날짜는 코드에 박지 않는다. 어댑터가 이름의 날짜가 가장 늦은 파일을 고르고, 고른 경로와
해시를 `manifest.json`에 남긴다.

## 정책 스냅샷은 자리표시자를 채운 뒤 뜬다

판정 프롬프트는 `{{BAG_OBSERVATION_SAFETY}}` 같은 자리표시자로 공용 문장을 불러온다.
자리표시자째 뜬 스냅샷은 정책이 아니라 정책의 겉면이다 — 보수 규칙이 통째로 빠진 채
감사가 돌아간다. 어댑터가 조각 파일을 찾아 채우고, 조각마다 해시를 남긴다.
채우지 못한 자리표시자가 있으면 멈춘다.

## 다음을 검증한다

- `.claude/os/runs/bag-category-gender/golden/bag-product-gt.jsonl`: 검수 시트 계보
- `.claude/os/runs/bag-category-gender/golden/bag-policy-evaluation.jsonl`: 실행 결과에 채점 계보 GT를 얹은 감사 입력
- `.claude/os/runs/bag-category-gender/manifest.json`: `goldenLineages`의 계보별 날짜와 경로,
  `integrity`의 겹치는 상품 수·라벨 충돌·GT가 갈린 건수·채점 GT가 없는 상품

이미지 바이트와 전체 원본 레코드는 복사하지 않는다.
