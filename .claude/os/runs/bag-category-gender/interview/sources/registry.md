# 성별 추론 버전·프롬프트 레지스트리

성별 추론 결과를 다시 재현하고 품질을 비교하기 위한 **버전의 정본**이다.

이 문서에서 말하는 버전은 세 가지를 분리한다.

| 구분 | 바뀌는 것 | 예시 |
| --- | --- | --- |
| 알고리즘 버전 | 입력을 접는 순서, 하드 룰, 판정 의미 | `V500` → `V501` |
| 프롬프트 버전 | 모델에 보내는 지시문·응답 계약 | `thumbnail-...-v101-...`, `product-gender-...-v500-...` |
| 평가/하네스 버전 | GT, split, 평가 코드와 리포트 형식 | `clothing-product-gender-split/v1` |

따라서 프롬프트가 그대로여도 판정 순서나 HTML 처리 규칙이 바뀌면 알고리즘 버전은 올라간다. 반대로
프롬프트 문구만 바뀌고 상품 폴드 계약도 바뀌었다면 프롬프트 버전과 알고리즘 버전을 각각 기록한다.

## 현재 파이프라인

```text
V101 썸네일 이미지별 모델 성별
        + 상품명·신발 사이즈
        + 비의류 상세 HTML 텍스트
        + 상세 이미지 상품 성별(의류 V1000 2-stage 상세 경로, 신발·기타 V500)
        ↓
V502 상품 타깃 성별 폴드
```

여기서 V101은 “사진에 보이는 모델이 어떤 성별로 관찰되는가”를 판단하고, V501은 “상품을 어떤 성별
고객에게 판매하는가”를 판단한다. 둘은 정답의 의미가 다르므로 한 버전 번호로 합치지 않는다.

## 버전 레지스트리

### 이미지 축

| 버전 | 상태 | 공식 식별자 | 역할 | 비고 |
| --- | --- | --- | --- | --- |
| V100 | 과거 호환 | `thumbnail-apparent-gender-grouped-v100-independent-compact-factors-no-mixed` | 이미지 독립 판정의 이전 계약 | 기존 결과 재현용. 새 실행의 기본값이 아님 |
| V101 | 현재 | `thumbnail-apparent-gender-grouped-v101-independent-compact-output` | 이미지별 `id/presence/gender` compact 응답 | V100의 판정 규칙은 유지하고 응답 필드만 운영 계약으로 축소 |

V101의 운영 스키마는 `id`, `presence`, `gender`이며 허용 gender는 `MALE`, `FEMALE`,
`PERSON_UNCLEAR`, `NO_PERSON`이다. `MIXED`는 이미지 모델의 와이어 값이 아니라 상품 폴드에서
남녀 이미지 투표를 합친 결과다.

관련 코드:

- 프롬프트 버전·SHA: `core/src/main/java/com/musinsa/ccp/core/platform/gender/application/support/GenderInferenceExecutionContract.java`
- 프롬프트 문면: `core/src/main/java/com/musinsa/ccp/core/platform/gender/application/support/GenderInferencePrompts.java`
- 제출 메타데이터: `core/.../platform/gender/adapter/out/promptflow/PromptWorkflowGenderInferenceAdapter.java`
- 응답 스키마: `core/.../promptflow/engine/gender/GenderGroupedSchemaProvider.java`

### 상품 축

| 버전 | 상태 | 공식 식별자 | 역할 | 비고 |
| --- | --- | --- | --- | --- |
| V500 | 과거 기준선 | `V500` | V100 계열 이미지 관찰과 상품명·상세 근거를 기존 순서로 접음 | 2026-08-21 리포트의 과거 기준선. 최신 Java 최종 품질로 부르면 안 됨 |
| V501 | 과거 알고리즘 | `V501` | V101·상품명·카테고리별 상세 근거를 접음. 의류 상세 신호는 의류상품성별 V1000 | V502 승격 전 결과 재현용 |
| V502 | 현재 알고리즘 | `V502` | V101·상품명·카테고리별 상세 근거를 접음. 5개 대상 카테고리는 Mapper → Judge의 2-stage 상세 경로 | Mapper는 성별을 판정하지 않고 Judge의 `MATCH` 관찰만 fold에 사용함 |

V502의 비의류 우선순위는 다음과 같다(비의류는 V501과 동일).

1. 신발의 강한 등록 사이즈
2. 상품명 명시 성별
3. 썸네일 `MIXED`
4. 상세 HTML의 실제 텍스트 노드에 있는 명시 성별
5. 상세 이미지 상품 성별
6. 썸네일 단성 투표
7. 근거 없음(`UNDETERMINED`)

