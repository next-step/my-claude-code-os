# LEARNINGS — recipegpt_2003.02498 (carries to next loop)

## Loop 1

### Environment facts (verified)
- This env has a REAL Python `C:\Users\kap\AppData\Local\Programs\Python\Python312\python.exe`
  (3.12.10, pip 25.0.1) — NOT just the Store stub. Claude CAN run Python here.
  Call it via PowerShell with the full path (bash `pip` hit a permission-denied shim).
- No ML packages preinstalled (torch/transformers/numpy/nltk absent).
- Strategy that worked: keep the **evaluation module dependency-free (pure stdlib)**
  so metrics run & verify instantly; put real GPT-2 behind a lazy import so
  `--mode evaluate` never needs torch.

### What was built (medium = terminal Python CLI, correct choice)
- `main.py` (modes: gen-instructions | gen-ingredients | evaluate) + `multifield.py`
  + `generate.py` (real GPT-2 via transformers) + `metrics.py` (F1@k, BLEU, BP,
  ROUGE-L, NTED via Zhang-Shasha, Jaccard, highlight). Pinned `requirements.txt`.
- Verified running here: multifield format, all metrics, `--mode evaluate` end-to-end.

### Gotchas fixed
- `parse()` collapsed ingredient newlines (via whitespace clean) → merged items;
  fixed by not cleaning the ingredient block before splitting.
- root-noun extraction: head-noun-per-line is right for ingredient LISTS but wrong
  for free-text instructions (grabbed only last word). Split into `ingredient_nouns`
  (head per line) vs `text_nouns` (all content tokens) with a dispatcher.

### Known stand-ins (improve next loop if score demands)
- Weights: base `gpt2`, not fine-tuned RecipeGPT (authors didn't release it).
- NLP: rule-based lemmatizer instead of spaCy.
- NTED relabel cost: string similarity instead of word2vec cosine.
- No ElasticSearch nearest-neighbor retrieval.

### Confirmed this loop
- Real GPT-2 generation EXECUTED here: installed torch==2.4.1 + transformers==4.44.2,
  downloaded gpt2 weights, ran both gen-instructions & gen-ingredients on CPU →
  coherent (generic) output. Real logs captured in 05_run.md.
- Critical gotcha: adding recipe markers as NEW special tokens to base gpt2 gives
  them random embeddings → model emits ONLY markers (garbage). Fix: for base gpt2
  feed markers as plain BPE text (no resize); only register special tokens for a
  real fine-tuned checkpoint. See generate.py BASE_MODELS / add_markers.
- Windows console is cp949 → must `sys.stdout.reconfigure(encoding='utf-8')` and
  avoid em-dashes in printed strings, else UnicodeEncodeError.

### Next-loop candidates (to raise score)
- Corpus-level evaluate over ALL bundled samples (not one pair) for stabler numbers.
- Optional spaCy path for root nouns; optional word2vec NTED cost.
- Add a `--retrieve` TF-IDF nearest-neighbor stand-in over bundled samples.

## 루프 1 — 총점 89/100 (PASS)
- 이번에 배운 것: Repo-verified verbatim against github.com/LARC-CMU-SMU/RecipeGPT-exp (master): field markers <start-title>/<end-title>/<start-directions>/<end-directions>/<start-ingredients> (data/recipe1M_example/test/X/1264i.txt), the set-based ingredient-F1 formula (utils/metrics.py), and split('<')[0] post-processing (conditional_gen_web.py) all match the app exactly. / The RecipeGPT fine-tuned checkpoint was never publicly released, so metric reproduction and on-topic generation are inherently capped for ANY faithful build; base gpt2 + STAND-IN label + real pipeline is the honest ceiling this app hits. / This environment DOES have torch 2.4.1+cpu and transformers 4.44.2 with gpt2 weights cached — real GPT-2 CPU inference runs here, so both evaluate and gen-ingredients were execution-verified (not merely runnable-by-structure): evaluate printed real F1@3=0.444/BLEU=22.721/NTED=0.344, gen produced novel neural text. / Attribution precision matters: conditional_gen_web.py's top_p default is 0.0, not the plausible-looking 0.9 the app claims as a repo default — decoding values labeled 'from repo defaults' must be checked against the actual source default.
- 다음 루프가 고칠 것(must_fix): Fix top_p attribution: REPRODUCE.md item 4 and generate.py DEFAULTS present top_p=0.9 as a 'conditional_gen_web.py default', but the repo's actual default is top_p=0.0. Relabel top_p=0.9 as a chosen nucleus value (not a repo default), or set it to 0.0 to match the source verbatim. / metric_fidelity is capped because the paper's test-set numbers cannot be regenerated without the unreleased fine-tuned weights. Add a fine-tune script pointer (train_ppl_pickle.py, lr 1e-4, batch 8, 512 tokens, ~5 epochs) so a produced checkpoint moves the 'paper' column from reference-only to reproduced. / Optional: add a real-NLP path (spaCy noun-chunk heads + gensim word2vec cosine for the NTED relabel cost) so the method stand-ins can be disabled for a higher-fidelity run.
