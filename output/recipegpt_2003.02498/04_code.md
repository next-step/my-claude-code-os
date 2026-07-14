# 구현 코드 분석: RecipeGPT — Generative Pre-training Based Cooking Recipe Generation and Evaluation System

- **저장소**: https://github.com/LARC-CMU-SMU/RecipeGPT-exp (**공식** — 논문 저자 소속 LARC-CMU-SMU)
- **언어 / 핵심 프레임워크**: Python 3.5/3.6 · TensorFlow 1.12 · OpenAI GPT-2 코드 fork · spaCy · zss(Zhang-Shasha 트리 편집거리) · Moses `multi-bleu.perl`
- **실행 진입점**:
  - 학습: `training/gpt-2/train_ppl_pickle.py`(파인튜닝) / `train_ppl_scratch.py`(from scratch)
  - 생성: `training/gpt-2/src/conditional_gen_web.py`(웹 백엔드용) / `conditional_gen_dir.py`(디렉토리 배치)
  - 평가: `utils/evaluation.py`(F1·NTED 등) + 노트북 `training/8-evaluation-ppl.ipynb`, `analysis/09-model-performances.ipynb`

## 1. 디렉토리 구조 (핵심만)
```
RecipeGPT-exp/
├─ training/
│  ├─ 6-fine tuning GPT2.ipynb / 7-inference.ipynb / 8-evaluation-ppl.ipynb
│  └─ gpt-2/                     # OpenAI GPT-2 fork (수정본)
│     ├─ train_ppl_pickle.py     # 파인튜닝 루프 (perplexity 학습)
│     ├─ train_ppl_scratch.py
│     └─ src/
│        ├─ model.py             # GPT-2 트랜스포머 정의 (원본과 동일)
│        ├─ sample.py            # top-k / top-p(nucleus) 샘플링
│        ├─ encoder.py           # BPE 인코더 (recipe 특수토큰 추가)
│        ├─ load_dataset_pad.py  # ★ 필드 셔플 + 패딩 → 단일 시퀀스
│        ├─ load_dataset_condition.py
│        └─ conditional_gen_web.py  # ★ 조건부 생성 진입점
├─ utils/
│  ├─ metrics.py                 # ★ 재료 F1 (set precision/recall/f1)
│  ├─ tree.py                    # ★ 조리법→트리, zss 트리 편집거리(NTED)
│  ├─ evaluation.py              # 지표 오케스트레이션 (F1·NTED 집계)
│  └─ spacy_func.py              # ★ root noun 추출 + 재료 겹침 하이라이트
├─ analysis/
│  ├─ 01/02/03-*.ipynb           # Recipe1M 정제 + BPE 인코딩 전처리
│  ├─ 04-ingr-database.ipynb     # 재료 DB 구축
│  ├─ 05-highlight feature.ipynb # 하이라이트 feature
│  ├─ 09-model-performances.ipynb# BLEU/ROUGE 등 성능 집계
│  ├─ 11-find-most-similar-recipe.ipynb # 최근접 이웃(유사 레시피)
│  └─ multi-bleu.perl            # ★ Moses BLEU 스크립트
└─ data/
   ├─ vocab.bin                  # 어휘/특수토큰
   └─ recipe1M_example/test/{X,y}/*.txt  # ★ 소형 예시 입출력 (동봉)
```

