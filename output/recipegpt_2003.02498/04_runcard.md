# 실행 카드: RecipeGPT (2003.02498)
- **저장소**: https://github.com/LARC-CMU-SMU/RecipeGPT-exp (**공식**) · **고정 커밋/태그**: 없음(master)
- **언어/프레임워크**: Python 3.6 · TensorFlow 1.12 · OpenAI GPT-2 fork · spaCy · zss · Moses multi-bleu.perl
- **진입점**: 생성 `training/gpt-2/src/conditional_gen_web.py` · 평가 `utils/evaluation.py`(+`metrics.py`,`tree.py`,`spacy_func.py`)
- **핵심 의존성**: tensorflow==1.12, spacy(+en모델), zss, gensim, numpy, regex; BLEU는 perl `analysis/multi-bleu.perl`

- **데이터 포맷(그대로 재현 가능)**: 한 레시피 = 단일 시퀀스
  `<start-title>…<end-title> <start-directions>…<end-directions> <start-ingredients>…<end-ingredients>`
  동봉 예시 `data/recipe1M_example/test/{X,y}/*.txt`. 파일접미사 `i`=재료생성, `d`=조리법생성. `X`=입력(생성할 필드 open태그만), `y`=정답. pad토큰 16791, 재료구분 토큰 3, max 512.

- **하이퍼파라미터**: 백본 GPT-2 124M(코드상 '117M') · lr 1e-4 · batch 8 · 512토큰 · ≈5에폭/≈5일/단일 V100. 생성: temperature=1, top_k=0, top_p=0.9(권장), length=n_ctx/2.

- **논문 보고치(테스트, 124M)**: 재료 F1=0.76 · 평균 재료수≈7.8 · BLEU=8.34 · BP=0.71 · ROUGE-L=0.36 · NTED=0.52 · PPL=3.70 · Jaccard(생성)0.53 vs (사람)0.49.

## 브라우저 '실제 동작' 대상 (real, stand-in 아님)
- 특수토큰 포맷 직렬화/파싱 + 필드/재료 셔플 + 패딩
- 재료 **F1**(집합 P/R/F1, `metrics.py`) — 정답 대비 실제 계산
- root-noun 추출 + **재료 겹침 하이라이트** + **Jaccard**(경량 규칙기반이 spaCy 대체)
- **NTED**: 조리법→(동작=노드,재료=리프) 트리 + Zhang-Shasha(zss) 편집거리, (노드합) 정규화
- **BLEU/Brevity Penalty/ROUGE-L**(표준 n-gram, JS로 완전 구현)

## 브라우저 불가 → 라벨된 stand-in
- GPT-2 124M **생성 가중치**(TF 필요) → 경량 생성기 stand-in로 정확한 포맷 레시피 산출, 그 위에서 위 real 지표 실행. 보고치와 나란히 표시.
- **ElasticSearch 최근접 이웃** → 동봉 예시 소집합 TF-IDF/코사인 stand-in
- NTED update의 **word2vec 코사인** → 문자열 유사도 stand-in(트리·zss 골격은 real)

- **최소 실행 경로(원저장소)**: clone → conda(py3.6,tf1.12) → download_model.py 117M → (Recipe1M 준비) → conditional_gen_web.py → utils/evaluation.py. **가중치·데이터 미동봉이라 완전 재현은 무거움** → 브라우저 재현은 위 평가모듈 중심으로.
