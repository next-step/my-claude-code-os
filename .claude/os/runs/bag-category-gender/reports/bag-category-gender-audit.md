# 가방 정책 ↔ 골든셋 감사 결과

## 결론

최신 fresh 실행은 상세 이미지를 실제로 읽었다. 정책의 직접 근거와 실행 근거가 같은 단일 성별을
지지하지만 현재 GT가 다른 **GT 오류 후보는 20건**이다. 이 큐가 가장
먼저 볼 대상이다. 예전 실행의 빈 `detailEvidence`만 보고 만든 ‘근거 없는 일치’ 보고서는 상세 이미지
근거를 누락했으므로 정본으로 사용하지 않는다.

`EGOOCM:3398529`는 상세 8장을 읽었고 여성 모델 착용과 오간자·리본 결합 신호로 `FEMALE`을
냈지만 GT는 `UNISEX`다. 정책의 근거 우선순위 2와 일치하므로 GT 오류 후보 큐에 포함했다.

## 전체 수치

- 평가 상품: 500건
- 최신 실행의 현재 GT 대비 정확도: 82.80%
- 정책 직접 근거가 있는 GT 오류 후보: 20건
- 공유 이미지 과잉 제거에서 복구된 상품: 4건
- 상세 이미지 URL 수집 실패에서 복구된 상품: 1건
- 가방 WORN 상호작용 정책에서 복구된 상품: 223건
- 전체 상세 타일 처리 완료: 410/410건
- 실행 라벨과 실행 근거가 서로 반대: 1건
- 단일 성별 결과와 GT가 다르지만 추가 검토 필요: 17건
- 근거 없는 UNISEX 변환: 48건
- 골든셋 소스 차이: 10건
- GT 분포: {'FEMALE': 288, 'MALE': 39, 'UNISEX': 173}

## 1. 정책 직접 근거가 있는 GT 오류 후보

- `EGOOCM:3398529` [세이프선데이 스트랩 숄더백 (오간자네이비)](https://www.29cm.co.kr/products/3398529): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3399281` [홀로홀로 원터치 밀크 텀블러 보온보냉병 구름파우치 - 핑크](https://www.29cm.co.kr/products/3399281): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3399286` [홀로홀로 원터치 밀크 텀블러 보온보냉병 구름파우치 - 코코아](https://www.29cm.co.kr/products/3399286): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3400602` [소가죽 버티컬 힙색 크로스백 IB25Z3MBH2689](https://www.29cm.co.kr/products/3400602): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`남성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3400648` [소가죽 메탈 브리프 케이스 IB25A3MBR1237](https://www.29cm.co.kr/products/3400648): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`남성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3404922` [스윗 도트 스트링 짐색 (아이보리)](https://www.29cm.co.kr/products/3404922): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3411572` [데님 방패 포켓 백팩 인디고 다크](https://www.29cm.co.kr/products/3411572): GT=`MALE`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3417183` [\[본사직영\]컬럼비아 공용 본레 포레스트 20L 패커블 경량 백팩 라이트그레이 (C76YU0369060)](https://www.29cm.co.kr/products/3417183): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3442201` [\[루즈앤라운지\] 모데나 호보 패브릭 RA2F7ABG024WP1BK](https://www.29cm.co.kr/products/3442201): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3448548` [NIMO_5color](https://www.29cm.co.kr/products/3448548): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3458963` [\[루즈앤라운지\] 모데나 숄더 RA2F7ABG023WBK](https://www.29cm.co.kr/products/3458963): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`
- `EGOOCM:3483889` [스탁사인 인비즈 크로스백](https://www.29cm.co.kr/products/3483889): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`

## 2. 실행 결과와 실행 근거가 서로 모순인 사례

- `MUSINSA:6080311` [에브리데이 보스턴 백 (M) 5colrs](https://www.musinsa.com/products/6080311): GT=`FEMALE`, 정책 실행=`MALE`, 근거=`여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.`

## 3. 추가 시각 검토가 필요한 정책↔GT 충돌

- `EGOOCM:3413959` [\[루즈앤라운지\] 알베로 숄더 RA2F7ABG151WBK](https://www.29cm.co.kr/products/3413959): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`탈부착 파우치 구성의 숄더백으로 여성용 디자인 특성을 보임`
- `EGOOCM:3420004` [\[키링 악세사리\] 체리 케이프 & 스커트](https://www.29cm.co.kr/products/3420004): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`체리 패턴의 프릴 케이프와 스커트 디자인은 여성용 장식 결합 신호에 해당함`
- `EGOOCM:3424883` [\[CITY LINE\] 빅 더플백 HPABFFA302](https://www.29cm.co.kr/products/3424883): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`더플백 형태의 기능적 구조와 디자인으로 남녀 공용 사용 가능`
- `EGOOCM:3442337` [\[루즈앤라운지\] 네오 살바토레 토트 RA2F9ABG101WBK](https://www.29cm.co.kr/products/3442337): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`작은 사이즈와 구조적 탑핸들, 부드러운 가죽 소재의 여성용 토트백 디자인`
- `EGOOCM:3447598` [Light Duffle Bag (M) White](https://www.29cm.co.kr/products/3447598): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`기능적 구조의 더플백으로 성별 구분 없는 디자인임`
- `EGOOCM:3448296` [Mini Handmade Net Bag - BLACK](https://www.29cm.co.kr/products/3448296): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`미니 사이즈와 구조적 형태가 여성용 디자인 결합 신호에 해당함`
- `EGOOCM:3448515` [Handmade Loop Bag - BURGUNDY](https://www.29cm.co.kr/products/3448515): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`미니 사이즈와 짧은 스트랩, 섬세한 루프 짜임의 여성용 디자인`
- `EGOOCM:3448530` [Handmade Loop Bag - KHAKI](https://www.29cm.co.kr/products/3448530): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`미니 사이즈와 섬세한 짜임 구조가 결합된 여성용 디자인`
- `EGOOCM:3451405` [Handmade Loop Bag - BROWN](https://www.29cm.co.kr/products/3451405): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`미니 사이즈와 짧은 탑핸들 구조가 결합된 여성용 디자인`
- `EGOOCM:3456202` [CARINA S (Ivory)](https://www.29cm.co.kr/products/3456202): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`미니 사이즈, 카드지갑 겸 백으로 활용되는 구조적 형태와 디자인`
- `EGOOCM:3474392` [Blue garden basic pouch(M)](https://www.29cm.co.kr/products/3474392): GT=`UNISEX`, 정책 실행=`MALE`, 근거=`기능적 구조의 파우치로 성별 구분 없는 디자인임`
- `MUSINSA:4881768` [마이멜로디 쿠로미 그레이 미디움 코코 크로스바디 \[4346.HC02\]](https://www.musinsa.com/products/4881768): GT=`UNISEX`, 정책 실행=`FEMALE`, 근거=`마이멜로디와 쿠로미 캐릭터 그래픽이 적용된 미니 사이즈 크로스바디 가방입니다.`

## 다음 행동

1. `golden-policy-violation-candidate.jsonl`의 상세 근거 이미지를 검수한다.
2. 대상 가방과 단일 성별 모델 연결이 확인되면 GT 수정 판정을 기록한다.
3. `model-policy-contradiction.jsonl`은 GT가 아니라 실행 버그로 분리한다.
4. 근거 없는 UNISEX는 내부 UNDETERMINED 보존 여부를 결정한다.
