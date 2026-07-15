"""
recipenlg.py — REAL recipe generation using a PUBLIC fine-tuned GPT-2.

The paper's own RecipeGPT (Recipe1M) fine-tuned checkpoint was released only as a
TensorFlow checkpoint on the authors' OneDrive (the official repo
LARC-CMU-SMU/RecipeGPT-exp README links a download under `training/gpt-2/models/`,
e.g. `model-633000`) — it is NOT directly HF-loadable, so this app can't load it as
a stand-alone HF model without conversion (see `convert_checkpoint.py`). To get
ACTUAL recipe-quality output out of the box — not the generic text base gpt2
produces — this adapter instead drives a publicly hosted GPT-2 already on HF that IS
fine-tuned on recipes:

    pratultandon/recipe-nlg-gpt2   (GPT-2 124M fine-tuned on RecipeNLG,
                                    a Recipe1M-derived corpus)

HONESTY: this is a DIFFERENT checkpoint than the paper's RecipeGPT — same
architecture (GPT-2 124M), same idea (special-token multi-field recipe
generation), different training corpus (RecipeNLG vs Recipe1M) and different
field-token scheme. It is a faithful, real, on-topic stand-in for the paper's
RecipeGPT weights, which are released only as a TensorFlow checkpoint on OneDrive
(not directly HF-loadable — see convert_checkpoint.py) — labeled as such.

This model's native format (from its model card):
  <RECIPE_START> <INPUT_START> ing1 <NEXT_INPUT> ing2 <INPUT_END>
  → model generates:
  <INGR_START> .. <NEXT_INGR> .. <INGR_END> <INSTR_START> .. <NEXT_INSTR> ..
  <INSTR_END> <TITLE_START> title <TITLE_END> <RECIPE_END>

`transformers`/`torch` are imported lazily.
"""

DEFAULT_MODEL = "pratultandon/recipe-nlg-gpt2"

_CACHE = {}


def _load(model_name):
    if model_name in _CACHE:
        return _CACHE[model_name]
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model.eval()
    _CACHE[model_name] = (tok, model)
    return tok, model


def build_prompt(ingredients):
    """RecipeNLG input format: the ingredients you want to use."""
    items = " <NEXT_INPUT> ".join(i.strip() for i in ingredients if i.strip())
    return f"<RECIPE_START> <INPUT_START> {items} <INPUT_END>"


def _between(text, start, end):
    if start not in text:
        return ""
    seg = text.split(start, 1)[1]
    if end in seg:
        seg = seg.split(end, 1)[0]
    return seg.strip()


def parse_recipe(text):
    """Parse the RecipeNLG token stream into title/ingredients/instructions."""
    title = _between(text, "<TITLE_START>", "<TITLE_END>")
    ingr_raw = _between(text, "<INGR_START>", "<INGR_END>")
    instr_raw = _between(text, "<INSTR_START>", "<INSTR_END>")
    ingredients = [x.strip() for x in ingr_raw.split("<NEXT_INGR>") if x.strip()]
    instructions = [x.strip() for x in instr_raw.split("<NEXT_INSTR>") if x.strip()]
    return {"title": title, "ingredients": ingredients, "instructions": instructions}


def generate(ingredients, model_name=DEFAULT_MODEL, seed=0,
             temperature=0.7, top_p=0.9, max_length=320):
    """Run REAL fine-tuned GPT-2 inference and return a parsed recipe."""
    import torch
    from transformers import set_seed
    set_seed(seed)
    tok, model = _load(model_name)
    prompt = build_prompt(ingredients)
    enc = tok(prompt, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(
            enc.input_ids, attention_mask=enc.attention_mask,
            max_length=max_length, do_sample=True,
            temperature=temperature, top_p=top_p,
            pad_token_id=tok.eos_token_id,
        )
    full = tok.decode(out[0], skip_special_tokens=False)
    recipe = parse_recipe(full)
    recipe["raw"] = full
    recipe["model"] = model_name
    recipe["prompt"] = prompt
    return recipe


if __name__ == "__main__":
    import json
    r = generate(["spaghetti", "garlic", "olive oil", "lemon", "parmesan"])
    print("MODEL:", r["model"])
    print("TITLE:", r["title"])
    print("INGREDIENTS:", json.dumps(r["ingredients"], ensure_ascii=False))
    print("INSTRUCTIONS:")
    for i, s in enumerate(r["instructions"], 1):
        print(f"  {i}. {s}")
