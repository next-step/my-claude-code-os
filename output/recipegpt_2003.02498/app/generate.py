"""
generate.py — REAL GPT-2 autoregressive inference for RecipeGPT.

Uses HuggingFace `transformers` to run an actual GPT-2 neural forward pass on CPU
(or GPU if available). The multi-field prompt (multifield.build_prompt) conditions
the model, and the target field is sampled autoregressively.

Decoding settings and their provenance (checked against the official repo):
  * temperature = 1.0   -> repo `conditional_gen_web.py` code default (verbatim).
  * top_k       = 0     -> repo `conditional_gen_web.py` code default (verbatim).
  * top_p       = 0.9   -> a CHOSEN nucleus value. NOTE: the repo's literal code
    default is top_p=0.0 (nucleus sampling OFF); 0.9 is the value RECOMMENDED in
    the repo notes / 04_code.md ("top_p 권장 0.9"), not the source-file default.
    Pass `--top-p 0.0` to match conditional_gen_web.py's default byte-for-byte.

Model selection:
  * --model gpt2 (default): the ORIGINAL, NON-fine-tuned GPT-2 124M. This is REAL
    neural inference but the weights are NOT the RecipeGPT fine-tuned checkpoint
    (which the authors released only as a TensorFlow checkpoint on OneDrive, not
    directly HF-loadable — see convert_checkpoint.py). Output is labeled STAND-IN
    WEIGHTS: the *pipeline, format, and decoding* are faithful; only the trained
    recipe weights are missing. To get on-topic recipes, fine-tune gpt2 on
    Recipe1M in this exact format, or point --model at a fine-tuned checkpoint
    (local dir or HF id) if you have one.

`transformers`/`torch` are imported lazily so metrics.py / evaluate mode run
without them installed.
"""

import multifield

# Decoding settings. temperature/top_k are the repo's literal conditional_gen_web.py
# code defaults. top_p=0.9 is a CHOSEN/RECOMMENDED nucleus value, NOT the repo's
# code default (which is top_p=0.0, nucleus off). See module docstring.
DEFAULTS = dict(temperature=1.0, top_p=0.9, top_k=0, max_new_tokens=256)
# Byte-for-byte repo default (nucleus off) — use via --top-p 0.0.
REPO_CODE_DEFAULT_TOP_P = 0.0

BASE_MODELS = {"gpt2", "gpt2-medium", "gpt2-large", "gpt2-xl", "distilgpt2"}

_CACHE = {}


def _load(model_name, add_markers):
    """
    Load tokenizer+model once.

    add_markers=True  -> register the recipe field markers as special tokens and
        resize embeddings. Use ONLY for a fine-tuned RecipeGPT checkpoint whose
        weights were trained with these tokens (repo: encoder.py adds them).
    add_markers=False -> keep the markers as ordinary text that the BPE tokenizer
        splits normally. REQUIRED for base gpt2: newly-added special tokens get
        random embeddings, which makes an untrained model emit only markers.
    """
    key = (model_name, add_markers)
    if key in _CACHE:
        return _CACHE[key]
    import torch  # noqa
    from transformers import GPT2LMHeadModel, GPT2TokenizerFast

    tok = GPT2TokenizerFast.from_pretrained(model_name)
    if add_markers:
        tok.add_special_tokens(
            {"additional_special_tokens": multifield.SPECIAL_TOKENS}
        )
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = GPT2LMHeadModel.from_pretrained(model_name)
    if add_markers:
        model.resize_token_embeddings(len(tok))
    model.eval()
    _CACHE[key] = (tok, model)
    return tok, model


