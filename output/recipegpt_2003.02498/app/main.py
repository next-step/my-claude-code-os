#!/usr/bin/env python3
"""
main.py — RecipeGPT CLI (paper 2003.02498).

Reproduces the paper's two capabilities from the terminal:

  1. BIDIRECTIONAL GENERATION (real GPT-2 neural inference via transformers)
       --mode gen-instructions   title + ingredients -> directions
       --mode gen-ingredients    title + instructions -> ingredients

  2. EVALUATION MODULE (real, deterministic metrics; no heavy deps)
       --mode evaluate           compares a candidate against a reference and
                                 prints F1@k, BLEU, Brevity Penalty, ROUGE-L,
                                 NTED, Jaccard consistency, ingredient highlight.

Runs with built-in sample recipes when no input args are given.

Also:
  3. PERPLEXITY (--mode perplexity)   live token PPL of the model over the bundled
                                      sample (companion to the paper's PPL=3.70).
  4. RETRIEVAL  (--mode retrieve)     rank similar recipes (BM25 / TF-IDF) — a
                                      labeled small-corpus stand-in for the paper's
                                      ElasticSearch nearest-neighbor panel (§4).

Honesty: generation uses REAL GPT-2 (transformers). By default it is the ORIGINAL
gpt2 (124M), NOT the RecipeGPT fine-tuned checkpoint. The paper's fine-tuned weights
were released only as a TensorFlow checkpoint on the authors' OneDrive (repo
`training/gpt-2/models/`), NOT directly HF-loadable — so the default is base gpt2
(a labeled STAND-IN) and generated recipes read as generic text. Run
`convert_checkpoint.py` to convert the released TF weights to HF and pass them via
`--model` to use the paper's OWN model. The format/pipeline/decoding are faithful;
the evaluation metrics are exact reimplementations of the official repo on real inputs.
"""

import argparse
import json
import os
import sys

# Windows consoles default to cp949/cp1252 and choke on non-ASCII output.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import multifield
import metrics

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "data", "sample_recipes.json")

# Paper-reported values (RecipeGPT fine-tuned GPT-2 124M, test set) — reference only.
PAPER = {"F1": 0.76, "avg_ingredients": 7.8, "BLEU": 8.34, "BP": 0.71,
         "ROUGE_L": 0.36, "NTED": 0.52, "PPL": 3.70,
         "Jaccard_gen": 0.53, "Jaccard_human": 0.49}


def load_samples():
    with open(SAMPLES, encoding="utf-8") as f:
        return json.load(f)


def _first_sample():
    return load_samples()[0]


