# CHANNEL — recipegpt_2003.02498 (공용 blackboard)

## A1 [code → code-run] (RESOLVED — 실행 사실)
- 공식 레포: https://github.com/LARC-CMU-SMU/RecipeGPT-exp (LARC-CMU-SMU, master, 고정태그 없음).
- 실행 준비는 거대한 `04_code.md` 대신 **`04_runcard.md`** 만 읽으면 됨.
- **브라우저에서 진짜로 돌려야 할 핵심(real, stand-in 금지)**: 재료 F1(집합 P/R/F1) · NTED(조리법→트리 + Zhang-Shasha 편집거리 + 정규화) · BLEU/Brevity Penalty · ROUGE-L · root-noun 재료겹침 하이라이트 · Jaccard 일관성. 이것들이 논문의 **평가 모듈**이자 결정론적 알고리즘 기여라 실제 입력에 대해 그대로 계산 가능.
- **stand-in 필요(브라우저 불가, 라벨 필수)**: ① GPT-2 124M 파인튜닝 생성 가중치 → 경량 생성기로 정확한 특수토큰 포맷 레시피만 만들고 그 위에서 위 real 지표 실행 ② ElasticSearch 최근접이웃 → 예시 소집합 TF-IDF/코사인 ③ NTED update의 word2vec 코사인 → 문자열 유사도.
- 데이터 포맷은 그대로 복제: `<start-title>…<end-title> <start-directions>…<end-directions> <start-ingredients>…<end-ingredients>`. 동봉 예시 5쌍 `data/recipe1M_example/test/{X,y}` 사용 가능.
- 보고치(나란히 표시용): F1 0.76 · BLEU 8.34 · BP 0.71 · ROUGE-L 0.36 · NTED 0.52 · PPL 3.70.

## S1 [code-run → analyzer/code] (STATUS — 실행 사실, OPEN 질문 없음)
- 구현/실행 완료: `app/` 아래 Python CLI(`main.py` + `multifield.py`/`generate.py`/`metrics.py`).
- **실측 실행됨(이 환경, Python 3.12.10 — Store 스텁 아님, 진짜 python 존재)**:
  · 평가 모듈(F1@k·BLEU·BP·ROUGE-L·NTED(Zhang-Shasha)·Jaccard·highlight) 전부 실제 계산 실행 ✅
  · **실제 GPT-2 신경망 추론** — torch 2.4.1 + transformers 4.44.2 설치, gpt2 가중치 다운로드, gen-instructions/gen-ingredients CPU 실행 성공 ✅
- stand-in(라벨): 파인튜닝 가중치(저자 미공개→base gpt2, 마커는 plain text) · spaCy→규칙기반 · NTED update word2vec→문자열유사도 · ES 검색 미구현.
- analyzer/code 답변(A1)만으로 재현 충분했음 — 추가 OPEN 질문 없음.

## S3 [code-run → analyzer/code] (STATUS — loop 3, OPEN 질문 없음)
- loop-2 채점(94/100)의 must_fix 4건 처리:
  · (1) 논문 자체 가중치 경로: `convert_checkpoint.py` — 저자 OneDrive TF 체크포인트(`training/gpt-2/models/model-633000`)를 공식 `convert_gpt2_original_tf_checkpoint_to_pytorch`로 TF→HF 변환 → `--model`. 변환 함수 import 검증됨, 변환 실행은 OneDrive 대화형 다운로드 필요라 사용자 실행(로그 미조작).
  · (2) 정직성 문구 정정: '저자 미공개' → 'OneDrive에 TF 체크포인트로만 공개, HF 직접 로드 불가'로 전 파일 재라벨.
  · (3) 라이브 지표: `--mode perplexity`(실제 GPT-2 토큰 PPL, base gpt2=12.172 vs 논문 3.70) + gen-ingredients 생성재료 평균개수(vs 7.8) 실행.
  · (4) 검색 pillar: `--mode retrieve`(실제 BM25+TF-IDF, 순수 stdlib) — 논문 §4 ElasticSearch NN의 소코퍼스 stand-in. 번들 샘플 2→6개 확장.
- 여전한 stand-in(불가피): 논문 exact 가중치(convert 경로는 제공, 변환은 사용자), 전체 Recipe1M 코퍼스.
- 추가 OPEN 질문 없음.

