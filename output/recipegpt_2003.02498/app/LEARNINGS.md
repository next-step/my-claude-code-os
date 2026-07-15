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

## Loop 2 — cleared all 3 must_fix from the 89/100 scorecard (EXECUTED, not just structural)

### (1) top_p attribution — FIXED
- `top_p=0.9` was mislabeled as a `conditional_gen_web.py` repo default. The repo's
  literal code default is `top_p=0.0` (nucleus off). Relabeled as a *chosen/recommended*
  value across: `generate.py` docstring + `DEFAULTS` comment + `REPO_CODE_DEFAULT_TOP_P=0.0`,
  `main.py --top-p` help, README table (split into two rows), REPRODUCE.md items 4/4b.
  Verified `--top-p 0.0` runs (repo-verbatim path).

### (2) Fine-tune path — now REAL and EXECUTED (unlocks metric reproduction)
- `finetune.py` really fine-tunes GPT-2 in the multi-field special-token format with
  the paper recipe (lr 1e-4, batch 8, 512 tok, ~5 epochs). Verified: `--demo --max-steps 3`
  trained (loss 78.96→17.93→7.13, train_loss 34.68), saved a checkpoint, and
  `main.py --model ckpt_demo` generated from it (is_finetuned path).
- GOTCHA: HF `Trainer` needs `accelerate` (device setup) — it was NOT installed and
  finetune crashed at `TrainingArguments`. Fix: `pip install accelerate` and pin it in
  requirements.txt (`accelerate>=0.26,<1.1`). Now finetune runs end-to-end.

### (3) Real-NLP path — now REAL and EXECUTED (removes method stand-ins)
- `nlp_backend.py` + `main.py --real-nlp`: real spaCy noun-chunk heads + gensim
  Word2Vec cosine for the NTED relabel cost. This env HAS spacy+gensim+en_core_web_sm,
  so it ACTIVATED and produced DIFFERENT real values vs the rule-based stand-in:
  F1@3 0.444→0.500, NTED 0.344→0.246, Jaccard 0.429→0.625. Proves the backend truly
  drives the metric. Honest fallback with notice if deps absent (no fake spaCy claims).

### Loop-2 environment facts
- This env's real Python (3.12.10) ALSO has spacy, gensim, en_core_web_sm, datasets,
  and (after this loop) accelerate installed — so BOTH the high-fidelity NLP path and
  the fine-tune loop are execution-verified here, not merely runnable-by-structure.
- Still capped-by-design: the authors' *specific* Recipe1M checkpoint is unreleased, so
  the paper's exact test-set numbers still need a full-corpus fine-tune (script provided).
  ElasticSearch NN retrieval still OMITTED.

## Loop 3 — cleared all 4 must_fix from the 94/100 scorecard (EXECUTED where possible)

### (1) PATH-TO-99: run the authors' OWN weights — convert_checkpoint.py (import-verified)
- `convert_checkpoint.py` scripts the official TF->HF conversion via
  `transformers.models.gpt2.convert_gpt2_original_tf_checkpoint_to_pytorch.
  convert_gpt2_checkpoint_to_pytorch` (import-verified present in transformers 4.44.2).
  Maps nshepperd `hparams.json` -> `GPT2Config`, runs the converter, saves an HF ckpt
  WITH the recipe markers registered as real special tokens (matches generate.py
  is_finetuned path). Then `main.py --model ./recipegpt-124m-hf`.
- NOT executed end-to-end: the authors' TF ckpt (`training/gpt-2/models/model-633000`)
  lives on OneDrive and needs an INTERACTIVE browser download — labeled user-run,
  no converted-model logs fabricated. Argument/error paths run clean here.

### (2) Honesty precision — FIXED
- Relabeled 'authors never released the checkpoint' -> 'released only as a TensorFlow
  checkpoint on OneDrive, not directly HF-loadable' across main.py docstring +
  recipenlg print, recipenlg.py header, README table + recipenlg section, REPRODUCE
  item 5. The repo README DOES link a model download; the barrier is TF->HF format.

### (3) Live perplexity + avg-ingredient count — REAL and EXECUTED
- `generate.perplexity()` + `--mode perplexity`: real GPT-2 token cross-entropy PPL
  over the 6 bundled recipes (multi-field serialized). Executed here: base gpt2
  PPL=12.172, mean NLL 2.4991, 719 tokens — printed vs paper 3.70 and honestly flagged
  far-higher (base weights). Genuinely from logits, not hardcoded.
