# REPRODUCE.md — what this app actually implements/runs ↔ paper evidence

Paper: *RecipeGPT: Generative Pre-training Based Cooking Recipe Generation and
Evaluation System* (Lee et al., WWW 2020 Demo, arXiv:2003.02498).
Official repo: https://github.com/LARC-CMU-SMU/RecipeGPT-exp

Legend: **REAL** = actually implemented & executed here · **STAND-IN** = labeled
substitute where the original asset is unavailable in this environment.

| # | Paper / repo element | Paper evidence | This app | Status |
|---|---|---|---|---|
| 1 | Multi-field single-sequence format with special tokens | §4 "fields wrapped in special delimiter tokens, single sequence"; repo `data/recipe1M_example/*.txt` | `multifield.serialize` / `parse`, markers `<start-title>…` verbatim | **REAL** |
| 2 | Bidirectional generation: title+ingredients→instructions AND title+instructions→ingredients | §4 "two modes"; repo `conditional_gen_web.py` | `multifield.build_prompt(mode)` + `main --mode gen-instructions/gen-ingredients` | **REAL** |
| 3 | GPT-2 autoregressive conditional generation | §4 backbone GPT-2 124M; repo `src/sample.py` `sample_sequence` | `generate.generate_field` → `transformers` GPT-2 real forward pass | **REAL (inference)** |
| 4 | Decoding hyperparameters temperature=1, top_k=0, top_p=0.9 | repo `conditional_gen_web.py` defaults | `generate.DEFAULTS`, `model.generate(do_sample, temperature, top_p)` | **REAL** |
| 5 | Fine-tuned RecipeGPT weights (124M, Recipe1M, lr 1e-4, batch 8, ~5 epochs) | §6 training setup | not released by authors → default `gpt2` base weights; `--model` accepts a real checkpoint | **STAND-IN (weights)** |
| 6 | Ingredient **F1** = 0.76 (set precision/recall/F1 over root nouns) | §6 Table; repo `utils/metrics.py` | `metrics.ingredient_f1` (exact set P/R/F1) + F1@k | **REAL** |
| 7 | **BLEU** = 8.34, **Brevity Penalty** = 0.71 | §6; repo `analysis/multi-bleu.perl` | `metrics.bleu` (Moses-style corpus BLEU + BP) | **REAL** |
| 8 | **ROUGE-L** = 0.36 | §6; notebook `09-model-performances` | `metrics.rouge_l` (LCS F-measure) | **REAL** |
| 9 | **NTED** = 0.52 (instruction tree + tree edit distance, normalized) | §6; repo `utils/tree.py`, `evaluation.py norm_dist` | `metrics.instr_tree` + `metrics.zhang_shasha` + `metrics.nted` | **REAL (algorithm)** |
| 10 | NTED node relabel cost = word2vec cosine | repo `utils/tree.py update_cost` | token-level string similarity | **STAND-IN (cost fn)** |
| 11 | **Jaccard** field consistency: gen 0.53 vs human 0.49 | §6 | `metrics.jaccard_consistency` | **REAL (metric)** |
| 12 | Root-noun extraction + ingredient-overlap **highlight** | §4 evaluation module; repo `utils/spacy_func.py` | `metrics.root_nouns` / `highlight_overlap` (rule-based) | **REAL metric, STAND-IN NLP** |
| 13 | Nearest-neighbor similar-recipe retrieval (ElasticSearch on Recipe1M) | §4 | not implemented (needs full Recipe1M index) | **OMITTED (labeled)** |
| 14 | Recipe1M training corpus (904k recipes) | §6 | not bundled; two built-in samples + repo-format example | **OMITTED (data)** |

## Verification status in THIS environment

- Items **1, 2, 6–12** were **executed here** (`python main.py --mode evaluate`,
  `python metrics.py`, `python multifield.py`) — real metric values printed, no
  heavy deps. See `../05_run.md` for captured logs.
- Items **3, 4** (real GPT-2 inference) were **executed here**: `pip install -r
  requirements.txt` (torch 2.4.1 + transformers 4.44.2) succeeded, `gpt2` weights
  downloaded, and both `--mode gen-instructions` and `--mode gen-ingredients`
  produced real, coherent (generic) neural output on CPU. Captured logs are in
  `../05_run.md`. No fake generation logs are included.
- Base-`gpt2` detail: the field markers are fed as **plain BPE text**, not added
  special tokens. Adding them as new special tokens gives them random embeddings,
  which makes the untrained model emit only marker tokens; a real fine-tuned
  checkpoint (`--model <dir>`) instead registers them as true special tokens.

## How to close the stand-in gaps (real reproduction path)

1. **Weights (item 5)**: fine-tune `gpt2` on Recipe1M in this exact multi-field
   format (repo `train_ppl_pickle.py`, lr 1e-4, batch 8, 512 tokens, ~5 epochs on
   a V100) → pass the checkpoint via `--model`. F1/BLEU/etc. should approach the
   paper's reported values.
2. **NLP (item 12)**: swap the rule-based `root_nouns` for spaCy noun-chunk heads.
3. **NTED cost (item 10)**: replace `_update_cost` with gensim word2vec cosine.
4. **Retrieval (item 13)**: index Recipe1M in ElasticSearch and add a retrieve mode.