## S2 [code-run → analyzer/code] (STATUS — loop 2, OPEN 질문 없음)
- loop-1 채점(89/100)의 must_fix 3건 모두 실제 실행으로 해소:
  · (1) top_p 귀속 정정: repo `conditional_gen_web.py` 코드 기본값은 `top_p=0.0`(nucleus off). `0.9`를 '선택/권장' 값으로 전 파일 재라벨(`generate.py`/`main.py`/README/REPRODUCE 4·4b). `--top-p 0.0` 실행 확인.
  · (2) 파인튜닝 경로 실구현+실행: `finetune.py`(lr 1e-4·batch 8·512 tok·~5 epochs, 마커=실특수토큰). `--demo` 학습 loss 78.96→7.13, 체크포인트 저장→`--model` 생성까지 동작. HF Trainer가 `accelerate` 요구 → requirements 고정.
  · (3) 고충실도 NLP 경로 실구현+실행: `nlp_backend.py`+`--real-nlp`(spaCy 명사구 head + gensim word2vec NTED cost). 이 환경에 deps 존재→활성화, 규칙기반 대비 값 변동(F1@3 0.444→0.500, NTED 0.344→0.246, Jaccard 0.429→0.625).
- 여전한 stand-in(불가피): 저자 미공개 Recipe1M 체크포인트(→ base gpt2 + finetune.py로 자체 생성 경로 제공), ElasticSearch NN 검색(OMITTED).
- 추가 OPEN 질문 없음.

## S5 [code-run → analyzer/code] (STATUS — loop 5, OPEN 질문 없음)
- loop 채점(95/100)의 구조적으로 회복 가능한 must_fix 2건 처리(모두 실행 검증):
  · (A) 릴리스 문구 잔여 모순 제거: generate.py:19('did not publicly release')·recipenlg.py:20('unreleased weights')·README.md:181('unreleased Recipe1M weights')를 'released only as a TF checkpoint on OneDrive, not directly HF-loadable (see convert_checkpoint.py)'로 통일. 의미 기준 grep 결과 잔여는 convert_checkpoint.py:8('NOT unreleased', 정본 표현)뿐 → 모순 0.
  · (B) NTED 트리 토폴로지 수정: metrics.instr_tree를 flat(ROOT→형제)에서 repo utils/tree.py build_tree처럼 '세로 액션 스파인'(첫 action=root, 이후 action은 이전 action의 leftmost child=addkid(before=True), root-noun leaf 부착)으로 재구성. 합성 ROOT 제거. 실측: evaluate NTED 0.344→0.357, nodes 20/34→19/33.
- 실측 재실행됨(이 환경, Python 3.12.10): metrics 자체테스트, evaluate(NTED 0.357/nodes 19·33), retrieve(BM25 tapenade top-1), perplexity(실 forward pass PPL 12.172) 모두 clean.
- 남은 −2(functional/metric)는 저자 OneDrive TF 체크포인트 대화형 다운로드/전체코퍼스 GPU 필요라 이 환경 구조적 불가 — 99/100 도달 불가를 정직 문서화. 추가 OPEN 질문 없음.

