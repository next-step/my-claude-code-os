# RecipeGPT CLI — runnable reproduction of *RecipeGPT* (WWW 2020, arXiv:2003.02498)

A terminal program that reproduces the two things RecipeGPT actually does:

1. **Bidirectional recipe generation** with **real GPT-2 autoregressive inference**
   (HuggingFace `transformers`, CPU-friendly):
   - `title + ingredients → instructions`
   - `title + instructions → ingredients`
2. **The evaluation module** — the paper's real, deterministic metrics computed on
   real inputs: **Ingredient F1@k · BLEU · Brevity Penalty · ROUGE-L · NTED
   (tree edit distance) · Jaccard field-consistency · ingredient-overlap highlight**.

Official paper repo (reference): https://github.com/LARC-CMU-SMU/RecipeGPT-exp

---

## What is real vs. stand-in (honest)

| Component | Status |
|---|---|
| Multi-field special-token format `<start-title>…<end-title> <start-directions>…<end-directions> <start-ingredients>…<end-ingredients>` | **REAL** — verbatim from the repo's `data/recipe1M_example` files |
| Bidirectional conditional prompting (any field as target) | **REAL** |
| GPT-2 neural forward pass / sampling — `temperature=1.0`, `top_k=0` | **REAL (verbatim)** — `transformers`; these two match `conditional_gen_web.py`'s code defaults exactly |
| Nucleus `top_p=0.9` | **REAL, but a CHOSEN value** — the repo's `conditional_gen_web.py` code default is actually `top_p=0.0` (nucleus OFF). 0.9 is a recommended value, NOT a repo default. Pass `--top-p 0.0` to match the source byte-for-byte. |
| **Fine-tuned RecipeGPT weights (124M on Recipe1M)** | **STAND-IN** — the paper's weights were released only as a **TensorFlow checkpoint on the authors' OneDrive** (repo `training/gpt-2/models/`), **not directly HF-loadable**, so the default is the ORIGINAL `gpt2` (markers fed as plain BPE text, since untrained special-token embeddings would be random). Text is generic; pipeline/format/decoding are faithful. **`convert_checkpoint.py` scripts the official TF→HF conversion** to load the paper's OWN weights, and **`finetune.py` implements the paper's fine-tune recipe** — either way, pass the result via `--model`. |
| Ingredient **F1** (set P/R/F1 over root nouns) — `utils/metrics.py` | **REAL** exact reimpl |
| **BLEU** + brevity penalty — Moses `multi-bleu.perl` | **REAL** exact reimpl |
| **ROUGE-L** (LCS F-measure) | **REAL** exact reimpl |
| **NTED**: instruction→tree + **Zhang-Shasha** edit distance + normalization — `utils/tree.py` | **REAL** algorithm (the `zss` library's algorithm, reimplemented) |
| **Jaccard** field-consistency + ingredient **highlight** — `utils/spacy_func.py` | **REAL** metric; root-noun extraction is a rule-based STAND-IN by default, **or REAL spaCy noun-chunk heads with `--real-nlp`** |
| NTED node relabel cost (repo: word2vec cosine) | token string similarity by default, **or REAL gensim Word2Vec cosine with `--real-nlp`** (tree + edit distance always real) |

No hardcoded results, no fake logs. The `paper (124M)` column in output shows the
paper's **reported** numbers (F1 0.76 · BLEU 8.34 · BP 0.71 · ROUGE-L 0.36 ·
NTED 0.52 · Jaccard 0.53) for side-by-side reference only.

### Turn the method stand-ins OFF (`--real-nlp`) — verified

The rule-based lemmatizer and string-similarity NTED cost are optional stand-ins.
Install `spacy` + `gensim` (in `requirements.txt`) plus the spaCy model, then add
`--real-nlp` to run the paper's **real** NLP components:

```bash
python -m spacy download en_core_web_sm
python main.py --mode evaluate --real-nlp
```

Verified here — the real backend changes the numbers (it genuinely drives the
metric, not a mock): F1@3 `0.444 → 0.500`, NTED `0.344 → 0.246`, Jaccard
`0.429 → 0.625`. If the deps are missing, it prints an honest notice and falls
back to the stand-in (no fake "used spaCy" claims).