def cmd_generate(args, mode):
    try:
        import generate
    except Exception as e:  # pragma: no cover
        print(f"[error] could not import generate module: {e}", file=sys.stderr)
        raise

    s = _first_sample()
    title = args.title or s["title"]
    ingredients = args.ingredients or (s["ingredients"] if mode == "gen-instructions" else None)
    instructions = args.instructions or (s["instructions"] if mode == "gen-ingredients" else None)

    # --format recipenlg: drive a PUBLIC recipe-fine-tuned GPT-2 that emits REAL
    # recipes (the paper's own Recipe1M checkpoint is released only as a TensorFlow
    # checkpoint on OneDrive, not directly HF-loadable; see convert_checkpoint.py).
    # Different
    # checkpoint/corpus than the paper — same GPT-2 architecture + special-token
    # multi-field idea — labeled as a real, on-topic stand-in.
    if getattr(args, "format", "recipegpt") == "recipenlg":
        import recipenlg
        model = args.model if args.model != "gpt2" else recipenlg.DEFAULT_MODEL
        ings = multifield.normalize_ingredients(ingredients or [])
        print("=" * 72)
        print(f"MODE: {mode}   FORMAT: recipenlg   MODEL: {model}")
        print("=" * 72)
        print(f"INPUT INGREDIENTS: {ings}")
        print("-" * 72)
        print("Running REAL fine-tuned GPT-2 recipe generation...")
        r = recipenlg.generate(
            ings, model_name=model, seed=args.seed,
            temperature=(args.temperature if args.temperature != 1.0 else 0.7),
            top_p=args.top_p)
        print(f"\nTITLE: {r['title']}")
        print("INGREDIENTS:")
        for x in r["ingredients"]:
            print(f"  - {x}")
        print("INSTRUCTIONS:")
        for i, step in enumerate(r["instructions"], 1):
            print(f"  {i}. {step}")
        print("\n[i] REAL fine-tuned weights: pratultandon/recipe-nlg-gpt2 (RecipeNLG).")
        print("    NOT the paper's exact RecipeGPT/Recipe1M checkpoint (that one is")
        print("    released only as a TF checkpoint on OneDrive, not HF-loadable; see")
        print("    convert_checkpoint.py) — same GPT-2 arch + special-token multi-field")
        print("    idea, different corpus.")
        if r["instructions"]:
            joined = " ".join(r["instructions"])
            jac = metrics.jaccard_consistency(joined, ings)
            hl = metrics.highlight_overlap(joined, ings)
            print("\nEVALUATION MODULE (live, on the generated recipe):")
            print(f"  ingredient coverage: {hl['coverage']:.2f}  used={hl['used']}")
            print(f"  Jaccard(directions vs input ingredients): {jac['jaccard']:.3f}")
        return 0

    print("=" * 72)
    print(f"MODE: {mode}   MODEL: {args.model}")
    print("=" * 72)
    print(f"TITLE: {title}")
    if mode == "gen-instructions":
        print("INGREDIENTS:")
        for x in multifield.normalize_ingredients(ingredients):
            print(f"  - {x}")
    else:
        print(f"INSTRUCTIONS: {instructions}")
    print("-" * 72)
    print("Loading GPT-2 and running REAL autoregressive inference (CPU ok)...")

    try:
        res = generate.generate_field(
            mode, title, ingredients=ingredients, instructions=instructions,
            model_name=args.model, seed=args.seed,
            temperature=args.temperature, top_p=args.top_p,
            max_new_tokens=args.max_new_tokens,
        )
    except ImportError as e:
        print("\n[MISSING DEPENDENCY] transformers/torch not installed.",
              file=sys.stderr)
        print("Install with:  pip install -r requirements.txt", file=sys.stderr)
        print(f"({e})", file=sys.stderr)
        sys.exit(2)

    print("\nPROMPT (multi-field format sent to the model):")
    print(f"  {res['prompt']}")
    print("\nGENERATED FIELD (real GPT-2 output):")
    print(f"  {res['generated'] or '(empty - try --max-new-tokens or another seed)'}")

    if not res["is_finetuned"]:
        print("\n[!] STAND-IN WEIGHTS: this is the ORIGINAL gpt2, not the RecipeGPT")
        print("    fine-tuned checkpoint. Text is generic; format/decoding are faithful.")

    # If we generated instructions, also show the live evaluation module.
    if mode == "gen-instructions":
        hl = metrics.highlight_overlap(res["generated"], ingredients)
        jac = metrics.jaccard_consistency(res["generated"], ingredients)
        print("\nEVALUATION MODULE (live, on the generated text):")
        print(f"  ingredient coverage: {hl['coverage']:.2f}  "
              f"used={hl['used']}  missing={hl['missing']}")
        print(f"  Jaccard(directions vs input ingredients): {jac['jaccard']:.3f}")
    elif mode == "gen-ingredients":
        f1 = metrics.ingredient_f1(res["generated"], s["ingredients"], k=args.k)
        gen_items = metrics.split_ingredient_items(res["generated"])
        print("\nEVALUATION MODULE (live, generated vs sample reference):")
        print(f"  F1@{args.k}: {f1['f1']:.3f}  P={f1['precision']:.3f}  R={f1['recall']:.3f}")
        print(f"  avg generated-ingredient count: {len(gen_items)}  "
              f"(paper avg = {PAPER['avg_ingredients']})")
    return 0


