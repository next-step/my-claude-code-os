---
name: bag-golden-import
description: core-catalog-platfom의 상품 단위 가방 GT와 기존 가방 추론 결과를 가벼운 JSONL 스냅샷으로 가져온다. "가방 골든셋 가져와", "가방 GT 동기화" 요청에서 사용한다.
---

# 가방 골든셋 가져오기

상품 대상 성별 GT만 사용한다. `image-gender`의 이미지별 모델 외형 GT를 상품 GT로 오해하지 않는다.

```bash
python3 .claude/os/attributes/bag-category-gender/adapters/import_bag_category_gender_sources.py
```

다음을 검증한다.

- `.claude/os/runs/bag-category-gender/golden/bag-product-gt.jsonl`: 상품 단위 가방 정본
- `.claude/os/runs/bag-category-gender/golden/bag-policy-evaluation.jsonl`: 정책 실행 결과와 GT를 함께 담은 감사 입력
- `.claude/os/runs/bag-category-gender/manifest.json`: 건수, 겹치는 상품 수, 라벨 충돌 수

이미지 바이트와 전체 원본 레코드는 복사하지 않는다.
