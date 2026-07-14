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
| GPT-2 neural forward pass / sampling (temp=1.0, top_p=0.9, top_k=0) | **REAL** — `transformers`, matches `conditional_gen_web.py` decoding |
| **Fine-tuned RecipeGPT weights (124M on Recipe1M)** | **STAND-IN** — authors did not release them; we use the ORIGINAL `gpt2` (markers fed as plain BPE text, since untrained special-token embeddings would be random). Text is generic; pipeline/format/decoding are faithful. Point `--model` at a fine-tuned checkpoint to fix. |
| Ingredient **F1** (set P/R/F1 over root nouns) — `utils/metrics.py` | **REAL** exact reimpl |
| **BLEU** + brevity penalty — Moses `multi-bleu.perl` | **REAL** exact reimpl |
| **ROUGE-L** (LCS F-measure) | **REAL** exact reimpl |
| **NTED**: instruction→tree + **Zhang-Shasha** edit distance + normalization — `utils/tree.py` | **REAL** algorithm (the `zss` library's algorithm, reimplemented) |
| **Jaccard** field-consistency + ingredient **highlight** — `utils/spacy_func.py` | **REAL** metric; root-noun extraction is a **rule-based STAND-IN for spaCy** |
| NTED node relabel cost (repo: word2vec cosine) | **STAND-IN** — token string similarity (tree + edit distance stay real) |

No hardcoded results, no fake logs. The `paper (124M)` column in output shows the
paper's **reported** numbers (F1 0.76 · BLEU 8.34 · BP 0.71 · ROUGE-L 0.36 ·
NTED 0.52 · Jaccard 0.53) for side-by-side reference only.

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

### (C) REAL recipes now — `--format recipenlg`

The paper's own RecipeGPT (Recipe1M) checkpoint was **never released**, so base
`gpt2` only emits generic text. To get **actual recipe output**, drive a public
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
for the unreleased Recipe1M weights.

---

## Files

| File | Role |
|---|---|
| `main.py` | CLI entry (`--mode gen-instructions｜gen-ingredients｜evaluate`) |
| `multifield.py` | Special-token multi-field format: serialize / build_prompt / parse |
| `generate.py` | Real GPT-2 inference (lazy-imports torch/transformers) |
| `metrics.py` | F1 · BLEU · ROUGE-L · NTED (Zhang-Shasha) · Jaccard · highlight |
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