HTML의 `img alt`, `src`, 태그, script/style, 주석은 텍스트 근거로 읽지 않는다. 예를 들어
`<img alt="남성용"><p>여성용</p>`는 `여성용`만 읽어 여성 신호가 된다.

의류 V1000은 다음 순서로 접는다.

1. 상품명 명시 성별
2. V101 전체 썸네일 합집합 `UNISEX`
3. 최신 성공 V1000 상세 이미지 결론
4. V101 썸네일 단성 투표
5. 근거 없음(`UNDETERMINED`)

의류의 상세 HTML 키워드는 이 폴드에 사용하지 않는다. 이는 해당 HTML이 구하기
어렵다는 의미가 아니라, V1000 품질을 승격한 전체 리포트의 최종 결정이 HTML을
입력으로 쓰지 않았기 때문이다.

V502는 의류·신발·스포츠/레저·가방·잡화의 상세 입력을 Mapper와 Judge로 분리한다.

1. `DETAIL_SCENE_MAPPING`은 192px·4-up·최대 768 output token으로 전체 타일을 ID 배열로
   매핑한다. Mapper는 성별·사람-상품 일치·SKU를 판정하지 않는다.
2. selector는 Mapper의 위치 정보만 사용해 사람 장면·성별 원문·인접 장면·상품 anchor를
   선택한다. soft cap은 8장, hard cap은 12장이다. Mapper ID가 누락·중복되거나 선택 결과가
   비면 실패로 닫고 Judge를 호출하지 않는다.
3. `DETAIL_RESOLUTION` Judge는 선택 타일만 역할에 따라 384px·2-up 또는 512px·1-up으로 보고,
   의류의 `TARGET_REFERENCE`는 256px로 제공한다. Judge JSON에는 각 관찰의 `subjectId`,
   `subjectRegion`, 구조화 `skuIdentity`가 있어야 한다.
4. 관찰 성별은 `targetProductMatch=MATCH`인 대상 착장만 다시 집계한다. 판매자 입력 성별과
   Mapper 분류는 상품 성별 근거가 아니다.
5. `DETAIL_RESOLUTION` Judge 결과를 최종 상세 결론으로 사용한다.

V502는 상품 폴드 알고리즘 버전이다. 상세 LLM은 카테고리별로 분기하지만 5개 대상 카테고리
모두 Mapper → Judge의 selected-only 구조를 사용한다.

| stage | 현재 프롬프트 식별자 |
| --- | --- |
| GROUPED 썸네일 | `thumbnail-apparent-gender-grouped-v101-independent-compact-output` |
| 의류 Scene Mapper | `clothing-scene-mapper-role-routing-v6` |
| 의류 상세 Judge | `clothing-evidence-judge-scene-role-v11` |
| 일반 상세 | `product-gender-detail-resolution-v500-gender-evidence-contact-sheet-v7` |
| 신발 상세 | `product-gender-detail-resolution-v500-shoes-gender-evidence-contact-sheet-v7` |

위 표는 Java 운영 경로의 식별자다. 의류 V502는 `DETAIL_SCENE_MAPPING`에서 192px·4-up·최대
768 output token으로 전체 타일을 위치만 훑은 뒤, selector가 soft cap 8·hard cap 12를 적용한다.
`DETAIL_RESOLUTION` Judge는 256px `TARGET_REFERENCE`와 선택 상세 384px·2-up을 사용하고,
생략 타일은 모델에 보내지 않고 감사 ID로만 남긴다. 캠페인·혼성·불명확 사람 장면도
Judge가 같은 입력에서 판단한다. 증분 실시간과 백필 배치는 같은 composer를 사용한다.
새 stage에는 고정 문면의
`prompt_sha256`과 상품명·전체 카테고리 문맥까지 합친 `effective_prompt_sha256`을 함께 남긴다.
합성기가 실제로 그린 `TARGET_REFERENCE/DxxTyy` 목록도 `rendered_source_image_ids`에 기록하며,
파서는 이 목록에 없던 근거 ID를 거절한다.

