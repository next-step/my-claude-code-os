---
name: bag-policy-import
description: core-catalog-platfom의 가방 상품 대상 성별 프롬프트를 프로젝트 내부 정책 스냅샷으로 가져오고 출처 해시를 남긴다. "가방 정책 가져와", "성별 프롬프트 동기화" 요청에서 사용한다.
---

# 가방 정책 가져오기

원본 저장소는 읽기만 한다. 기본 원본은 형제 경로 `../core-catalog-platfom`이다.

```bash
python3 .claude/os/attributes/bag-category-gender/adapters/import_bag_category_gender_sources.py
```

실행 후 `.claude/os/runs/bag-category-gender/policy/bag-category-gender.md`와
`.claude/os/runs/bag-category-gender/manifest.json`의 `policy` 출처·해시를 확인한다.
원본 저장소가 dirty이면 스냅샷은 만들되, 리뷰 결과에 그 사실을 밝혀 재현 범위를 구분한다.