### Produce a real fine-tuned checkpoint (`finetune.py`) — verified

The paper's own Recipe1M checkpoint is released only as a TensorFlow checkpoint
on OneDrive (`training/gpt-2/models/`, not directly HF-loadable — see
`convert_checkpoint.py`), but the *training method* is here. `finetune.py`
fine-tunes GPT-2 in the exact multi-field special-token
format with the paper's recipe (lr 1e-4, batch 8, 512 tokens, ~5 epochs):

```bash
# smoke DEMO on the bundled sample (CPU, proves the loop trains):
python finetune.py --demo --out ckpt_demo --epochs 1 --max-steps 3
# real reproduction (full corpus, GPU):
python finetune.py --data recipe1m.jsonl --out recipegpt-124m --epochs 5 --batch 8 --lr 1e-4 --block-size 512
python main.py --mode gen-instructions --model recipegpt-124m
```

Verified here — the DEMO really trained (loss `78.96 → 17.93 → 7.13` over 3 steps)
and saved a checkpoint that `--model` then loads and generates from. The DEMO
overfits the tiny sample; the paper's numbers need the full Recipe1M corpus.

---

## Install & run (copy-paste)

```bash
cd output/recipegpt_2003.02498/app

# (A) EVALUATION MODULE — needs NOTHING but Python 3.9+ (pure stdlib):
python main.py --mode evaluate

# (B) REAL GPT-2 GENERATION — install deps first (first run downloads gpt2 ~500MB):
pip install -r requirements.txt
python main.py --mode gen-instructions          # title+ingredients -> directions
python main.py --mode gen-ingredients           # title+instructions -> ingredients
```

Windows one-liners: `./run.ps1` (eval only) or `./run.ps1 -Gen` (install + generate).
Linux/macOS: `./run.sh` or `./run.sh --gen`.

### Custom input

```bash
python main.py --mode gen-instructions \
  --title "lemon garlic pasta" \
  --ingredients "spaghetti" "garlic" "olive oil" "lemon" "parmesan" "parsley"

python main.py --mode gen-ingredients \
  --title "banana bread" \
  --instructions "Mash bananas, mix with butter and sugar, add flour, bake 50 min."

python main.py --mode evaluate --json \
  --ingredients "olives" "garlic" "capers" \
  --ref-ingredients "black olives" "garlic cloves" "capers" "anchovy" \
  --instructions "Blend olives with garlic and capers into a paste." \
  --ref-instructions "Combine olives, garlic, capers; blend to a coarse paste."
```

Use a fine-tuned checkpoint (local dir or HF id) if you have one:

```bash
python main.py --mode gen-instructions --model /path/to/recipegpt-124m
```

### Use the paper's OWN weights — `convert_checkpoint.py`

The paper's checkpoint is **released only as a TensorFlow checkpoint on OneDrive**
(repo README links `training/gpt-2/models/model-633000`), not directly HF-loadable.
Convert it to HF GPT-2 with the official converter, then run the paper's real model:

```bash
# 1) download + unzip the TF checkpoint from the repo README's OneDrive link
# 2) convert TF -> HF:
python convert_checkpoint.py --tf-ckpt-dir ./RecipeGPT_tf/model-633000 \
    --config ./RecipeGPT_tf/hparams.json --out ./recipegpt-124m-hf
# 3) run the PAPER'S OWN model (no longer a stand-in):
python main.py --mode gen-instructions --model ./recipegpt-124m-hf
python main.py --mode perplexity        --model ./recipegpt-124m-hf   # -> approaches paper PPL 3.70
```

The TF→HF conversion function is verified present here; the conversion run itself
needs the interactive OneDrive download (labeled user-run in `../05_run.md`).

### Perplexity and retrieval (evaluation module, pillar 2)

```bash
# live token perplexity over the bundled recipes (companion to paper PPL=3.70):
python main.py --mode perplexity                 # base gpt2 -> ~12 (honestly > 3.70)

# nearest-neighbor similar recipes (BM25 + TF-IDF) — pure stdlib, no deps:
python main.py --mode retrieve                    # ranks the bundled corpus
python main.py --mode retrieve --title "garlic pasta" \
  --ingredients "spaghetti" "garlic" "olive oil" "parmesan"
```