Python 하네스와 Java는
`tool/image-gender/gt-harness/fixtures/v1000-java-parity-golden.json`을 단일 golden fixture로
공유한다. 프롬프트 SHA, 상품 식별 문맥 SHA, 최대 20타일 균등 샘플의 원본 DxxTyy 위치를 한
파일로 고정한다.
V1000 재현 parity 테스트 두 건(`ProductGenderPolicyTest`, `GenderInferenceResponseParserTest`)의
입력도 gitignore 되는 `results/` 실행물이 아니라 추적 fixture
`fixtures/clothing-v1000-parity-v1.jsonl`(260행)과 `fixtures/detail-v1000-parity-v1.jsonl`(433행)을
읽는다. 출처와 승격 사유는 각 fixture 옆의 `.provenance.json`에 기록한다.
하네스에서 V502를 선택하면 Mapper 192px·4-up·768 output tokens, Judge 384px·2-up·선택 최대
12타일·256px reference의 selected-only Judge와 Java와 같은 JSON response
schema가 자동 적용된다. 캐시는 model, stage prompt version, canonical/effective SHA,
composer/schema/reducer version, maxTokens가 모두 같은 성공 행만 재사용한다.

| 하네스 단계 | 프롬프트 식별자 | 핵심 계약 |
| --- | --- | --- |
| 의류 상세 2장 묶음 현재 기준선 | `product-gender-detail-resolution-v501-verified-evidence-v11` | 214/236(90.68%)로 현재 권장. 착용 의복 종류, 색상 관계, 색상 외 상품 정체성을 분리해 관찰 |
| 의류 상세 2장 묶음 축약 실험 | `product-gender-detail-resolution-v501-verified-evidence-v13-diet` | 전체 측정 207/236(87.71%)로 회귀해 승격하지 않음 |
| 의류상품성별 V1000 개발명 | `product-gender-detail-resolution-v501-verified-evidence-v14-scope-guard` | 전체 품질 측정에 사용한 개발 식별자. 프롬프트 문면·SHA는 V1000과 동일하며 신규 호출에는 사용하지 않음 |
| 의류상품성별 V1000 | `clothing-product-gender-v1000` | 과거 단일 호출 공식 식별자. 신규 Java 실행의 기본값이 아님 |
| 의류상품성별 V502 Mapper | `clothing-scene-mapper-role-routing-v6` | 모든 타일을 192px·4-up으로 routing. 최종 성별·상품 연결을 판정하지 않음 |
| 의류상품성별 V502 Judge | `clothing-evidence-judge-scene-role-v11` | selector 타일을 384px·2-up으로 직접 판독. 관찰에 subjectId·subjectRegion·skuIdentity 요구 |

V11에서는 색상이 다르다는 이유만으로 `MISMATCH`를 만들 수 없다. 의복 종류와 로고·그래픽·절개·
실루엣 같은 색상 외 정체성이 모두 일치하면 다른 색상 옵션도 `MATCH`다. 반대로 색상 외 정체성이
실제로 다르면 기존처럼 `MISMATCH`다. 프롬프트 응답뿐 아니라 하네스 parser도 같은 규칙을 적용해,
색상 외 차이가 검증되지 않은 `MISMATCH`를 `UNCLEAR`로 낮춘다.

V13-diet은 이 판정 계약과 JSON 스키마를 유지하면서 중복된 UNISEX 근거·상품 연결·MODEL INFO
제외 설명을 합쳤다. 본문은 5,246자에서 2,936자로 44.03% 줄었다.
대표 6개 fresh 호출은 V11 결론을 유지했지만, 전체 202개 무캐시 호출에서는 7개가 회귀해
214/236(90.68%)에서 207/236(87.71%)로 하락했다. 입력 비용은 전체 상품 평균 1.97원에서
1.75원으로 약 11.1% 감소했지만 품질 손실이 더 크므로 현재 프롬프트로 승격하지 않는다.

