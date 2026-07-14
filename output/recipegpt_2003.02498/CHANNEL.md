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