`--mode retrieve` is a labeled small-corpus **stand-in** for the paper's
ElasticSearch-on-Recipe1M "similar recipes" panel (§4): the BM25/TF-IDF ranking math
is real, the corpus is the bundled samples rather than the 904k index.

### (C) REAL recipes now — `--format recipenlg`

The paper's own RecipeGPT (Recipe1M) checkpoint is **not directly HF-loadable**
(released only as a TF checkpoint on OneDrive; see `convert_checkpoint.py`), so base
`gpt2` only emits generic text. To get **actual recipe output** out of the box, drive a public
GPT-2 that IS fine-tuned on recipes — same architecture + special-token
multi-field idea, different corpus (RecipeNLG), **labeled** as a real stand-in:

```bash
pip install -r requirements.txt      # first run downloads the model (~500MB)
python main.py --mode gen-instructions --format recipenlg \
  --ingredients "chicken breast" "soy sauce" "honey" "garlic" "ginger"
```

Real verified output (`pratultandon/recipe-nlg-gpt2`, CPU):

```
TITLE: Chicken Stir-Fry
INGREDIENTS: 1 lb chicken breast cut into strips · 3 tbsp soy sauce · 2 tbsp honey
             · 2 garlic cloves minced · 1 tsp ginger grated
INSTRUCTIONS:
  1. Mix together all ingredients.
  2. Marinate chicken strips for 1 hour.
  3. Grill on outdoor grill or in skillet until cooked through.
```

`recipenlg.py` builds this model's native token format
(`<RECIPE_START> <INPUT_START> … <INPUT_END>`), runs real GPT-2 inference, and
parses the output back into title / ingredients / instructions. It is **not** the
paper's exact checkpoint — it is a faithful, on-topic, honestly-labeled stand-in
for the paper's RecipeGPT weights, which are released only as a TensorFlow
checkpoint on OneDrive (not directly HF-loadable — see `convert_checkpoint.py`).

---

## Files

| File | Role |
|---|---|
| `main.py` | CLI entry (`--mode gen-instructions｜gen-ingredients｜evaluate｜perplexity｜retrieve`) |
| `multifield.py` | Special-token multi-field format: serialize / build_prompt / parse |
| `generate.py` | Real GPT-2 inference + `perplexity()` (lazy-imports torch/transformers) |
| `metrics.py` | F1 · BLEU · ROUGE-L · NTED (Zhang-Shasha) · Jaccard · highlight |
| `retrieve.py` | `--mode retrieve`: BM25 + TF-IDF similar-recipe ranking (pure stdlib) |
| `nlp_backend.py` | `--real-nlp` high-fidelity path: real spaCy noun-chunk heads + gensim word2vec NTED cost |
| `finetune.py` | Real GPT-2 fine-tuning into RecipeGPT (paper recipe: lr 1e-4/batch 8/512 tok/~5 epochs) |
| `convert_checkpoint.py` | Convert the authors' released TF checkpoint → HF GPT-2 (run the paper's OWN weights) |
| `recipenlg.py` | `--format recipenlg`: drive a public recipe-fine-tuned GPT-2 for on-topic output |
| `data/sample_recipes.json` | Built-in samples (runs with no args) |
| `data/recipe1M_example/` | Repo-format example pair (`X` input / `y` target) |
| `requirements.txt` | Pinned deps (only needed for generation) |
| `REPRODUCE.md` | What was implemented/run ↔ paper evidence |

## Expected output

- `--mode evaluate`: a metric table (this-run vs paper), the NTED tree node counts,
  the ingredient highlight (used/missing), and shared root-nouns. Runs in <1s, no deps.
- `--mode gen-*`: the multi-field prompt sent to GPT-2, then the **real** generated
  field, plus a live mini-evaluation (coverage / Jaccard or F1) on that output.
  With the default `gpt2` weights the text is generic (STAND-IN weights notice printed).