## 2. 논문 ↔ 코드 매핑 표
| 논문 개념 | 코드 위치(파일:함수/클래스) | 설명 |
|---|---|---|
| 필드를 특수토큰으로 감싼 단일 시퀀스 | `data/recipe1M_example/**` 포맷 · `src/load_dataset_pad.py` | `<start-title>…<end-title> <start-directions>…<end-directions> <start-ingredients>…<end-ingredients>` 구조 |
| 양방향 생성(재료↔조리법) + 학습 증강 | `load_dataset_pad.py: shuffle()`, `shuff_ingredients()` | 필드 순서를 셔플( `[1279,9688]`=`<start-` 감지)해 어느 필드든 조건/타깃이 되게 학습. 재료 항목도 셔플 |
| 최대 512 토큰, 패딩 | `load_dataset_pad.py` (`max_token=512`, pad=`16791`) | 512 초과 시 랜덤 서브시퀀스, 미만 시 pad 토큰 채움 |
| GPT-2 124M/355M 파인튜닝 | `train_ppl_pickle.py`, `src/model.py` | 배포는 `117M`(=124M small) 체크포인트. lr 1e-4, batch 8 |
| top-k/top-p 자기회귀 생성 | `src/sample.py: sample_sequence()`, `conditional_gen_web.py` | temperature=1, top_p 권장 0.9, top_k=0 |
| **재료 F1** (재료 생성 정확도 0.76) | `utils/metrics.py: precision/recall/f1` | root-noun 재료 **집합** 교집합 기반 P/R/F1 |
| **NTED**(조리법 구조 유사도 0.52) | `utils/tree.py` + `evaluation.py: instr_tree()/norm_dist()` | 조리법→(동작=내부노드, 재료=리프) 트리, `zss.distance` 편집거리 / (노드수 합) 정규화 |
| 트리 노드 update 비용 | `utils/tree.py` (update_cost) | 두 노드 라벨 word2vec 임베딩 **코사인 거리** |
| **재료 겹침 하이라이트** + root noun | `utils/spacy_func.py: ingr()/instr()` | spaCy lemmatize + noun-chunk head로 어근명사 추출 후 조리법 토큰과 매칭 |
| **BLEU / Brevity Penalty** | `analysis/multi-bleu.perl` (+노트북 09) | Moses 표준 BLEU |
| ROUGE-L | `analysis/09-model-performances.ipynb` | 노트북에서 라이브러리로 집계(추정: rouge 패키지) |
| 최근접 이웃(유사 레시피) | `analysis/11-find-most-similar-recipe.ipynb` | 논문 배포판은 ElasticSearch 색인, 실험 노트북은 벡터 유사도 |

## 3. 데이터 흐름 추적
1. **전처리**(`analysis/01~03`): Recipe1M raw → 필드 정제 → 각 레시피를 특수토큰 시퀀스 문자열로 직렬화 → BPE 인코딩(`encoder.py`).
2. **학습**(`train_ppl_pickle.py`): 인코딩 시퀀스 로드 → `load_dataset_pad.Sampler`가 필드 순서·재료 순서 셔플 후 512로 패딩 → GPT-2 LM 손실(다음토큰 예측, perplexity)로 파인튜닝.
3. **조건부 생성**(`conditional_gen_web.py`): 입력 텍스트(예: `<start-title>…<end-title> <start-directions>…<end-directions> <start-ingredients>`)를 인코딩 → `sample_sequence`로 나머지 필드 자기회귀 생성 → 디코드 후 `<` 이후·개행 제거로 후처리.
4. **평가**(`utils/evaluation.py`): 생성물 vs 정답 → `spacy_func`로 재료 root noun 집합 추출 → `metrics.py` F1 · `tree.py` NTED · 외부 BLEU/ROUGE 집계.

## 4. 핵심 코드 발췌 + 해설
**(a) 특수토큰 포맷** — 동봉된 `data/recipe1M_example/test/X/1264i.txt` 실제 내용:
```
<start-title>tapenade <end-title> <start-directions>place the anchovies in a small shallow bowl … right before serving. <end-directions> <start-ingredients>
```
파일명 접미사 `i`=재료생성(ingredient) 태스크, `d`=조리법생성(directions) 태스크. `X/`는 입력(마지막에 생성할 필드의 open 태그만 열림), `y/`는 정답 필드. → **브라우저에서 그대로 재현 가능한 데이터 포맷**.

**(b) 필드 셔플/패딩**(`load_dataset_pad.py`, 요지):
```python
# 필드 시작 [1279,9688](=" <start-") 위치로 3필드 분해 후 순서 셔플
# 재료는 항목구분 토큰 [3] 기준 shuff_ingredients()로 재배열
diff = length - len(tokens)
if diff > 0:  tokens += [16791]*diff          # pad
elif diff < 0: start = rs.randint(0,abs(diff)); tokens = tokens[start:start+length]  # 랜덤 크롭
```
필드 순서를 매 스텝 섞는 것이 곧 **양방향 생성**을 하나의 LM으로 학습하는 트릭(어느 필드든 조건/타깃이 됨).

