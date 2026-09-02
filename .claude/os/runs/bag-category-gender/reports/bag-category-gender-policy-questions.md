# 가방 성별 정책 질문서

## GQ-GT-001

- 질문: 정책의 직접 근거가 단일 성별을 지지하는데 GT가 UNISEX인 사례를 GT 오류로 확정할 것인가?
- 영향: `{"candidates": 20, "femaleCandidates": 14, "maleCandidates": 6}`
- 권고: 상세 근거 이미지를 우선 검수하고, 근거가 실제 대상 가방과 연결되면 GT를 수정한다.

## GQ-RUN-001

- 질문: 근거가 없을 때 내부 UNDETERMINED를 최종 UNISEX로 바꿔도 되는가?
- 영향: `{"affected": 48, "unsupportedCorrect": 16, "wrongAgainstGt": 32}`
- 권고: 평가에서는 UNDETERMINED를 보존하고 저장 호환 변환은 별도 projection으로 분리한다.

## GQ-SOURCE-001

- 질문: 두 GT 소스 중 어느 버전을 정본으로 사용할 것인가?
- 영향: `{"differentRows": 10, "labelToLabel": 5, "unclassifiedToLabeled": 5}`
- 권고: 최신 사람 검수 원장을 정본으로 지정하고 datasetVersion과 라벨 해시를 평가 입력에 기록한다.