의류상품성별 V1000(개발명 V14-scope-guard)은 V13의 단어 탐지 결과를 그대로 신뢰하지 않는다.
V1000의 공식 프롬프트 식별자는 `clothing-product-gender-v1000`이다. 최초 승격 시에는 V14 전체 측정 뒤
문면을 바꾸지 않아 당시 prompt SHA와 품질 수치를 기준선으로 보존했다. 2026-08-27부터는 실제 입력과
모순되는 판매자 등록 성별 미제공 안내와 `일반적인 의복 형태`만으로 자동 `UNCLEAR`를 만드는 문구를
제거했다. 가려져 상품을 확인할 수 없는 경우의 `UNCLEAR`와 의복 종류·색상 외 특징 검증은 유지한다.
이 변경은 canonical/effective prompt SHA를 바꾸므로 변경 전 결과를 신규 호출 캐시로 재사용하지 않는다. 성별 문구는
`PRODUCT / BRAND_OR_COMMON / MODEL_PROFILE / UNCLEAR`, 표 문구는
`PRODUCT_SIZE_TABLE / MODEL_PROFILE / COMMON_GUIDE / UNCLEAR` 범위와 원본 이미지 ID를 함께
반환한다. 하네스는 `PRODUCT`와 실제 상품 사이즈 행이 있는 `PRODUCT_SIZE_TABLE`만 최종 근거로
채택한다. 캠페인에서는 브랜드 로고와 일반 실루엣만으로 상품 MATCH를 만들지 않으며, 반바지와
긴바지처럼 의복 종류·길이가 다른 착장은 제외한다. `4448140`, `6624759`를 각각 10회 무캐시로
호출한 표적 검증에서는 최종 판정과 중간 근거가 10/10 일관됐다. 202개 상세 호출을 모두 새로 한
전체 의류 측정은 207/236(87.71%)로 V13과 엄격 GT 점수가 같았다. V13 대비 판정 변경은 7건,
GT상 개선 3건·회귀 3건·미분류 GT 변경 1건이다. 요청 오답 두 건은 모두 교정됐지만 전체 점수
개선은 확인되지 않았지만, 표적 오염 차단과 근거 감사 가능성을 우선해 의류 운영 프롬프트로
지정했다. 엄격 GT 자체의 오표기 가능성은 별도 정제 과제로 남긴다.

2026-08-31 일반 착장 상품 연결은 색상·작은 로고·패치·작은 그래픽의 저해상도 차이를 다른 상품
근거로 사용하지 않도록 강화했다. 의복 종류 또는 넥라인·전체 길이·소매·여밈·주요 포켓 위치로
확인되는 전체 실루엣이 명확히 다를 때만 `MISMATCH/OTHER_SKU`로 기록한다. 전체 실루엣 자체가
가려져 비교할 수 없으면 `UNCLEAR`다. 캠페인 장면은 다른 SKU 오탐을 막기 위해 기존의 고유 디자인
검증 규칙을 유지한다. 이 변경은 prompt SHA와 role-aware Judge 버전을 함께 갱신하며, 기존 응답
캐시를 재사용하지 않는다.

최종 상품 폴드는 상세 우선이더라도 관찰을 덮어쓰지 않고 합친다. V101 전체 썸네일에서 남성과
여성이 이미 확인된 `UNISEX`는 상세에서 한쪽 성별만 다시 관찰되어도 유지한다.

비용 최적화 실행에서는 상품명 명시 성별 또는 V101 썸네일 `UNISEX`로 상세 단계 전에 결론이 난
상품도 상세 모델 호출 대상에서 제외한다. 한쪽 성별 썸네일은 상세가 더 많은 정보를 추가할 수 있으므로
제외하지 않는다.

정확한 승격 기준은
`tool/image-gender/gt-harness/results/v501-v14-scope-guard-full-no-cache-2026-08-26/clothing-v501-v14-scope-guard.html`의
260건 실행이다. 해당 실행은 상품명/V101 선확정 후 남은 202건을 무캐시로 상세 호출했고,
과거 단일 호출 계약은 기준선으로만 보존한다.
이 실행물 자체는 gitignore 되는 `results/`에만 있었고 로컬에서도 소실되어, Java 재현 테스트는
현행 문면의 2026-08-27 무캐시 실행에서 승격한 `fixtures/*-v1000-parity-v1.jsonl`을 읽는다.
V502 Java의 입력·parser·폴드·비용 최적화는 Mapper → Judge 계약을 재현한다.

## V501을 도입한 이유

V500이라는 이름을 그대로 쓰면 다음 두 가지를 구별할 수 없다.

- 과거 V100 관찰값을 접은 2026-08-21 기준선
- V101과 최신 상세 HTML 입력을 사용하는 현재 Java 폴드

V501로 올리면 “같은 상품을 다시 계산했지만 내부 판정 규칙이 달라졌다”는 사실을 결과 파일과
리포트에서 숨기지 않을 수 있다. 과거 V500 결과는 삭제하거나 덮어쓰지 않고 그대로 보존한다.

## 결과에 반드시 남길 메타데이터

모델 호출 또는 상품 폴드 결과에는 다음 값을 함께 남긴다.

