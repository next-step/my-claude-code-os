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

Honesty: generation uses REAL GPT-2 (transformers). By default it is the ORIGINAL
gpt2 (124M), NOT the RecipeGPT fine-tuned checkpoint (not publicly released), so
generated recipes read as generic text — the format/pipeline/decoding are faithful,
only the trained weights are a stand-in. The evaluation metrics are exact
reimplementations of the official repo and run on real inputs.
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
        print("\nEVALUATION MODULE (live, generated vs sample reference):")
        print(f"  F1@{args.k}: {f1['f1']:.3f}  P={f1['precision']:.3f}  R={f1['recall']:.3f}")
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

    f1 = metrics.ingredient_f1(cand_ingr, ref_ingr, k=args.k)
    bl = metrics.bleu(cand_instr, ref_instr)
    rl = metrics.rouge_l(cand_instr, ref_instr)
    nt = metrics.nted(cand_instr, ref_instr)
    jac = metrics.jaccard_consistency(cand_instr, cand_ingr)
    hl = metrics.highlight_overlap(cand_instr, cand_ingr)

    print("=" * 72)
    print("RecipeGPT EVALUATION MODULE  (real metrics on real inputs)")
    print("=" * 72)
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


def build_parser():
    p = argparse.ArgumentParser(
        description="RecipeGPT CLI — bidirectional recipe generation + evaluation.")
    p.add_argument("--mode", required=True,
                   choices=["gen-instructions", "gen-ingredients", "evaluate"])
    p.add_argument("--title", default=None)
    p.add_argument("--ingredients", nargs="*", default=None,
                   help="ingredient items (space-separated quoted strings)")
    p.add_argument("--instructions", default=None)
    # evaluate references
    p.add_argument("--ref-ingredients", nargs="*", default=None, dest="ref_ingredients")
    p.add_argument("--ref-instructions", default=None, dest="ref_instructions")
    p.add_argument("--k", type=int, default=3, help="F1@k truncation (paper k=3)")
    # generation params
    p.add_argument("--model", default="gpt2",
                   help="HF model id or local checkpoint dir (default: gpt2 = STAND-IN weights)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--top-p", type=float, default=0.9, dest="top_p")
    p.add_argument("--max-new-tokens", type=int, default=200, dest="max_new_tokens")
    p.add_argument("--json", action="store_true", help="also print JSON (evaluate)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.mode == "evaluate":
        return cmd_evaluate(args)
    return cmd_generate(args, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
