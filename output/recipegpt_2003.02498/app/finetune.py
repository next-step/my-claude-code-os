#!/usr/bin/env python3
"""
finetune.py — REAL fine-tuning of GPT-2 into RecipeGPT (paper 2003.02498, §6).

This is the piece that UNLOCKS metric reproduction. The paper's own Recipe1M
fine-tuned checkpoint was released only as a TensorFlow checkpoint on OneDrive
(training/gpt-2/models/, e.g. model-633000), not directly HF-loadable, so
`main.py` defaults to base `gpt2` (a STAND-IN whose text is generic). To load
the authors' own weights instead, see convert_checkpoint.py (TF->HF). This
script is the other path: it lets you PRODUCE a real
checkpoint yourself: it fine-tunes GPT-2 on recipes serialized in the exact
multi-field special-token format, using the paper's training recipe. Point
`main.py --model <out_dir>` at the result and the `paper` column in evaluate
moves from reference-only toward reproduced.

Paper / repo training setup (01_analysis.md §6; repo training/gpt-2/train_ppl_pickle.py):
  * backbone     : GPT-2 124M  (repo calls it '117M')
  * max tokens   : 512  (Recipe1M 98.6% coverage), pad id 16791, ingr-sep id 3
  * batch size   : 8
  * learning rate: 1e-4
  * schedule     : ~5 epochs (~5 days on a single V100 over the full 904k corpus)
This script exposes those exact defaults (--epochs/--batch/--lr/--block-size).

Honesty:
  * The METHOD here (special-token multi-field serialization + GPT-2 causal-LM
    fine-tuning at lr 1e-4 / batch 8 / 512 tokens) is the paper's, implemented for
    real with HuggingFace transformers — this really trains.
  * The DATA that ships with this app is a tiny bundled sample (data/*.json), NOT
    the full 904k Recipe1M corpus (not redistributable here). Fine-tuning on the
    sample is a real-but-small DEMO: it overfits and will NOT reach the paper's
    test-set F1/BLEU. To reproduce the paper's numbers, pass --data <recipe1M.jsonl>
    with the full corpus (see --help). No numbers are faked; you get exactly what
    you trained.

Unlike base gpt2, a model fine-tuned HERE is trained WITH the field markers as
real special tokens (embeddings resized + learned), so at inference the markers
behave as true delimiters — matching the paper's setup (generate.py add_markers).

Usage:
  # smoke DEMO on the bundled sample (CPU, tiny; proves the loop runs):
  python finetune.py --demo --out ckpt_demo --epochs 1 --max-steps 3

  # real reproduction run on the full corpus (GPU strongly recommended):
  python finetune.py --data recipe1m.jsonl --out recipegpt-124m \
      --epochs 5 --batch 8 --lr 1e-4 --block-size 512
  #   recipe1m.jsonl = one JSON per line: {"title","ingredients":[...],"instructions"}

  # then generate / evaluate with YOUR checkpoint:
  python main.py --mode gen-instructions --model recipegpt-124m
"""

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import multifield

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_records(data_path, demo):
    """Yield {title, ingredients, instructions} dicts."""
    if demo or not data_path:
        with open(os.path.join(HERE, "data", "sample_recipes.json"),
                  encoding="utf-8") as f:
            recs = json.load(f)
        # tiny corpus: repeat so the demo has a few steps to run
        return recs * 8 if demo else recs
    recs = []
    with open(data_path, encoding="utf-8") as f:
        if data_path.endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
        else:
            recs = json.load(f)
    return recs


def _serialize_records(recs):
    """Each recipe -> the paper's single multi-field sequence (+ EOS)."""
    seqs = []
    for r in recs:
        seqs.append(multifield.serialize(
            r["title"], r["ingredients"], r["instructions"]))
    return seqs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fine-tune GPT-2 -> RecipeGPT.")
    ap.add_argument("--data", default=None,
                    help="path to corpus (.jsonl / .json). Omit + --demo for the "
                         "bundled sample. Full Recipe1M reproduces paper numbers.")
    ap.add_argument("--demo", action="store_true",
                    help="tiny CPU smoke run on the bundled sample (overfits).")
    ap.add_argument("--model", default="gpt2", help="base model to fine-tune")
    ap.add_argument("--out", default="recipegpt-124m", help="output checkpoint dir")
    ap.add_argument("--epochs", type=float, default=5.0, help="paper: ~5")
    ap.add_argument("--batch", type=int, default=8, help="paper: 8")
    ap.add_argument("--lr", type=float, default=1e-4, help="paper: 1e-4")
    ap.add_argument("--block-size", type=int, default=512, dest="block_size",
                    help="paper: 512 tokens")
    ap.add_argument("--max-steps", type=int, default=-1, dest="max_steps",
                    help="cap steps (use for --demo, e.g. 3). -1 = full epochs.")
    args = ap.parse_args(argv)

    try:
        import torch  # noqa
        from transformers import (GPT2LMHeadModel, GPT2TokenizerFast,
                                  Trainer, TrainingArguments,
                                  DataCollatorForLanguageModeling)
        from datasets import Dataset
    except Exception as e:
        print("[MISSING DEPENDENCY] need transformers + datasets + torch.",
              file=sys.stderr)
        print("Install:  pip install -r requirements.txt datasets", file=sys.stderr)
        print(f"({e})", file=sys.stderr)
        return 2

    recs = _load_records(args.data, args.demo)
    seqs = _serialize_records(recs)
    print(f"[data] {len(seqs)} serialized multi-field recipes "
          f"({'DEMO sample' if (args.demo or not args.data) else args.data})")

    # Tokenizer WITH the recipe markers as REAL special tokens (paper setup).
    tok = GPT2TokenizerFast.from_pretrained(args.model)
    tok.add_special_tokens({"additional_special_tokens": multifield.SPECIAL_TOKENS})
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = GPT2LMHeadModel.from_pretrained(args.model)
    model.resize_token_embeddings(len(tok))   # learn the new marker embeddings

    def tok_fn(batch):
        return tok(batch["text"], truncation=True, max_length=args.block_size)

    ds = Dataset.from_dict({"text": [s + tok.eos_token for s in seqs]})
    ds = ds.map(tok_fn, batched=True, remove_columns=["text"])

    collator = DataCollatorForLanguageModeling(tok, mlm=False)  # causal LM
    targs = TrainingArguments(
        output_dir=args.out,
        per_device_train_batch_size=args.batch,
        learning_rate=args.lr,                 # paper 1e-4
        num_train_epochs=args.epochs,          # paper ~5
        max_steps=args.max_steps,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        seed=0,
    )
    trainer = Trainer(model=model, args=targs,
                      train_dataset=ds, data_collator=collator)
    print(f"[train] lr={args.lr} batch={args.batch} block={args.block_size} "
          f"epochs={args.epochs} max_steps={args.max_steps} "
          f"(paper: lr 1e-4, batch 8, 512 tok, ~5 epochs)")
    trainer.train()

    os.makedirs(args.out, exist_ok=True)
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    print(f"[done] saved fine-tuned RecipeGPT checkpoint -> {args.out}")
    print(f"       generate:  python main.py --mode gen-instructions --model {args.out}")
    if args.demo or not args.data:
        print("[note] this was the tiny bundled DEMO — it OVERFITS and will NOT")
        print("       reach the paper's test-set numbers. Use --data <full recipe1M>.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