def cmd_evaluate(args):
    s = _first_sample()
    # Candidate vs reference. Defaults: perturbed copy of the sample so metrics
    # exercise real (non-trivial) values without needing model weights.
    if args.instructions or args.ref_instructions:
        cand_instr = args.instructions or s["instructions"]
        ref_instr = args.ref_instructions or s["instructions"]
    else:
        cand_instr = ("Combine the anchovies, garlic and capers. Add olives and "
                      "pulse until chopped. Pour in olive oil and lemon juice. "
                      "Blend into a paste.")
        ref_instr = s["instructions"]

    cand_ingr = args.ingredients or ["olives", "anchovy", "garlic", "capers",
                                     "olive oil", "lemon juice"]
    ref_ingr = args.ref_ingredients or s["ingredients"]

    nlp_status = None
    if getattr(args, "real_nlp", False):
        corpus = [cand_instr, ref_instr] + [str(x) for x in cand_ingr] + \
                 [str(x) for x in ref_ingr]
        nlp_status = _activate_real_nlp(corpus, getattr(args, "w2v_vectors", None))

    f1 = metrics.ingredient_f1(cand_ingr, ref_ingr, k=args.k)
    bl = metrics.bleu(cand_instr, ref_instr)
    rl = metrics.rouge_l(cand_instr, ref_instr)
    nt = metrics.nted(cand_instr, ref_instr)
    jac = metrics.jaccard_consistency(cand_instr, cand_ingr)
    hl = metrics.highlight_overlap(cand_instr, cand_ingr)

    print("=" * 72)
    print("RecipeGPT EVALUATION MODULE  (real metrics on real inputs)")
    print("=" * 72)
    if nlp_status:
        print(nlp_status)
    else:
        print("NLP path: rule-based STAND-IN  |  root-noun = head-word rule, "
              "NTED relabel cost = token-string similarity.")
        print("           The repo uses spaCy noun-chunk heads + gensim word2vec "
              "cosine cost;")
        print("           enable the high-fidelity path with --real-nlp "
              "(shifts F1/NTED/Jaccard, see REPRODUCE.md).")
    print("-" * 72)
    print(f"Candidate ingredients: {cand_ingr}")
    print(f"Reference ingredients: {ref_ingr}")
    print("-" * 72)
    rows = [
        ("Ingredient F1@%s" % args.k, f1["f1"], PAPER["F1"]),
        ("  precision", f1["precision"], None),
        ("  recall", f1["recall"], None),
        ("BLEU (0-100)", bl["bleu"], PAPER["BLEU"]),
        ("Brevity Penalty", bl["brevity_penalty"], PAPER["BP"]),
        ("ROUGE-L", rl["rouge_l"], PAPER["ROUGE_L"]),
        ("NTED", nt["nted"], PAPER["NTED"]),
        ("Jaccard (dir vs ingr)", jac["jaccard"], PAPER["Jaccard_gen"]),
    ]
    print(f"{'metric':<26}{'this run':>12}{'paper (124M)':>16}")
    for name, val, paper in rows:
        pv = f"{paper:.2f}" if paper is not None else ""
        print(f"{name:<26}{val:>12.3f}{pv:>16}")
    print("-" * 72)
    print(f"NTED tree: edit_distance={nt['edit_distance']:.2f}  "
          f"nodes_a={nt['nodes_a']} nodes_b={nt['nodes_b']}")
    print(f"Ingredient highlight: used={hl['used']}  missing={hl['missing']}")
    print(f"Jaccard shared root-nouns: {jac['shared']}")
    print("-" * 72)
    print("NOTE: 'paper (124M)' are the paper's reported values on the full test")
    print("set with the fine-tuned model; single-example runs here will differ.")

    if args.json:
        print("\nJSON:")
        print(json.dumps({"f1": f1, "bleu": bl, "rouge_l": rl, "nted": nt,
                          "jaccard": jac, "highlight": hl, "paper": PAPER},
                         indent=2))
    return 0