- `gen-ingredients` now prints avg generated-ingredient count (metrics.
  split_ingredient_items) vs paper 7.8.

### (4) Retrieval pillar — REAL ranking, STAND-IN corpus, EXECUTED
- `retrieve.py` + `--mode retrieve`: real Okapi BM25 (k1=1.5, b=0.75) + TF-IDF cosine
  (ElasticSearch's scorer family), PURE STDLIB (no deps). Labeled small-corpus stand-in
  for the paper's ES-on-Recipe1M §4 panel. Executed: tapenade query -> top-1 tapenade
  (BM25 17.21); garlic-pasta query -> top-1 marinara (sensible). Expanded bundled
  samples 2 -> 6 recipes so ranking is non-trivial.

### Loop-3 environment facts
- transformers 4.44.2 HAS convert_gpt2_original_tf_checkpoint_to_pytorch (import OK).
- Perplexity forward pass runs on CPU in a few seconds for the 6-recipe corpus.
- Still capped-by-design: paper's exact PPL 3.70 / F1 0.76 need the real fine-tuned
  weights (convert path provided but conversion is user-run) or full-corpus finetune.

## Loop 4 — cleared all 3 must_fix from the 95/100 scorecard (EXECUTED)

### (1) Honesty relabel FINISHED (the recurring miss) — verified 0 residual
- The prior loop fixed 'never released' in primary docs but left 3 secondary spots
  (main.py:81, README.md:55, finetune.py:6) contradicting the corrected text. This
  loop swept ALL of them to 'released only as a TensorFlow checkpoint on OneDrive,
  not directly HF-loadable (see convert_checkpoint.py)'. `grep 'never released'` over
  *.py and README.md now returns ZERO matches. LESSON CONFIRMED: after a relabel,
  grep the WHOLE app (all .py + .md), not just the flagged files — comments and
  section bodies hide stale copies.

### (2) Structural ceiling now DOCUMENTED at 3 layers (was only implied)
- Added a 'Structural ceiling' section to REPRODUCE.md stating plainly that in a
  non-interactive/no-GPU env, functional_reproduction + metric_fidelity cannot be
  maxed (OneDrive download is browser-only; full-corpus fine-tune needs GPU), so
  99/100 is unreachable BY CONSTRUCTION — every other axis is already near max.
- Surfaced the same CEILING notice in the LIVE `--mode perplexity` output (printed
  under the STAND-IN WEIGHTS block) and in 05_run.md. Verified printed: PPL 12.172.

### (3) method-fidelity gap now VISIBLE at runtime (was REPRODUCE.md-only)
- The default `--mode evaluate` header now names the deviation explicitly: root-noun
  = head-word rule, NTED relabel cost = token-string similarity, vs the repo's spaCy
  noun-chunk heads + gensim word2vec cosine, with a `--real-nlp` pointer. Verified in
  both the rule-based header and the `[real-nlp] ACTIVE` path.

### Loop-4 environment facts
- Re-verified live here (Python 3.12.10, torch 2.4.1+cpu, transformers 4.44.2, spaCy
  + gensim + en_core_web_sm present): evaluate (rule-based + --real-nlp) and perplexity
  (real forward pass) all run clean. The structural cap is unchanged: 95 is the honest
  ceiling for a fully-runnable, no-authors'-weights build of this paper.

## Loop 5 — cleared both structurally-recoverable must_fix from the 95/100 scorecard (EXECUTED)

### (A) Release-wording residual — FIXED (swept by MEANING, verified 0 residual)
- Fixed the 3 spots the prior sweep missed because they used different verbs:
  generate.py:19 ("did not publicly release"), recipenlg.py:20 ("unreleased
  weights"), README.md:181 ("unreleased Recipe1M weights"). All now read
  "released only as a TensorFlow checkpoint on OneDrive, not directly HF-loadable
  (see convert_checkpoint.py)". Grep by MEANING (did not/publicly/never release,
  unreleased, not released) over app/*.py + *.md now returns only
  convert_checkpoint.py:8 — which asserts they are NOT "unreleased" (the canonical
  framing), so zero contradiction remains. LESSON REINFORCED: grep the concept,
  not the literal string.

### (B) NTED tree topology — vertical action spine (was flat siblings-under-ROOT)
- metrics.instr_tree now builds a VERTICAL action spine matching repo
  utils/tree.py build_tree: the first action is the root, each subsequent action
  is inserted as the LEFTMOST child of the previous (repo addkid(before=True)),
  with that action's root-noun leaves attached. The synthetic ROOT node is gone.
- EXECUTED here (Python 3.12.10): evaluate NTED 0.344->0.357, nodes 20/34->19/33
  (one fewer node per tree = the dropped synthetic ROOT), proving the topology
  change is live and shifts the edit distance. metrics.py self-test, evaluate,
  retrieve, perplexity (real forward pass PPL 12.172) all re-ran clean.
- Updated REPRODUCE.md row 9 (now "REAL (algorithm + repo tree topology)") and
  the 05_run.md (A) log to the actual re-run values.

### Loop-5 residual ceiling (unchanged, structural)
- The remaining -2 (functional_reproduction/metric_fidelity) needs the authors'
  OneDrive TF checkpoint (interactive browser download) or full-corpus GPU
  fine-tune — impossible in this non-interactive/no-GPU env. 99 is unreachable BY
  CONSTRUCTION; documented, not faked. Both recoverable must_fix are now closed.

## Loop 6 — 총점 98/100 (FAIL, threshold 99) — RE-VERIFIED, no fixable defect remains

### Situation
- The task prompt's "이번 실행 반영 지침" references an OLD 95/100 state and lists (A)
  release-wording + (B) NTED-topology as must_fix. Both were ALREADY closed in the
  loop that produced the current 98/100 scorecard.json. This loop CONFIRMED they are
  intact (not regressed) and re-ran the executable checks — no fabricated improvement.

### Verified intact this loop (live, Python 3.12.10 + torch 2.4.1+cpu + transformers 4.44.2)
- (A) Release wording: grep-by-MEANING over app *.py/*.md (excluding LEARNINGS/scorecard
  history) for did-not/publicly/never/not-release + unreleased -> ZERO residual. Only the
  canonical 'released only as a TensorFlow checkpoint on OneDrive, not directly HF-loadable'
  framing remains. No internal contradiction.
- (B) NTED topology: metrics.py:320-327 still builds the VERTICAL action spine
  (cur.children.insert(0,nxt) == repo addkid(before=True), first action = root, no
  synthetic ROOT). Matches repo utils/tree.py build_tree.
- Re-ran clean, values match the recorded scorecard exactly: metrics.py self-test;
  --mode evaluate (F1@3 0.444 / BLEU 22.721 / ROUGE-L 0.595 / NTED 0.357, edit 18.58,
  nodes 19/33 / Jaccard 0.429); --mode retrieve (tapenade top-1 BM25 17.2055 / TFIDF
  0.7540); --mode perplexity (REAL GPT-2 CPU forward pass PPL 12.172, 719 tokens,
  mean NLL 2.4991). No regression.

### Conclusion (carry forward — do not re-litigate)
- 98/100 is the honest ceiling for a fully-runnable, no-authors'-weights build. The
  remaining -2 (functional_reproduction 24/25 + metric_fidelity 14/15) is 100% STRUCTURAL:
  the paper's exact numbers need the authors' OneDrive TF checkpoint (interactive browser
  download, not HF-loadable) or a full 904k-Recipe1M GPU fine-tune — both impossible in
  this non-interactive/no-GPU env. There is NO code defect to fix; a score of 99 is
  unreachable here BY CONSTRUCTION. Future loops should NOT attempt code edits for these
  2 points, and must NOT hardcode/fake the paper's numbers to close the gap.
- Noise note: app/korean/ is an unrelated from-scratch Korean char-LSTM mini-project
  (main.py doesn't import it); left untouched, isolated in its own subdir.

## Loop 7 — 총점 98/100 (FAIL, threshold 99) — RE-VERIFIED live again, no fixable defect

### Situation (same as loop 6 — the prompt's directive is stale)
- The task prompt again lists (A) release-wording + (B) NTED-topology as must_fix from an
  OLD 95/100 state. Both were closed loops ago and the current scorecard.json is 98/100
  whose sole must_fix is the STRUCTURAL ceiling. This loop RE-RAN the executable checks
  live (real Python here) to confirm no regression — no fabricated improvement, no code
  edit made to chase the last 2 points (they are environmental, not a defect).

### Verified intact this loop (live, Python 3.12.10 + torch 2.4.1+cpu + transformers 4.44.2)
- (A) Release wording: meaning-grep over app *.py/*.md (excluding LEARNINGS/scorecard
  history) for unreleased / never·did-not·publicly·not-release -> only convert_checkpoint.py:8
  ("NOT 'unreleased'", the canonical framing). Zero contradiction.
- (B) NTED topology: metrics.py:320-327 still the VERTICAL action spine
  (cur.children.insert(0,nxt) == repo addkid(before=True), first action=root, no synthetic
  ROOT).
- Re-ran clean, values EXACTLY match the recorded scorecard: metrics.py self-test;
  --mode evaluate (F1@3 0.444 / BLEU 22.721 / BP 0.457 / ROUGE-L 0.595 / NTED 0.357,
  edit 18.58, nodes 19/33 / Jaccard 0.429); --mode retrieve (tapenade top-1 BM25 17.2055 /
  TFIDF 0.7540); --mode perplexity (REAL GPT-2 CPU forward pass PPL 12.172, 719 tokens,
  mean NLL 2.4991).
- Tooling note: the Grep tool errored here (EUNKNOWN uv_spawn) twice; fell back to
  PowerShell Get-ChildItem | Select-String for the meaning-grep. Same result.

### Conclusion (carry forward — do NOT re-litigate, do NOT fake numbers)
- 98/100 is the honest ceiling for a fully-runnable, no-authors'-weights build. The
  remaining -2 (functional_reproduction 24/25 + metric_fidelity 14/15) is 100% STRUCTURAL:
  needs the authors' OneDrive TF checkpoint (interactive browser download, not HF-loadable)
  or a full 904k-Recipe1M GPU fine-tune — both impossible in this non-interactive/no-GPU
  env. 99 is unreachable here BY CONSTRUCTION. Updated 05_run.md re-verification section +
  CHANNEL S7. Future loops on this paper should STOP: no code change reaches 99.

## 루프 2 — 총점 95/100 (FAIL)
- 이번에 배운 것: Repo-verified verbatim this iteration via WebFetch: set-based ingredient-F1 (utils/metrics.py), decoding defaults temperature=1/top_k=0/top_p=0.0 and post-processing text.replace('\n','').split('<')[0] (conditional_gen_web.py), and the field-marker schema (data/recipe1M_example/test/X/*_i.txt) ALL match the app exactly — repo fidelity is genuinely high. / Iter-1 must_fix items are addressed and verified live: --mode perplexity (real PPL 12.172 over 719 tokens), --mode retrieve (real BM25/TF-IDF, tapenade top-1), avg-ingredient counting, convert_checkpoint.py path — lifted metric_fidelity 13->14 and total 94->95. / Residual honesty gap: the 'never released' -> 'released only as TF checkpoint on OneDrive' relabel was applied in primary docs but missed 3 secondary spots (main.py:81, README:55, finetune.py:6), creating an internal contradiction (README says both). Sweep ALL occurrences next time. / Structural ceiling confirmed: without running the authors' actual model (interactive OneDrive TF download + conversion) or full-corpus GPU fine-tuning, functional_reproduction and metric_fidelity cannot be perfect, so threshold 99 is unreachable for this paper by construction — 95 is a faithful, honest, fully-runnable reproduction. / This env has torch 2.4.1+cpu + transformers 4.44.2 with gpt2 cached — real GPT-2 CPU inference (perplexity forward pass) executes here, so generation/PPL claims are execution-verified, not runnable-by-structure.
- 다음 루프가 고칠 것(must_fix): Finish the honesty relabel (partially done): three residual spots still say the checkpoint was 'never released' and now contradict the app's own corrected primary docs — change main.py line 81 comment, README.md line 55, and finetune.py line 6 to 'released only as a TensorFlow checkpoint on OneDrive, not directly HF-loadable'. README currently says both (line 25 correct, line 55 wrong). / PATH-TO-99 (structural ceiling): the app never runs the authors' actual model, so it cannot regenerate the paper's own metrics. Only closure is running convert_checkpoint.py end-to-end on the real OneDrive TF checkpoint (training/gpt-2/models/model-633000) -> HF GPT-2, then `main.py --model <converted> --mode perplexity` to drive PPL toward 3.70. Requires an interactive OneDrive download (user-run); document that 99 is unreachable non-interactively/no-GPU without it. / Optional fidelity lift: surface --real-nlp (real spaCy noun-chunk heads + gensim word2vec NTED cost) in the default evaluate output header so the rule-based-vs-word2vec-cost gap is visible at runtime, not only in REPRODUCE.md.

## 루프 1 — 총점 89/100 (PASS)
- 이번에 배운 것: Repo-verified verbatim against github.com/LARC-CMU-SMU/RecipeGPT-exp (master): field markers <start-title>/<end-title>/<start-directions>/<end-directions>/<start-ingredients> (data/recipe1M_example/test/X/1264i.txt), the set-based ingredient-F1 formula (utils/metrics.py), and split('<')[0] post-processing (conditional_gen_web.py) all match the app exactly. / The RecipeGPT fine-tuned checkpoint was never publicly released, so metric reproduction and on-topic generation are inherently capped for ANY faithful build; base gpt2 + STAND-IN label + real pipeline is the honest ceiling this app hits. / This environment DOES have torch 2.4.1+cpu and transformers 4.44.2 with gpt2 weights cached — real GPT-2 CPU inference runs here, so both evaluate and gen-ingredients were execution-verified (not merely runnable-by-structure): evaluate printed real F1@3=0.444/BLEU=22.721/NTED=0.344, gen produced novel neural text. / Attribution precision matters: conditional_gen_web.py's top_p default is 0.0, not the plausible-looking 0.9 the app claims as a repo default — decoding values labeled 'from repo defaults' must be checked against the actual source default.
- 다음 루프가 고칠 것(must_fix): Fix top_p attribution: REPRODUCE.md item 4 and generate.py DEFAULTS present top_p=0.9 as a 'conditional_gen_web.py default', but the repo's actual default is top_p=0.0. Relabel top_p=0.9 as a chosen nucleus value (not a repo default), or set it to 0.0 to match the source verbatim. / metric_fidelity is capped because the paper's test-set numbers cannot be regenerated without the unreleased fine-tuned weights. Add a fine-tune script pointer (train_ppl_pickle.py, lr 1e-4, batch 8, 512 tokens, ~5 epochs) so a produced checkpoint moves the 'paper' column from reference-only to reproduced. / Optional: add a real-NLP path (spaCy noun-chunk heads + gensim word2vec cosine for the NTED relabel cost) so the method stand-ins can be disabled for a higher-fidelity run.

## 루프 1 — 총점 94/100 (FAIL)
- 이번에 배운 것: Repo-verified verbatim via WebFetch this iteration: field markers (data/recipe1M_example/test/X/1264i.txt), the set-based ingredient-F1 formula (utils/metrics.py), decoding defaults temperature=1/top_k=0/top_p=0.0 and the text.replace('\n','').split('<')[0] post-processing (conditional_gen_web.py) ALL match the app exactly — repo fidelity is genuinely high, not asserted. / The prior-iteration top_p mislabel is FIXED: generate.py/main.py/REPRODUCE.md now correctly state the repo default is top_p=0.0 and 0.9 is a chosen nucleus value reachable byte-for-byte via --top-p 0.0. / Correction for future scoring: the paper's fine-tuned weights are NOT strictly unreleased — the repo README links an OneDrive TF checkpoint (training/gpt-2/models/). The real barrier is TF->HF conversion, so 'never released' overstates it and costs an honesty point. / Fundamental ceiling: without running the authors' actual model or full-corpus fine-tuning, functional and metric reproduction cannot be perfect, so a 99 threshold is unreachable for this paper by construction — 94 reflects a faithful, honest, fully-runnable reproduction whose only gaps are the unavailable exact checkpoint and two labeled omissions (retrieval, full corpus). / This env has torch 2.4.1+cpu + transformers 4.44.2 with gpt2 cached — real GPT-2 CPU inference executes here (gen-ingredients produced novel neural text), so generation claims are execution-verified, not merely runnable-by-structure.
- 다음 루프가 고칠 것(must_fix): PATH-TO-99 (biggest cap): the app never runs the authors' own model. Add a scripted path to download the released TF checkpoint from the repo's OneDrive (training/gpt-2/models/, e.g. model-633000) and convert it to HF GPT-2 (convert_gpt2_original_tf_checkpoint_to_pytorch), then main.py --model <converted> — moves generation and the 'paper' column from base-gpt2 stand-in to the paper's real weights. / Honesty precision: relabel 'the authors never released the checkpoint' (main.py docstring, recipenlg.py, REPRODUCE.md item 5) as 'released only as a TensorFlow checkpoint on OneDrive, not directly HF-loadable' — the repo README does link a model download; the barrier is TF->HF conversion, not non-release. / Add a live --mode perplexity (token PPL over the bundled sample, companion to paper PPL=3.70) and compute avg generated-ingredient count in gen-ingredients (paper 7.8) so those two PAPER-dict entries are exercised, not display-only. / Represent the OMITTED nearest-neighbor evaluation feature (paper §4): add a lightweight BM25/TF-IDF retrieval over bundled sample_recipes.json, labeled as a small-corpus stand-in for the ElasticSearch-on-Recipe1M retrieval.

## 루프 3 — 총점 95/100 (FAIL)
- 이번에 배운 것: Repo verified verbatim via WebFetch this iteration (github.com/LARC-CMU-SMU/RecipeGPT-exp, master): F1 set-formula (utils/metrics.py), decoding defaults temperature=1/top_k=0/top_p=0.0 + post-proc text.replace('\n','').split('<')[0] (conditional_gen_web.py), NTED normalization normed=tree_dist/(ori_nodes+gen_nodes) (evaluation.py), update_cost=1-word2vec-cosine (tree.py), and the field-marker schema (data/recipe1M_example/test/X/tapenade_i.txt) ALL match the app exactly — repo fidelity is genuinely high, not asserted. / The prior 3 'never released' spots (main.py:81, README:55, finetune.py:6) WERE fixed this cycle, but generate.py:19 'did not publicly release' (same defect, different verb) was missed, so the wording-contradiction deduction persists in BOTH repo_fidelity and honesty — net total flat at 95 despite the partial fix. Sweep by meaning, not literal string. / Newly noticed repo-vs-app deviations not previously flagged: (1) repo utils/tree.py chains action nodes VERTICALLY while the app's instr_tree makes them siblings under ROOT (flat) — a NTED tree-topology difference affecting edit-distance magnitude even though the ZS algorithm + (nodes_a+nodes_b) normalization are correct; (2) F1@k top-k truncation is an app-added convenience absent from the repo's metrics.py (labeled, paper k=3). / Structural ceiling confirmed: without running the authors' actual weights (interactive OneDrive TF download + convert, or full-corpus GPU fine-tune) functional_reproduction and metric_fidelity cannot be perfect, so threshold 99 is unreachable for this paper by construction; 95 reflects a faithful, honest, fully-runnable reproduction of the method + evaluation module. / This env has torch 2.4.1+cpu + transformers 4.44.2 with gpt2 cached — evaluate/retrieve (pure stdlib) and perplexity (real GPT-2 CPU forward pass, PPL=12.172 over 719 tokens) all re-ran clean this iteration, so functional/PPL claims are execution-verified, not runnable-by-structure.
- 다음 루프가 고칠 것(must_fix): Close the last release-wording residual: generate.py line 19 still says the fine-tuned weights are ones the authors 'did not publicly release', contradicting convert_checkpoint.py:8 ('NOT unreleased') and the corrected primary docs. Change it to 'released only as a TensorFlow checkpoint on OneDrive, not directly HF-loadable'; also soften README.md:181 and recipenlg.py:20 'unreleased'. The prior sweep fixed main.py:81/README:55/finetune.py:6 but missed this 4th spot because it used a different verb — grep by meaning (did not release / publicly release / unreleased / never released). / PATH-TO-99 (structural ceiling): the app never runs the authors' actual model so it cannot regenerate the paper's own metrics. Run convert_checkpoint.py end-to-end on the real OneDrive TF checkpoint (training/gpt-2/models/model-633000) -> HF GPT-2, then main.py --model <converted> --mode perplexity to drive PPL toward 3.70. Requires an interactive OneDrive download (user-run, no GPU-free path); 99 is unreachable in a non-interactive/no-GPU env by construction (documented in REPRODUCE.md). / Method-fidelity lift (newly found): metrics.instr_tree builds a FLAT tree (all action nodes siblings under ROOT) but repo utils/tree.py build_tree chains action nodes VERTICALLY (each action a child of the previous). Rebuild instr_tree as a vertical action chain so the Zhang-Shasha edit distance matches the repo's tree semantics, or label this topology simplification explicitly in REPRODUCE.md.

## 루프 1 — 총점 98/100 (FAIL)
- 이번에 배운 것: All three fixable iteration-3 must_fixes are now CLOSED and verified live this session, lifting the total 95 -> 98: (1) release-wording residual — generate.py:19 'did not publicly release' + recipenlg.py:20/README:181 'unreleased' now all read 'released only as a TensorFlow checkpoint on OneDrive, not directly HF-loadable', consistent with convert_checkpoint.py:8 (repo_fidelity 19->20, honesty 9->10); (2) NTED tree topology — metrics.instr_tree now builds a VERTICAL action spine matching repo utils/tree.py build_tree addkid(before=True), WebFetch-confirmed, live node counts fell 20/34 -> 19/33 (method_fidelity 14->15). / Repo fidelity is genuinely MAXED (20/20), verified verbatim via WebFetch against LARC-CMU-SMU/RecipeGPT-exp master: F1 set-formula (utils/metrics.py), decoding temperature=1/top_k=0/top_p=0.0 + post-proc text.replace('\n','').split('<')[0] (conditional_gen_web.py), NTED normalization normed=tree_dist/(ori_nodes+gen_nodes) (evaluation.py), update_cost=1-word2vec-cosine + build_tree vertical spine (tree.py), and the field-marker schema (data/recipe1M_example) ALL match the app. / The remaining 2-point gap is 100% structural: functional_reproduction and metric_fidelity are each capped at -1 because the paper's fine-tuned weights are OneDrive-only TF (interactive, not HF-loadable) and the full 904k Recipe1M + GPU are needed to regenerate exact numbers. threshold 99 is unreachable for this paper in a non-interactive/no-GPU env by construction; 98 reflects a faithful, honest, fully-runnable reproduction of the method + evaluation module with only labeled checkpoint/scale/data omissions. / Live-execution confirmed this env: python 3.12.10 + torch 2.4.1+cpu + transformers 4.44.2 with gpt2 cached — evaluate/retrieve (pure stdlib) and perplexity (real GPT-2 CPU forward pass, PPL=12.172 over 719 tokens) all ran clean, so functional/PPL claims are execution-verified, not runnable-by-structure. Future loops cannot exceed 98 without the OneDrive weights — stop chasing the last 2 points with code changes.
- 다음 루프가 고칠 것(must_fix): PATH-TO-99 (structural ceiling — the ONLY remaining gap, worth 2 pts and NOT a fixable code defect): the app never runs the authors' actual model, so it cannot regenerate the paper's own metrics (functional_reproduction 24/25, metric_fidelity 14/15). Closure requires running convert_checkpoint.py end-to-end on the real OneDrive TF checkpoint (training/gpt-2/models/model-633000) -> HF GPT-2, then `python main.py --model <converted> --mode perplexity` to drive PPL toward 3.70. This needs an interactive OneDrive download and/or full-corpus GPU fine-tune — impossible in this non-interactive/no-GPU environment. REPRODUCE.md already documents 99 is unreachable here by construction; do NOT attempt further code edits for these last 2 points, they are environmental.

## 루프 2 — 총점 98/100 (FAIL)
- 이번에 배운 것: Iteration 2 delivered a genuine, verified functional improvement over iteration 1: `--format recipenlg` drives a REAL recipe-fine-tuned GPT-2 (pratultandon/recipe-nlg-gpt2, cached in this env) and produced a coherent recipe live ('Spaghetti With Garlic' + 4 ingredients + 6 steps) with the live evaluation module run on it. Honestly labeled as a different-corpus checkpoint than the paper's, so it strengthens the functional demonstration but does not lift the exact-weights structural cap. / Repo fidelity re-verified verbatim via WebFetch this session (LARC-CMU-SMU/RecipeGPT-exp master): F1 set-formula (utils/metrics.py), decoding defaults model='117M'/temp=1/top_k=0/top_p=0.0 + post-proc text.replace('\n','').split('<')[0] (conditional_gen_web.py), NTED norm=tree_dist/(ori_nodes+gen_nodes) with node count sum(len(ingredient)+1) (evaluation.py), update_cost=1-word2vec-cosine + build_tree vertical spine addkid(before=True) (tree.py). All match the app — repo_fidelity genuinely maxed 20/20. / The remaining 2-point gap is 100% structural/environmental: the paper's own weights are OneDrive TF-only (interactive download, not HF-loadable) and exact numbers need the full 904k corpus + GPU. At threshold 99 in a non-interactive/no-GPU env this is unreachable by construction; 98 reflects a faithful, honest, fully-runnable reproduction of the method + evaluation module. / Env has torch 2.4.1+cpu + transformers 4.44.2 with BOTH gpt2 and pratultandon/recipe-nlg-gpt2 cached, python 3.12.10; all five modes (evaluate, retrieve, perplexity, recipenlg gen, recipegpt gen) ran clean this session — all functional claims are execution-verified, not runnable-by-structure. Future loops cannot exceed 98 without the OneDrive weights.
- 다음 루프가 고칠 것(must_fix): STRUCTURAL CEILING (the only remaining 2 pts, NOT a fixable code defect): functional_reproduction (24/25) and metric_fidelity (14/15) are each capped -1 because the app never runs the authors' EXACT Recipe1M fine-tuned weights, released only as a TF checkpoint on the authors' OneDrive (training/gpt-2/models/model-633000, not HF-loadable). Closing it requires an interactive OneDrive download + convert_checkpoint.py TF->HF + `main.py --model <converted> --mode perplexity` to drive PPL toward 3.70, OR a full-corpus (904k) GPU fine-tune via finetune.py --data. Both are impossible in this non-interactive/no-GPU env. The iteration-2 --format recipenlg addition already maximized achievable functional evidence (real recipe output via a real recipe-fine-tuned GPT-2). Recommend stopping the loop on this paper — no code change reaches 99 here.

## 루프 3 — 총점 98/100 (FAIL)
- 이번에 배운 것: Iteration 3 re-verified everything LIVE end-to-end (Python 3.12.10, torch 2.4.1+cpu, transformers 4.44.2): evaluate (F1@3=0.444/BLEU=22.721/NTED=0.357), retrieve (BM25 tapenade top-1 17.2055), perplexity (real GPT-2 forward pass PPL=12.172/719 tokens), and --format recipenlg gen (real recipe 'Spaghetti With Garlic' + 4 ingredients + 6 steps). All functional claims execution-verified, not asserted — no hardcoded results, no fake logs. / Repo fidelity re-verified verbatim via WebFetch this session (LARC-CMU-SMU/RecipeGPT-exp master): F1 set-formula with NO top-k in repo (utils/metrics.py), decode defaults 117M/temp1/top_k0/top_p0.0 + post-proc text.replace('\n','').split('<')[0] (conditional_gen_web.py), NTED norm=tree_dist/(ori_nodes+gen_nodes) node count sum(len(ingredient)+1) (evaluation.py), update_cost=1-word2vec-cosine + build_tree vertical spine addkid(before=True) first action=root (tree.py). ALL match the app — repo_fidelity genuinely 20/20, not asserted. / The remaining 2-point gap is 100% structural/environmental: the paper's own fine-tuned weights are released only as a TF checkpoint on OneDrive (interactive-only, not HF-loadable) and the full 904k corpus + GPU are needed for the exact numbers (F1 0.76 / PPL 3.70). At threshold 99 in a non-interactive/no-GPU env this is unreachable by construction. / Three iterations have converged on 98/98/98 — the score is stable and the last 2 points are environmental, not addressable by code. Future loops on this paper cannot exceed 98 without the OneDrive weights; do not attempt further code fixes for the last 2 points. Stop the loop.
- 다음 루프가 고칠 것(must_fix): STRUCTURAL CEILING (only remaining gap, 2 pts) — NOT a fixable code defect, confirmed again in iteration 3. functional_reproduction (24/25) and metric_fidelity (14/15) are each capped -1 because the app never runs the authors' EXACT Recipe1M fine-tuned weights (released only as a TF checkpoint on OneDrive: training/gpt-2/models/model-633000, not HF-loadable). Closing it needs: (1) interactive OneDrive download (browser-only, cannot be scripted) + convert_checkpoint.py TF->HF; or (2) full-corpus 904k GPU fine-tune via finetune.py --data. Both impossible in this non-interactive/no-GPU env. No code change reaches threshold 99 here — recommend stopping the loop and accepting 98 as the honest ceiling.
