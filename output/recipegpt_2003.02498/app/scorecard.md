# Scorecard — RecipeGPT (arXiv:2003.02498)

- **Slug**: `recipegpt_2003.02498`
- **Iteration**: 3
- **Medium**: terminal (Python CLI)
- **Total**: **98 / 100**
- **Threshold**: 99
- **Verdict**: **FAIL** (2-point gap is structural — see below)

All six axes were re-verified LIVE this session: the app was executed end-to-end
(Python 3.12.10, torch 2.4.1+cpu, transformers 4.44.2) and the official repo
(github.com/LARC-CMU-SMU/RecipeGPT-exp, `master`) was re-read via WebFetch.

## Axis breakdown

| Axis | Score | Notes |
|---|---|---|
| Functional reproduction | **24 / 25** | 5 modes run live end-to-end; real recipe generation; -1 structural (paper's exact weights never run) |
| Repo fidelity | **20 / 20** | Every code-level value verified verbatim against live repo source this session |
| Method fidelity | **15 / 15** | Bidirectional two-mode + Zhang-Shasha NTED over repo-matching vertical action spine |
| Metric fidelity | **14 / 15** | All paper values shown side-by-side; PPL computed live; -1 (cannot regenerate exact test-set numbers) |
| Runnability | **15 / 15** | Pinned deps, clear entry point, pure-stdlib defaults, copy-paste commands ran clean |
| Honesty | **10 / 10** | Meticulous REAL/STAND-IN/OMITTED labeling; no fake logs; consistent across all files |

## Live execution log (this session)

| Command | Result |
|---|---|
| `python main.py --mode evaluate` | pure stdlib, no args → F1@3=0.444, BLEU=22.721, BP=0.457, ROUGE-L=0.595, NTED=0.357 (edit 18.58, nodes 19/33), Jaccard=0.429, highlight used=6/0 — input-derived |
| `python main.py --mode retrieve` | real BM25 (k1=1.5,b=0.75) + TF-IDF → tapenade top-1 (BM25 17.2055 / TFIDF 0.7540), then hummus/marinara |
| `python main.py --mode perplexity` | real GPT-2 CPU forward pass, 719 tokens → PPL=12.172 (mean NLL 2.4991), side-by-side with paper 3.70, honestly flagged as base-weights |
| `python main.py --mode gen-instructions --format recipenlg --ingredients spaghetti garlic 'olive oil' parmesan` | real recipe-fine-tuned GPT-2 → "Spaghetti With Garlic" + 4 ingredients + 6 numbered steps, then live evaluation (coverage 0.75, Jaccard 0.136) |

No hardcoded results, no fabricated logs. The `paper (124M)` column is a labeled
reference; every "this run" value is computed live.

## Repo-fidelity checks (verified verbatim via WebFetch this session)

| Claim | Repo source | File | Match |
|---|---|---|---|
| Ingredient F1 set-based P=inter/len(pred), R=inter/len(true), F1=2PR/(P+R) | `len(set(y_true)&set(y_pred))/len(set(y_pred))` … `2*precision*recall/(precision+recall)` | `utils/metrics.py` | yes |
| F1@k truncation | NOT in repo — app convenience, labeled "paper k=3" | `utils/metrics.py` | no (honestly labeled) |
| Decode defaults 117M / temp 1 / top_k 0 / top_p 0.0 | `interact_model` defaults exactly | `training/gpt-2/src/conditional_gen_web.py` | yes |
| top_p=0.9 labeled CHOSEN (repo default 0.0) | signature default `top_p=0.0`; `--top-p 0.0` matches | `conditional_gen_web.py` | yes |
| Post-process `text.replace('\n','').split('<')[0]` | verbatim | `conditional_gen_web.py` | yes |
| NTED norm = tree_dist/(ori_nodes+gen_nodes), nodes = sum(len(ingredient)+1) | `norm_dist` verbatim | `utils/evaluation.py` | yes |
| Relabel cost = 1 − word2vec cosine | `update_cost=lambda a,b: wordvec_dist(...)` | `utils/tree.py` | yes |
| Vertical action spine, `addkid(before=True)`, first action = root | `build_tree` verbatim | `utils/tree.py` | yes |
| Field markers verbatim | bundled `data/recipe1M_example` matches schema | `data/recipe1M_example/test/X/tapenade_i.txt` | yes |
| Paper checkpoint released as TF-only on OneDrive, not HF-loadable | README OneDrive link; consistent across all app docs | `generate.py:19` | yes |

## Why not 99? (structural ceiling — not a fixable defect)

Two axes are each capped −1 for the **same** reason: the app never runs the
authors' **exact** Recipe1M fine-tuned weights. Those weights are released **only
as a TensorFlow checkpoint on the authors' OneDrive** (`training/gpt-2/models/model-633000`),
which is **not directly HF-loadable**. Reaching the paper's exact numbers
(F1 0.76 / PPL 3.70) needs either:

1. an **interactive** OneDrive download (browser-only, cannot be scripted) + TF→HF
   conversion (`convert_checkpoint.py`), or
2. a full-corpus (904k Recipe1M) **GPU** fine-tune (`finetune.py --data`).

Both are impossible in this non-interactive, no-GPU environment. The
`--format recipenlg` path already maximizes achievable functional evidence
(real coherent recipe output via a real recipe-fine-tuned GPT-2, honestly labeled
as a different-corpus checkpoint). **98 is the honest ceiling here; no code change
reaches 99.** Three iterations have converged on 98 — recommend stopping the loop.

## must_fix

- **STRUCTURAL CEILING (only remaining gap, 2 pts) — not a code defect.** Requires
  the authors' OneDrive TF checkpoint (interactive download) + TF→HF convert, or a
  full-corpus GPU fine-tune. Impossible in this environment; the loop should stop.