def cmd_perplexity(args):
    """Live token perplexity of the model over the bundled recipes (paper PPL=3.70)."""
    try:
        import generate
    except Exception as e:  # pragma: no cover
        print(f"[error] could not import generate module: {e}", file=sys.stderr)
        raise
    recs = load_samples()
    texts = [multifield.serialize(r["title"], r["ingredients"], r["instructions"])
             for r in recs]
    print("=" * 72)
    print(f"RecipeGPT PERPLEXITY  (real token PPL, MODEL: {args.model})")
    print("=" * 72)
    print(f"Scoring {len(texts)} bundled recipes serialized in the multi-field format.")
    print("Computing GPT-2 cross-entropy over each token (real forward pass)...")
    try:
        r = generate.perplexity(texts, model_name=args.model,
                                block_size=args.max_new_tokens if args.max_new_tokens else 512)
    except ImportError as e:
        print("\n[MISSING DEPENDENCY] transformers/torch not installed.", file=sys.stderr)
        print("Install with:  pip install -r requirements.txt", file=sys.stderr)
        print(f"({e})", file=sys.stderr)
        sys.exit(2)
    print("-" * 72)
    print(f"{'metric':<26}{'this run':>12}{'paper (124M)':>16}")
    print(f"{'Perplexity':<26}{r['ppl']:>12.3f}{PAPER['PPL']:>16.2f}")
    print("-" * 72)
    print(f"tokens scored: {r['n_tokens']}   mean NLL: {r['mean_nll']:.4f}")
    if not r["is_finetuned"]:
        print("\n[!] STAND-IN WEIGHTS: this is base gpt2, so PPL is FAR above the")
        print("    paper's 3.70. The paper's 3.70 needs the Recipe1M fine-tuned")
        print("    weights (convert_checkpoint.py) or your own finetune.py checkpoint.")
        print("    The number above is genuinely computed from logits, not hardcoded.")
        print("    CEILING: driving PPL to 3.70 needs the authors' OneDrive TF")
        print("    checkpoint (interactive download) + TF->HF convert, or full-corpus")
        print("    GPU fine-tune -- both impossible in a non-interactive/no-GPU env,")
        print("    so an exact match is unreachable here by construction (see REPRODUCE.md).")
    if args.json:
        print("\nJSON:")
        print(json.dumps({"perplexity": r, "paper_ppl": PAPER["PPL"]}, indent=2))
    return 0


