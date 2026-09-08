# 가방 정책 ↔ 골든셋 감사 결과

## 결론

최신 fresh 실행은 상세 이미지를 실제로 읽었다. 정책의 직접 근거와 실행 근거가 같은 단일 성별을
지지하지만 현재 GT가 다른 **GT 오류 후보는 12건**이다. 이 큐가 가장
먼저 볼 대상이다. 예전 실행의 빈 `detailEvidence`만 보고 만든 ‘근거 없는 일치’ 보고서는 상세 이미지
근거를 누락했으므로 정본으로 사용하지 않는다.

`EGOOCM:3398529`는 상세 8장을 읽었고 여성 모델 착용과 오간자·리본 결합 신호로 `FEMALE`을
냈지만 GT는 `UNISEX`다. 정책의 근거 우선순위 2와 일치하므로 GT 오류 후보 큐에 포함했다.

## 전체 수치

- 평가 상품: 500건
- 최신 실행의 현재 GT 대비 정확도: 82.60%
- 정책 직접 근거가 있는 GT 오류 후보: 12건
- 공유 이미지 과잉 제거에서 복구된 상품: 4건
- 상세 이미지 URL 수집 실패에서 복구된 상품: 1건
- 가방 WORN 상호작용 정책에서 복구된 상품: 223건
- 전체 상세 타일 처리 완료: 410/410건
- 실행 라벨과 실행 근거가 서로 반대: 1건
- 단일 성별 결과와 GT가 다르지만 추가 검토 필요: 12건
- 근거 없는 UNISEX 변환: 48건
- 골든셋 소스 차이: 51건
- GT 분포: {'FEMALE': 316, 'MALE': 38, 'UNISEX': 146}

## 1. 정책 직접 근거가 있는 GT 오류 후보

- `EGOOCM:3407206` [스포츠 미니 크로스백 - 블랙(QQ323ABG81)](https://www.29cm.co.kr/products/3407206): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3417183` [\[본사직영\]컬럼비아 공용 본레 포레스트 20L 패커블 경량 백팩 라이트그레이 (C76YU0369060)](https://www.29cm.co.kr/products/3417183): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3420094` [TOTE BROCLE \[SUEDE MOCHA COMBI\]](https://www.29cm.co.kr/products/3420094): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3458125` [Leather Strap Double Pouch (Black)](https://www.29cm.co.kr/products/3458125): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3460326` [Rio Square Middle Bag_2colors](https://www.29cm.co.kr/products/3460326): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3484743` [트래블러 패스포트 RFID차단 개인정보 보호 여행지갑 여권 케이스 지갑 - 체커보드](https://www.29cm.co.kr/products/3484743): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `MUSINSA:4459402` [MULTI POUCH 003 Olive Green](https://www.musinsa.com/products/4459402): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`남성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `MUSINSA:4870915` [A90 28인치 화물용 도어식오픈 확장형 캐리어](https://www.musinsa.com/products/4870915): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `MUSINSA:4924741` [로프 키링 짐색 \[브라운 비즈\]](https://www.musinsa.com/products/4924741): GT=`FEMALE`, 정책 실행=`MALE`, 근거=`남성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `MUSINSA:4973361` [아비스코 힙팩 6 (23200306)](https://www.musinsa.com/products/4973361): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `MUSINSA:5356269` [라운드 볼륨 무지 에코백 RVS-147 데님 블랙](https://www.musinsa.com/products/5356269): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`남성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `MUSINSA:5356353` [라운드 볼륨 펜타곤포켓 크로스백 RVP-150 차콜](https://www.musinsa.com/products/5356353): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`남성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`

## 2. 실행 결과와 실행 근거가 서로 모순인 사례

- `MUSINSA:6080311` [에브리데이 보스턴 백 (M) 5colrs](https://www.musinsa.com/products/6080311): GT=`FEMALE`, 정책 실행=`MALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`

## 3. 추가 시각 검토가 필요한 정책↔GT 충돌

- `EGOOCM:3413959` [\[루즈앤라운지\] 알베로 숄더 RA2F7ABG151WBK](https://www.29cm.co.kr/products/3413959): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`탈부착 파우치 구성의 숄더백으로 여성용 디자인 특성을 보임`
- `EGOOCM:3425317` [\[슈베어\] 메쉬 포켓 백팩 HPADZFA201](https://www.29cm.co.kr/products/3425317): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`기능과 구조가 명확한 표준 백팩 디자인으로 남녀 공용 사용 가능`
- `EGOOCM:3447598` [Light Duffle Bag (M) White](https://www.29cm.co.kr/products/3447598): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`기능적 구조의 더플백으로 성별 구분 없는 디자인임`
- `EGOOCM:3474392` [Blue garden basic pouch(M)](https://www.29cm.co.kr/products/3474392): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`기능적 구조의 파우치로 성별 구분 없는 디자인임`
- `MUSINSA:3539191` [라이트파스텔 프리미엄 여행용파우치 6종세트 캐리어정리 수납 정리파우치](https://www.musinsa.com/products/3539191): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여행용 파우치 세트로 기능과 구조가 명확한 공용 상품임`
- `MUSINSA:3588401` [크런치 폴디드 나일론 토트백 (블랙)](https://www.musinsa.com/products/3588401): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`없음`
- `MUSINSA:4928720` [경량 트래블 백팩 - 블랙(QQ223ABP41)](https://www.musinsa.com/products/4928720): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`없음`
- `MUSINSA:4970995` [허그 크로스백 - 블랙 / 219912780872](https://www.musinsa.com/products/4970995): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`미니 사이즈와 구조적 탑핸들, 여성용 디자인 결합 신호 확인됨`
- `MUSINSA:4982054` [르꼬끄X그로서리스터프 크로스백 - 레드(QQ223XBG41)](https://www.musinsa.com/products/4982054): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`없음`
- `MUSINSA:5400801` [\[SS25\] 맨티스 2 웨이스트 팩](https://www.musinsa.com/products/5400801): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`없음`
- `MUSINSA:5872187` [\[키링증정\] 사인로고 벨트 백팩 - BLACK](https://www.musinsa.com/products/5872187): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`없음`
- `MUSINSA:6056063` [\[앞판 오픈형\] N265ASU330 타르가 캐리어 24형 IVORY](https://www.musinsa.com/products/6056063): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`캐리어는 구조와 기능이 명확한 공용 여행용 가방입니다.`

## 다음 행동

1. `golden-policy-violation-candidate.jsonl`의 상세 근거 이미지를 검수한다.
2. 대상 가방과 단일 성별 모델 연결이 확인되면 GT 수정 판정을 기록한다.
3. `model-policy-contradiction.jsonl`은 GT가 아니라 실행 버그로 분리한다.
4. 근거 없는 UNISEX는 내부 UNDETERMINED 보존 여부를 결정한다.
