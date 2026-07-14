# Scorecard — RecipeGPT (arXiv:2003.02498)

- **Slug**: `recipegpt_2003.02498`  ·  **Iteration**: 1  ·  **Medium**: terminal
- **Total**: **89 / 100**  ·  **Threshold**: 85  ·  **Verdict**: **PASS**
- **Scored against**: `01_analysis.md` (canonical) + real GPT-2 execution in this env + official repo source (github.com/LARC-CMU-SMU/RecipeGPT-exp) fetched via WebFetch.

## Axis breakdown

| Axis | Score | Max |
|---|---|---|
| 1. Functional reproduction (실제 실행 구현) | 23 | 25 |
| 2. Repo fidelity (실제 코드 대조) | 17 | 20 |
| 3. Method fidelity | 13 | 15 |
| 4. Metric fidelity | 12 | 15 |
| 5. Runnability | 15 | 15 |
| 6. Honesty | 9 | 10 |
| **Total** | **89** | **100** |

## 1. Functional reproduction — 23/25 (executed here)

Both capabilities were **actually run** in this environment (Python 3.12.10; torch 2.4.1+cpu; transformers 4.44.2; gpt2 weights cached):

- `python main.py --mode evaluate` → pure-stdlib, printed **real computed** metrics on real inputs: F1@3 = 0.444 (P 0.667 / R 0.333), BLEU = 22.721, BP = 0.457, ROUGE-L = 0.595, NTED = 0.344 (edit_distance 18.58, nodes_a 20, nodes_b 34), Jaccard = 0.429, highlight used 6 / missing 0. Input-derived, not hardcoded.
- `python main.py --mode gen-ingredients` → **real GPT-2 CPU forward pass**, emitted novel text (`Add 1 cup soy sauce, 1/3 cup corn syrup, 1 teaspoon baking soda...`) conditioned on the verbatim multi-field prompt, then ran the live F1 mini-eval. No fake logs.

Core paper method is real code: bidirectional multi-field conditional generation + Zhang-Shasha tree-edit-distance NTED. **-2**: the flagship RecipeGPT fine-tuned weights are unavailable (never released), so generation runs on base `gpt2` (labeled STAND-IN) and reads generic.

## 2. Repo fidelity — 17/20 (verified against real source)

| Claim | Repo source | File | Match |
|---|---|---|---|
| Field markers `<start-title>…<start-ingredients>` | verbatim in example file | `data/recipe1M_example/test/X/1264i.txt` | ✅ |
| Ingredient F1 = set P/R, `2PR/(P+R)` | `len(set(y_true)&set(y_pred))/len(set(y_pred))`… | `utils/metrics.py` | ✅ |
| Post-process `split('<')[0]` | `text.replace('\n','').split('<')[0]` | `conditional_gen_web.py` | ✅ |
| temperature=1, top_k=0 | temperature=1, top_k=0 | `conditional_gen_web.py` | ✅ |
| top_p=0.9 "from repo defaults" | **repo default is top_p=0.0** | `conditional_gen_web.py` | ❌ |
| Repo tree (utils/, training/gpt-2/src, analysis nb) | matches | repo tree | ✅ |
| BLEU not in utils/metrics.py (→ multi-bleu.perl) | confirmed absent | `utils/metrics.py` | ✅ |

**-3** for the top_p mislabel (0.9 presented as a repo default; the actual default is 0.0).

## 3. Method fidelity — 13/15

Two-mode bidirectional conditional generation with correct field ordering (matches repo i-/d- example files). NTED = normalized Zhang-Shasha ordered-tree edit distance. **-2**: NTED relabel cost (string-sim STAND-IN for word2vec cosine) and rule-based root-noun extraction (STAND-IN for spaCy) — labeled, but shift metric magnitudes.

## 4. Metric fidelity — 12/15

All paper values present and shown side-by-side with this-run values (F1 0.76 · avg-ingr 7.8 · BLEU 8.34 · BP 0.71 · ROUGE-L 0.36 · NTED 0.52 · PPL 3.70 · Jaccard 0.53/0.49), honestly flagged as full-test-set reference. **-3**: without the unreleased fine-tuned weights the paper numbers can't be *regenerated* — they are display/reference only (honest cap, not fabrication).

## 5. Runnability — 15/15

Pinned `requirements.txt` (torch==2.4.1, transformers==4.44.2). Clear `main.py` entry. `run.sh` + `run.ps1` work, heavy deps gated behind `--gen`/`-Gen`. Evaluate mode needs zero third-party deps. Runs with no args from `data/sample_recipes.json`. README copy-paste verified by actually running.

## 6. Honesty — 9/10

Clear REAL / STAND-IN / OMITTED tables (REPRODUCE.md, README), runtime STAND-IN WEIGHTS notice, paper numbers labeled "reported", omissions (ElasticSearch retrieval, full Recipe1M) declared. No fake logs. **-1**: the top_p mislabel.

## must_fix (next iteration)

1. **Fix top_p attribution** — REPRODUCE.md item 4 / `generate.py DEFAULTS` call top_p=0.9 a "conditional_gen_web.py default", but the repo default is **0.0**. Relabel as a chosen nucleus value or set to 0.0 to match the source.
2. **Unlock metric reproduction** — add a fine-tune pointer (`train_ppl_pickle.py`, lr 1e-4, batch 8, 512 tok, ~5 epochs) so a produced checkpoint moves the "paper" column from reference-only to reproduced.
3. *(Optional)* add a real-NLP path (spaCy noun heads + gensim word2vec NTED cost) to turn off method stand-ins for a high-fidelity run.

## learned (hand-off)

- Repo-verified verbatim: field markers, set-based ingredient-F1, and `split('<')[0]` post-processing all match the app — strong repo fidelity.
- RecipeGPT fine-tuned weights were never released → metric reproduction and on-topic generation are inherently capped for any faithful build; base-gpt2 + STAND-IN label + real pipeline is the honest ceiling.
- This env HAS torch 2.4.1+cpu / transformers 4.44.2 + cached gpt2 → real CPU inference runs here; generation is execution-verified, not just structurally runnable.
- Verify decoding values against the actual source default: `conditional_gen_web.py` top_p default is 0.0, not the plausible-looking 0.9.
