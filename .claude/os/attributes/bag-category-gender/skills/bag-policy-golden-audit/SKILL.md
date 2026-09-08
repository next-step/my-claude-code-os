---
name: bag-policy-golden-audit
description: 최신 가방 상세 이미지 실행과 성별 정책·상품 GT를 대조해 정책 직접 근거가 있는 GT 오류 후보와 실행 오류를 분리한다. "정책과 골든셋 비교", "가방 불일치 찾아", "GT 오류 후보" 요청에서 사용한다.
---

# 가방 정책 ↔ 골든셋 감사

먼저 결정론적 감사를 실행한다.

```bash
python3 .claude/os/attributes/bag-category-gender/adapters/audit_bag_category_gender.py
```

`.claude/os/runs/bag-category-gender/run-summary.json`의 `completed=true`와 입력 건수를 확인한다. manifest가
상세 이미지를 읽은 최신 `final-fresh.jsonl`과 `detail-fresh.jsonl`을 가리키는지도 확인한다.
정확도만 보지 말고 다음을 분리한다.

- 정책 문장과 실행 변환이 직접 모순인가
- 같은 상품의 골든셋 소스끼리 라벨이 다른가
- GT와 결과는 같지만 근거가 없는가
- 사람 GT는 답을 갖지만 정책은 답을 못 내는가
- 정책 실행이 강하게 확정했지만 GT가 다른가
- 대상 가방 착용자의 단일 성별 또는 직접 문구가 실행 라벨을 지지해 GT 오류 후보인가
- 실행 라벨과 실행이 기록한 근거가 서로 반대라서 모델 오류인가

상세 근거가 있는 항목에는 `evidenceImageUrls`와 `policyEvidenceSceneIds`를 남긴다. 입력의 빈
`detailEvidence`만 보고 실제 상품 상세에 근거가 없다고 단정하지 않는다.

대표 사례를 해석할 때는 공용 `catalog-golden-adjudicator`에
`.claude/os/attributes/bag-category-gender/profile.json`을 넘겨 사용한다.