def generate_field(mode, title, ingredients=None, instructions=None,
                   model_name="gpt2", seed=0, **kw):
    """
    Run real GPT-2 inference to generate the missing field.

    Returns dict: {prompt, generated, full_text, model, is_finetuned}.
    """
    import torch
    from transformers import set_seed

    params = dict(DEFAULTS)
    params.update({k: v for k, v in kw.items() if v is not None})
    set_seed(seed)

    is_ft = model_name.lower() not in BASE_MODELS
    add_markers = is_ft  # only a fine-tuned model knows the marker tokens
    tok, model = _load(model_name, add_markers)
    prompt, end_marker = multifield.build_prompt(
        mode, title, ingredients=ingredients, instructions=instructions
    )
    enc = tok(prompt, return_tensors="pt")
    input_ids = enc.input_ids
    attn = enc.attention_mask
    n_prompt = input_ids.shape[1]

    # Early-stop on the field end marker only when it is a real single token
    # (fine-tuned model). For base gpt2 the marker is multi-token text, so we
    # rely on max_new_tokens + clean_generated cutting at the next '<'.
    eos_ids = [tok.eos_token_id]
    if add_markers:
        end_id = tok.convert_tokens_to_ids(end_marker)
        if isinstance(end_id, int) and end_id != tok.unk_token_id:
            eos_ids.append(end_id)

    with torch.no_grad():
        out = model.generate(
            input_ids,
            attention_mask=attn,
            do_sample=True,
            temperature=params["temperature"],
            top_p=params["top_p"],
            top_k=(params["top_k"] if params["top_k"] and params["top_k"] > 0 else 0),
            max_new_tokens=params["max_new_tokens"],
            pad_token_id=tok.pad_token_id,
            eos_token_id=eos_ids,
        )
    # Decode ONLY the newly generated tokens (robust to prompt re-spacing).
    new_ids = out[0][n_prompt:]
    gen_text = tok.decode(new_ids, skip_special_tokens=False)
    generated = multifield.clean_generated(gen_text, end_marker)
    full = tok.decode(out[0], skip_special_tokens=False)

    return {"prompt": prompt, "generated": generated, "full_text": full,
            "model": model_name, "is_finetuned": is_ft, "params": params}


def perplexity(texts, model_name="gpt2", block_size=512):
    """
    Compute REAL token-level perplexity of a (base or fine-tuned) GPT-2 over a
    list of texts, using the standard causal-LM cross-entropy:

        PPL = exp( mean_token( -log p(token | context) ) )

    This is the live companion to the paper's reported PPL=3.70 (paper §6, Table).
    Honesty: with base `gpt2` (STAND-IN weights) on recipe text the PPL is far
    higher than 3.70 — 3.70 is only reachable with the paper's Recipe1M fine-tuned
    weights (convert_checkpoint.py) or your own finetune.py checkpoint. The NUMBER
    printed is genuinely computed from the model's logits, never hardcoded.

    Returns dict: {ppl, mean_nll, n_tokens, model, is_finetuned, per_text}.
    """
    import math
    import torch

    is_ft = model_name.lower() not in BASE_MODELS
    add_markers = is_ft
    tok, model = _load(model_name, add_markers)

    total_nll = 0.0
    total_tokens = 0
    per_text = []
    loss_fct = torch.nn.CrossEntropyLoss(reduction="sum")
    for t in texts:
        enc = tok(t, return_tensors="pt", truncation=True, max_length=block_size)
        ids = enc.input_ids
        if ids.shape[1] < 2:
            continue
        with torch.no_grad():
            logits = model(ids, attention_mask=enc.attention_mask).logits
        # shift: predict token[i+1] from context up to i
        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = ids[:, 1:].contiguous()
        nll = loss_fct(shift_logits.view(-1, shift_logits.size(-1)),
                       shift_labels.view(-1)).item()
        n = shift_labels.numel()
        total_nll += nll
        total_tokens += n
        per_text.append({"ppl": math.exp(nll / n), "n_tokens": n})
    mean_nll = total_nll / total_tokens if total_tokens else float("nan")
    return {"ppl": math.exp(mean_nll) if total_tokens else float("nan"),
            "mean_nll": mean_nll, "n_tokens": total_tokens,
            "model": model_name, "is_finetuned": is_ft, "per_text": per_text}


if __name__ == "__main__":
    r = generate_field(
        "gen-instructions", "tapenade",
        ingredients=["black olives", "anchovy fillets", "garlic", "capers", "olive oil"],
    )
    print("MODEL:", r["model"], "| finetuned:", r["is_finetuned"])
    print("PROMPT:", r["prompt"])
    print("GENERATED:", r["generated"])
