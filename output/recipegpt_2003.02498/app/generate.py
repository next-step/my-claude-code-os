"""
generate.py — REAL GPT-2 autoregressive inference for RecipeGPT.

Uses HuggingFace `transformers` to run an actual GPT-2 neural forward pass on CPU
(or GPU if available). The multi-field prompt (multifield.build_prompt) conditions
the model, and the target field is sampled autoregressively with the paper's
decoding settings (temperature=1.0, top_p=0.9, top_k=0 — from
conditional_gen_web.py).

Model selection:
  * --model gpt2 (default): the ORIGINAL, NON-fine-tuned GPT-2 124M. This is REAL
    neural inference but the weights are NOT the RecipeGPT fine-tuned checkpoint
    (which the authors did not publicly release). Output is labeled STAND-IN
    WEIGHTS: the *pipeline, format, and decoding* are faithful; only the trained
    recipe weights are missing. To get on-topic recipes, fine-tune gpt2 on
    Recipe1M in this exact format, or point --model at a fine-tuned checkpoint
    (local dir or HF id) if you have one.

`transformers`/`torch` are imported lazily so metrics.py / evaluate mode run
without them installed.
"""

import multifield

# Decoding defaults from conditional_gen_web.py
DEFAULTS = dict(temperature=1.0, top_p=0.9, top_k=0, max_new_tokens=256)

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


if __name__ == "__main__":
    r = generate_field(
        "gen-instructions", "tapenade",
        ingredients=["black olives", "anchovy fillets", "garlic", "capers", "olive oil"],
    )
    print("MODEL:", r["model"], "| finetuned:", r["is_finetuned"])
    print("PROMPT:", r["prompt"])
    print("GENERATED:", r["generated"])
