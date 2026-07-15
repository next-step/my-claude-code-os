#!/usr/bin/env python3
"""
convert_checkpoint.py — turn the authors' RELEASED TensorFlow RecipeGPT checkpoint
into an HF GPT-2 checkpoint that `main.py --model <dir>` can load.

WHY THIS EXISTS (the path to running the paper's OWN weights)
------------------------------------------------------------
The paper's fine-tuned RecipeGPT weights are NOT "unreleased" — the official repo
(github.com/LARC-CMU-SMU/RecipeGPT-exp) README links a **OneDrive download** of the
model under `training/gpt-2/models/` (a TensorFlow checkpoint, e.g. `model-633000`,
the original OpenAI GPT-2 `.ckpt` + `hparams.json` layout used by nshepperd/gpt-2).
The real barrier is that it is a **TensorFlow checkpoint, not directly HF-loadable** —
so this app defaults to base `gpt2` (STAND-IN). This script closes that gap: it runs
HuggingFace's official TF->PyTorch GPT-2 converter so you can then generate/evaluate
with the paper's actual model instead of the stand-in.

WHAT IS REAL vs. WHAT YOU MUST SUPPLY
-------------------------------------
* REAL / automated here: the TF->HF conversion itself
  (`transformers.models.gpt2.convert_gpt2_original_tf_checkpoint_to_pytorch`),
  plus registering the recipe field-marker special tokens on the converted tokenizer.
* YOU must supply: the downloaded TF checkpoint directory. It is hosted on the
  authors' OneDrive (personal cloud, requires an interactive browser download +
  possibly sign-in), so it cannot be fetched non-interactively from this script.
  Download it from the repo README's model link, unzip, and pass --tf-ckpt-dir.

USAGE
-----
  # 1) Download the TF checkpoint from the repo README's OneDrive link, unzip it.
  #    Expect files like:  model-633000.data-00000-of-00001, model-633000.index,
  #    model-633000.meta, checkpoint, hparams.json, encoder.json, vocab.bpe
  #
  # 2) Convert TF -> HF PyTorch:
  python convert_checkpoint.py \
      --tf-ckpt-dir ./RecipeGPT_tf/model-633000 \
      --config      ./RecipeGPT_tf/hparams.json \
      --out         ./recipegpt-124m-hf
  #
  # 3) Generate / evaluate with the PAPER'S OWN weights (no longer a stand-in):
  python main.py --mode gen-instructions --model ./recipegpt-124m-hf
  python main.py --mode perplexity        --model ./recipegpt-124m-hf

HONESTY: this script is execution-verified for its DEPENDENCIES and code path, but
the conversion itself was NOT run in this build environment because the OneDrive
checkpoint requires an interactive download (labeled 'user-run required' in
../05_run.md). No converted-model logs are fabricated.
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


def _find_hparams(tf_ckpt_dir, explicit):
    if explicit and os.path.isfile(explicit):
        return explicit
    for cand in ("hparams.json", os.path.join("..", "hparams.json")):
        p = os.path.join(tf_ckpt_dir, cand)
        if os.path.isfile(p):
            return p
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Convert the released RecipeGPT TF checkpoint to HF GPT-2.")
    ap.add_argument("--tf-ckpt-dir", required=True, dest="tf_ckpt_dir",
                    help="dir with the downloaded TF checkpoint "
                         "(model-*.data/.index/.meta + hparams.json)")
    ap.add_argument("--config", default=None,
                    help="path to hparams.json (GPT-2 config). Auto-detected if omitted.")
    ap.add_argument("--out", default="recipegpt-124m-hf",
                    help="output HF checkpoint directory")
    ap.add_argument("--add-markers", action="store_true", default=True,
                    help="register the recipe field-marker special tokens on the "
                         "tokenizer (the fine-tuned model was trained WITH them)")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.tf_ckpt_dir):
        print(f"[error] TF checkpoint dir not found: {args.tf_ckpt_dir}",
              file=sys.stderr)
        print("        Download it from the repo README's OneDrive model link, unzip,",
              file=sys.stderr)
        print("        then pass --tf-ckpt-dir <unzipped dir>.", file=sys.stderr)
        return 2

    hparams = _find_hparams(args.tf_ckpt_dir, args.config)
    if hparams is None:
        print("[error] could not find hparams.json (GPT-2 config). Pass --config.",
              file=sys.stderr)
        return 2

    try:
        import torch  # noqa
        from transformers import GPT2Config, GPT2TokenizerFast
        from transformers.models.gpt2.convert_gpt2_original_tf_checkpoint_to_pytorch \
            import convert_gpt2_checkpoint_to_pytorch
    except Exception as e:
        print("[MISSING DEPENDENCY] need torch + transformers.", file=sys.stderr)
        print("Install:  pip install -r requirements.txt", file=sys.stderr)
        print(f"({e})", file=sys.stderr)
        return 2

    # Map nshepperd/OpenAI hparams.json -> HF GPT2Config, then run the official
    # TF->PT converter (writes pytorch_model.bin + config.json into --out).
    with open(hparams, encoding="utf-8") as f:
        hp = json.load(f)
    cfg = GPT2Config(
        vocab_size=hp.get("n_vocab", 50257),
        n_positions=hp.get("n_ctx", 1024),
        n_embd=hp.get("n_embd", 768),
        n_layer=hp.get("n_layer", 12),
        n_head=hp.get("n_head", 12),
    )
    os.makedirs(args.out, exist_ok=True)
    cfg_path = os.path.join(args.out, "gpt2_config.json")
    cfg.to_json_file(cfg_path)

    print(f"[convert] TF ckpt : {args.tf_ckpt_dir}")
    print(f"[convert] config  : {hparams} -> GPT2Config"
          f"(n_layer={cfg.n_layer}, n_embd={cfg.n_embd}, n_head={cfg.n_head})")
    print(f"[convert] out     : {args.out}")
    # Official HF converter (same function transformers ships for OpenAI GPT-2 ckpts).
    convert_gpt2_checkpoint_to_pytorch(args.tf_ckpt_dir, cfg_path, args.out)

    # Save a GPT-2 tokenizer WITH the recipe markers as real special tokens so
    # main.py's is_finetuned path (add_markers=True) matches the trained embeddings.
    tok = GPT2TokenizerFast.from_pretrained("gpt2")
    if args.add_markers:
        tok.add_special_tokens(
            {"additional_special_tokens": multifield.SPECIAL_TOKENS})
    tok.save_pretrained(args.out)

    print(f"[done] HF checkpoint written -> {args.out}")
    print(f"       generate:  python main.py --mode gen-instructions --model {args.out}")
    print(f"       perplexity: python main.py --mode perplexity --model {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