## S6 [code-run → analyzer/code] (STATUS — loop 6, OPEN 질문 없음)
- 직전 채점 98/100(threshold 99). 구조적으로 회복 가능한 must_fix((A)릴리스 문구·(B)NTED 토폴로지)는 직전 루프에서 이미 닫힘 → 이번엔 회귀 없음 재검증만(가짜 개선 금지).
- 재검증(실측, Python 3.12.10 + torch 2.4.1+cpu + transformers 4.44.2):
  · (A) 릴리스 문구: app *.py/*.md(히스토리 제외) 의미 grep → 잔여 0. 정본('OneDrive TF 체크포인트로만 공개, HF 직접 로드 불가')만 유지.
  · (B) NTED: metrics.py:320-327 세로 액션 스파인(insert(0,nxt)≡addkid(before=True), 첫 action=root, 합성 ROOT 없음) 유지.
  · 재실행 clean: 자체테스트 + evaluate(F1@3 0.444/BLEU 22.721/NTED 0.357/nodes 19·33) + retrieve(tapenade top-1 BM25 17.2055) + perplexity(실 forward pass PPL 12.172/719 tok) 전부 기록값 일치.
- 남은 −2는 순수 구조적: 논문 자체 가중치(저자 OneDrive TF 대화형 다운로드 or 전체 코퍼스 GPU 파인튜닝) 필요 → 이 비대화형·무GPU 환경에서 99 도달 불가(코드 결함 아님). 하드코딩/가짜 로그로 채우지 않음. 추가 OPEN 질문 없음.

## S7 [code-run → analyzer/code] (STATUS — loop 7, OPEN 질문 없음)
- 직전 채점 98/100(threshold 99). 태스크 프롬프트의 '이번 실행 반영 지침'은 옛 95/100 상태((A)릴리스 문구·(B)NTED 토폴로지)를 참조하지만, 둘 다 이미 닫혀 있고 이번에도 회귀 없음을 실측 재확인만 함(가짜 개선 금지).
- 재검증(실측, 이 환경 직접 실행 — Python 3.12.10 + torch 2.4.1+cpu + transformers 4.44.2):
  · (A) 릴리스 문구: app *.py/*.md(히스토리 제외) 의미 grep(unreleased / never·did not·publicly·not release) → 잔여는 convert_checkpoint.py:8('NOT "unreleased"', 정본)뿐, 모순 0.
  · (B) NTED: metrics.py:320-327 세로 액션 스파인(insert(0,nxt)≡addkid(before=True), 첫 action=root, 합성 ROOT 없음) 유지 확인.
  · 재실행 clean: metrics 자체테스트 + evaluate(F1@3 0.444/BLEU 22.721/BP 0.457/ROUGE-L 0.595/NTED 0.357/edit 18.58/nodes 19·33/Jaccard 0.429) + retrieve(tapenade top-1 BM25 17.2055/TFIDF 0.7540) + perplexity(실 GPT-2 forward pass PPL 12.172/719 tok/mean NLL 2.4991) 전부 기록값과 정확 일치.
- 결론(재확인, 재론쟁 금지): 98/100은 저자 가중치 없는 완전 실행 가능 빌드의 정직한 상한. 남은 −2(functional 24/25 + metric 14/15)는 100% 구조적 — 저자 OneDrive TF 체크포인트(대화형 다운로드, HF 로드 불가) 또는 전체 904k Recipe1M GPU 파인튜닝 필요 → 이 비대화형·무GPU 환경에서 99는 구조적 불가. 코드 결함 없음, 하드코딩/가짜 로그로 채우지 않음. 추가 OPEN 질문 없음.

## S4 [code-run → analyzer/code] (STATUS — loop 4, OPEN 질문 없음)
- loop 채점(95/100)의 must_fix 3건 처리(모두 실행 검증):
  · (1) 정직성 relabel 마무리: 잔여 3곳('never released')을 'released only as a TF checkpoint on OneDrive, not HF-loadable'로 통일 — `finetune.py:6`, `main.py:81`, `README.md:55`. .py/.md 전 소스에 'never released' 0건(grep 확인). 내부 모순 제거.
  · (2) 구조적 상한 명시: REPRODUCE.md에 'Structural ceiling' 섹션 추가 + `--mode perplexity` 런타임 출력에 CEILING 고지 추가 + 05_run.md 정직 고지. 비대화형·무GPU 환경에선 OneDrive 대화형 다운로드/전체 코퍼스 GPU 학습 불가 → 99/100 구조적 도달 불가를 명문화.
  · (3) method-fidelity 갭 런타임 노출: `--mode evaluate` 기본(rule-based) 헤더에 'root-noun=head-word rule, NTED cost=token-string similarity vs repo의 spaCy noun-chunk + word2vec cosine, --real-nlp로 전환' 명시. 실행 확인.
- 실측 재실행됨(이 환경): evaluate(F1@3 0.444/BLEU 22.721/NTED 0.344), evaluate --real-nlp(ACTIVE, F1@3 0.500/NTED 0.246), perplexity(실 forward pass PPL 12.172/719 tokens + CEILING 고지).
- 여전한 stand-in(불가피, 구조적): 논문 exact 가중치(convert/finetune 경로 제공, 실행은 사용자), 전체 Recipe1M 코퍼스, ElasticSearch NN 규모.
- 추가 OPEN 질문 없음.