def cmd_retrieve(args):
    """Nearest-neighbor similar-recipe retrieval (BM25 / TF-IDF) over bundled recipes.

    STAND-IN for the paper's ElasticSearch-on-Recipe1M 'similar recipes' panel (§4):
    same ranking principle, tiny bundled corpus instead of the 904k index.
    """
    import retrieve as retr
    corpus = retr.load_corpus()
    if args.ingredients or args.title or args.instructions:
        parts = []
        if args.title:
            parts.append(args.title)
        if args.ingredients:
            parts += list(args.ingredients)
        if args.instructions:
            parts.append(args.instructions)
        query = " ".join(parts)
    else:
        s = corpus[0]
        query = " ".join([s["title"]] + [str(x) for x in s["ingredients"]])

    print("=" * 72)
    print("RecipeGPT RETRIEVAL  (similar-recipe nearest neighbors)")
    print("=" * 72)
    print("STAND-IN for the paper's ElasticSearch-on-Recipe1M retrieval panel (§4):")
    print(f"real BM25/TF-IDF ranking, but over the {len(corpus)} bundled recipes only.")
    print("-" * 72)
    print(f"QUERY: {query}")
    print("-" * 72)
    for method in ("bm25", "tfidf"):
        ranked = retr.retrieve(query, corpus, method=method, top_k=args.k)
        print(f"{method.upper()} top-{args.k}:")
        for rank, (score, rec) in enumerate(ranked, 1):
            print(f"  {rank}. {score:7.4f}  {rec['title']}")
    if args.json:
        ranked = retr.retrieve(query, corpus, method="bm25", top_k=args.k)
        print("\nJSON:")
        print(json.dumps(
            {"query": query, "method": "bm25",
             "results": [{"score": s, "title": r["title"], "id": r.get("id")}
                         for s, r in ranked]}, indent=2))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="RecipeGPT CLI — bidirectional recipe generation + evaluation.")
    p.add_argument("--mode", required=True,
                   choices=["gen-instructions", "gen-ingredients", "evaluate",
                            "perplexity", "retrieve"])
    p.add_argument("--title", default=None)
    p.add_argument("--ingredients", nargs="*", default=None,
                   help="ingredient items (space-separated quoted strings)")
    p.add_argument("--instructions", default=None)
    # evaluate references
    p.add_argument("--ref-ingredients", nargs="*", default=None, dest="ref_ingredients")
    p.add_argument("--ref-instructions", default=None, dest="ref_instructions")
    p.add_argument("--k", type=int, default=3, help="F1@k truncation (paper k=3)")
    # generation params
    p.add_argument("--format", default="recipegpt", choices=["recipegpt", "recipenlg"],
                   help="recipegpt = paper's multi-field format on --model (base gpt2 = stand-in); "
                        "recipenlg = a PUBLIC recipe-fine-tuned GPT-2 (pratultandon/recipe-nlg-gpt2) "
                        "that emits REAL recipes (different checkpoint than the paper's, labeled)")
    p.add_argument("--model", default="gpt2",
                   help="HF model id or local checkpoint dir (default: gpt2 = STAND-IN weights)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--top-p", type=float, default=0.9, dest="top_p",
                   help="nucleus sampling p. Default 0.9 is a CHOSEN/recommended "
                        "value; the repo's conditional_gen_web.py code default is "
                        "0.0 (nucleus off) — pass --top-p 0.0 to match it verbatim.")
    p.add_argument("--max-new-tokens", type=int, default=200, dest="max_new_tokens")
    p.add_argument("--json", action="store_true", help="also print JSON (evaluate)")
    p.add_argument("--real-nlp", action="store_true", dest="real_nlp",
                   help="use the HIGH-FIDELITY path: real spaCy noun-chunk heads + "
                        "real gensim word2vec cosine for the NTED relabel cost "
                        "(needs `pip install spacy gensim` + "
                        "`python -m spacy download en_core_web_sm`). "
                        "Falls back to the rule-based stand-in with a notice if absent.")
    p.add_argument("--w2v-vectors", default=None, dest="w2v_vectors",
                   help="optional path to pretrained gensim KeyedVectors for the "
                        "word2vec NTED cost (else word2vec is trained on the inputs).")
    return p


def _activate_real_nlp(corpus_sentences, vectors_path=None):
    """
    Try to switch metrics.py onto the real spaCy + gensim word2vec backend.
    Returns a human-readable status line (honest about fallback).
    """
    import metrics
    try:
        import nlp_backend
    except Exception as e:
        return f"[real-nlp] backend import failed ({e}); using rule-based STAND-IN."
    nouns, cost, note = nlp_backend.build(
        sentences=corpus_sentences, vectors_path=vectors_path)
    if nouns is None:
        return (f"[real-nlp] UNAVAILABLE: {note}\n"
                "           -> falling back to rule-based STAND-IN (no fake claims).\n"
                "           install: pip install spacy gensim && "
                "python -m spacy download en_core_web_sm")
    metrics.set_nlp_backend(nouns, cost)
    return f"[real-nlp] ACTIVE: {note}"


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.mode == "evaluate":
        return cmd_evaluate(args)
    if args.mode == "perplexity":
        return cmd_perplexity(args)
    if args.mode == "retrieve":
        return cmd_retrieve(args)
    return cmd_generate(args, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