**(c) 재료 F1**(`metrics.py`, 집합 기반):
```python
precision = len(set(y_true) & set(y_pred)) / len(set(y_pred))
recall    = len(set(y_true) & set(y_pred)) / len(set(y_true))
f1        = 2*precision*recall/(precision+recall)
```
재료를 root-noun **집합**으로 보고 순서·중복 무시. → 브라우저 JS로 완전 동일 구현 가능.

**(d) NTED**(`tree.py`/`evaluation.py`): 조리법을 (동작 동사=내부노드, 재료 명사=리프)로 파싱 → `zss.distance(t1,t2, get_children, insert/remove/update_cost)`. insert/remove=이진(빈 라벨 0, 아니면 1), update=두 라벨 word2vec **코사인 거리**. `norm_dist`가 `(ori_nodes+gen_nodes)`로 정규화 → 평균이 NTED.

**(e) 생성 하이퍼파라미터**(`conditional_gen_web.py` 기본값): `model_name='117M'`, `temperature=1`, `top_k=0`, `top_p`(권장 0.9), `length=None`(기본 n_ctx/2), `nsamples=1`, `batch_size=1`. 후처리: `text.replace('\n','').split('<')[0]`.

## 5. 의존성 / 환경 요구사항 (실행에 필요한 것)
- **원저장소 완전 재현**: Python 3.6, TensorFlow 1.12(GPU), CUDA 9/10, spaCy(en 모델), `zss`, gensim(word2vec), Perl(multi-bleu). requirements: 루트 `requirements.txt` + `training/gpt-2/requirements.txt`.
- **학습 데이터**: Recipe1M 필터링본(≈904k 레시피) — 별도 취득 필요, 저장소엔 미포함(동봉은 `recipe1M_example` 5쌍뿐).
- **가중치**: 파인튜닝된 124M/117M 체크포인트는 저장소에 미포함(용량). 원본 GPT-2 117M은 `download_model.py`로 취득.
- **하드웨어**: 학습 단일 V100 ≈5일. 생성만이면 CPU로도 가능하나 파인튜닝 가중치가 있어야 의미 있는 출력.

## 6. 최소 재현(Minimal Repro) 가능 여부와 경로
- **브라우저에서 실제 동작 가능(=핵심 알고리즘 기여, stand-in 불필요)**:
  1. **특수토큰 레시피 포맷** 직렬화/파싱 + 필드/재료 셔플 + 패딩 (자료구조/포맷).
  2. **재료 F1**(집합 P/R/F1) — 정답 대비 실제 계산.
  3. **root-noun 추출 + 재료 겹침 하이라이트**(경량 규칙기반 lemmatize/head-noun; spaCy 대체) + **Jaccard 일관성**(생성 조리법 root-noun ∩ 입력 재료).
  4. **NTED 트리 구조 + Zhang-Shasha 편집거리**(zss 알고리즘 JS 이식) — 정규화까지.
  5. **BLEU / Brevity Penalty / ROUGE-L**(표준 n-gram, JS로 완전 구현).
  → 이들은 논문의 **평가 모듈** 자체이며, 실제 입력에 대해 진짜로 돌아가는 결정론적 알고리즘. **implement-loop의 '실제 동작 우선' 대상**.
- **브라우저 불가 → 라벨된 stand-in 필요**:
  1. **GPT-2 124M 파인튜닝 생성**(핵심 가중치·TF 필요) → 경량 stand-in(동봉 예시/템플릿/간이 생성기)로 **정확한 특수토큰 포맷의 레시피**를 만들어 그 위에서 위 실제 지표를 돌린다. "STAND-IN generator" 라벨 필수, 논문 보고치(F1 0.76 등)와 나란히 표시.
  2. **ElasticSearch 최근접 이웃 검색**(전체 Recipe1M 색인) → 동봉 예시 소집합에 대한 TF-IDF/코사인 유사도 stand-in.
  3. **NTED update 비용의 word2vec 코사인** → 문자열 유사도(예: 토큰 자카드/편집거리) stand-in로 대체(트리·zss 골격은 real).