| 필드 | 예시 | 목적 |
| --- | --- | --- |
| `algorithmVersion` | `V502` | 2-stage 의류 상세 입력·상품 폴드 규칙 식별 |
| `thumbnailPromptVersion` | V101 공식 식별자 | 이미지 축 재현 |
| `detailPromptVersion` | 카테고리별 Mapper/Judge 또는 일반 detail 공식 식별자 | 상세 stage별 LLM 재현 |
| `promptSha256` | SHA-256 | 같은 이름인데 문구가 바뀐 경우 탐지 |
| `effectivePromptSha256` | 고정 문면 + 상품 식별 문맥 SHA-256 | 상품별 실제 요청 재현 |
| `schemaVersion` | `gender-v101-compact` | 응답 필드 계약 식별 |
| `reducerVersion` | `product-gender-fold-v502` | MATCH 관찰만 재집계하는 결정론적 폴드 식별 |
| `model` | 실제 모델명 | 모델 교체 영향 추적 |
| `sourceImageIds` | 실제 호출에 사용한 원본 이미지·타일 ID | 호출 입력 감사와 재현. 자동 상품 재추론 여부는 해시로 결정하지 않음 |
| `renderedSourceImageIds` | `TARGET_REFERENCE`, `D01T01`, ... | 모델 근거가 실제 화면에 있었는지 검증 |
| `gtSnapshot` | GT 스냅샷 날짜/해시 | 평가 정답 버전 식별 |

## 버전 올리는 규칙

1. 판정 우선순위, 키워드, HTML 정제, 이미지 투표, `UNISEX`/`UNDETERMINED` 의미가 바뀌면
   `algorithmVersion`을 올린다.
2. 프롬프트 문구, 응답 JSON 스키마, 모델 입력 형식이 바뀌면 해당 `promptVersion` 또는
   `schemaVersion`을 올리고 SHA-256을 새로 기록한다.
3. GT나 split만 바뀌면 알고리즘 버전은 올리지 않고 `gtSnapshot` 또는 `evaluationVersion`을
   올린다.
4. 모델만 교체해도 결과 비교가 필요하므로 모델명과 실행 시각을 반드시 남긴다. 프롬프트·폴드 계약이
   같으면 알고리즘 버전은 유지할 수 있다.
5. 과거 결과 파일은 새 버전 결과로 덮어쓰지 않는다. 파일명과 리포트에 버전을 함께 넣는다.

## V501 품질 측정 기준

V501의 공식 품질 측정은 V101 썸네일 결과와 최신 상세 입력을 사용해 의류 GT를 다시 추론한 뒤,
상품 단위로 평가한다. 이미지 단위 V101 정확도와 상품 단위 V501 정확도를 한 숫자로 합치지 않는다.

측정 리포트에는 최소한 다음을 포함한다.

- GT snapshot과 대상 상품 수
- V101 이미지 입력 수와 prompt SHA
- 상세 HTML 텍스트 입력 보유율
- 판정 출처별 건수(`NAME`, `DETAIL_TEXT`, `DETAIL_IMAGE`, `IMAGES`, `NONE`)
- accuracy, macro F1, 라벨별 precision/recall
- `MALE↔FEMALE` 직접 오류와 `UNISEX`/`UNDETERMINED` 혼동
- 모델·프롬프트·알고리즘 버전

현재 저장된 2026-08-21 V500 리포트는 과거 기준선으로 보존하며, V501 공식 점수로 승격하지 않는다.

2026-08-25에는 최신 V101 썸네일과 저장된 V500 상세 증거를 사용한 결정론적 재현 측정을
`results/v501-clothing-replay-2026-08-25.md`로 남겼다. 최신 원문 HTML을 다시 추출한 배치가 아니므로
이 결과는 V501 공식 점수가 아니라 입력 재현 가능성을 확인하는 중간 점검으로 취급한다.

같은 날 최신 공개 상세 이미지 60개를 일반 상세 v7 프롬프트로 다시 추론한 부분 fresh 측정도
`results/v501-detail-fresh-2026-08-25/v501-detail-fresh.md`로 남겼다. Verbatim textSignal은 저장값이므로
공식 V501-fresh는 아니며, 결과는 211/236(89.41%)였다. 최신 상세가 최종 준거가 된 40건의 정답률은
23/40(57.50%)로 낮았다. 이 결과 때문에 일반 상세 v7은 “현재 식별자”로 보존하되 차기 상세
프롬프트의 기준선으로 승격하지 않는다. 차기 버전은 최종 상품 라벨 대신 직접 문구·대상 착장 모델·
상품 전용 사이즈 같은 관찰값을 구조화하고 reducer에서 판정해야 한다.
