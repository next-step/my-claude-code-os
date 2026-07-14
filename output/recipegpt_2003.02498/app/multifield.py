"""
multifield.py — RecipeGPT multi-field I/O format.

Implements the special-token serialization used by RecipeGPT
(github.com/LARC-CMU-SMU/RecipeGPT-exp, data/recipe1M_example format):

    <start-title>...<end-title> <start-directions>...<end-directions> <start-ingredients>...<end-ingredients>

A recipe is a single token sequence with three fields, each wrapped by
start/end markers. Because the fine-tuned LM is trained on field-shuffled
sequences, *any* field can be the target: leaving one field's open-tag as the
last token turns the model into a conditional generator for that field. This
module builds those prompts (both directions) and parses generated text back
into structured fields.

Real algorithmic contribution of the paper (not a stand-in): the bidirectional
multi-field format itself. Field markers below are copied verbatim from the
official repo's example files.
"""

import re

# Field markers — verbatim from RecipeGPT-exp data/recipe1M_example/*.txt
T_START, T_END = "<start-title>", "<end-title>"
D_START, D_END = "<start-directions>", "<end-directions>"
I_START, I_END = "<start-ingredients>", "<end-ingredients>"

SPECIAL_TOKENS = [T_START, T_END, D_START, D_END, I_START, I_END]

# Ingredient item separator. The repo tokenizes each ingredient line separately
# (separator token id 3). We keep newline-separated ingredients and normalize.
INGR_SEP = "\n"


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def normalize_ingredients(ingredients):
    """Accept a list or a delimited string; return a clean list of items."""
    if isinstance(ingredients, str):
        parts = re.split(r"[\n;|]+", ingredients)
    else:
        parts = list(ingredients)
    return [_clean(p) for p in parts if _clean(p)]


def serialize(title, ingredients, instructions):
    """Serialize a full recipe into the single-sequence multi-field format."""
    ing = INGR_SEP.join(normalize_ingredients(ingredients))
    return (
        f"{T_START}{_clean(title)}{T_END} "
        f"{D_START}{_clean(instructions)}{D_END} "
        f"{I_START}{ing}{I_END}"
    )


def build_prompt(mode, title, ingredients=None, instructions=None):
    """
    Build a conditional-generation prompt (ends with the target field's OPEN tag).

    mode == "gen-instructions": condition on title + ingredients, generate directions.
    mode == "gen-ingredients":  condition on title + instructions, generate ingredients.
    """
    title = _clean(title)
    if mode == "gen-instructions":
        ing = INGR_SEP.join(normalize_ingredients(ingredients or []))
        # title, ingredients given -> open directions for the model to complete
        return (
            f"{T_START}{title}{T_END} "
            f"{I_START}{ing}{I_END} "
            f"{D_START}"
        ), D_END
    elif mode == "gen-ingredients":
        instr = _clean(instructions or "")
        return (
            f"{T_START}{title}{T_END} "
            f"{D_START}{instr}{D_END} "
            f"{I_START}"
        ), I_END
    else:
        raise ValueError(f"unknown mode: {mode}")


def parse(sequence):
    """Parse a (possibly partial) multi-field sequence into a dict of fields."""
    out = {"title": None, "ingredients": [], "instructions": None}

    def grab(start, end, clean=True):
        m = re.search(re.escape(start) + r"(.*?)(?:" + re.escape(end) + r"|$)",
                      sequence, re.DOTALL)
        if not m:
            return None
        return _clean(m.group(1)) if clean else m.group(1)

    out["title"] = grab(T_START, T_END)
    out["instructions"] = grab(D_START, D_END)
    ing = grab(I_START, I_END, clean=False)  # keep newlines to split items
    if ing:
        out["ingredients"] = normalize_ingredients(ing)
    return out


def clean_generated(gen_text, end_marker):
    """
    Post-process ONLY the newly generated continuation (already prompt-stripped
    at the token level). Stop at the field end marker or any next special tag,
    mirroring the repo's `text.split('<')[0]` post-processing.
    """
    tail = gen_text
    cut = tail.find(end_marker)
    if cut != -1:
        tail = tail[:cut]
    cut2 = tail.find("<")
    if cut2 != -1:
        tail = tail[:cut2]
    # normalize special-token artefacts and whitespace
    tail = tail.replace("<|endoftext|>", " ")
    return _clean(tail)


def extract_generated_field(full_text, prompt, end_marker):
    """
    Given the model's full decoded text and the prompt used, return only the
    newly generated field content (stops at end_marker or next start-tag).

    Mirrors the repo post-processing: text after prompt, cut at first '<'.
    """
    tail = full_text[len(prompt):] if full_text.startswith(prompt) else full_text
    # Stop at the field's end marker or any next special tag.
    cut = tail.find(end_marker)
    if cut != -1:
        tail = tail[:cut]
    cut2 = tail.find("<")
    if cut2 != -1:
        tail = tail[:cut2]
    return _clean(tail)


if __name__ == "__main__":
    seq = serialize(
        "tapenade",
        ["1 cup black olives", "2 anchovy fillets", "1 clove garlic"],
        "Place the anchovies in a small shallow bowl. Combine all ingredients.",
    )
    print("SERIALIZED:\n", seq, "\n")
    print("PARSED:\n", parse(seq), "\n")
    p, end = build_prompt("gen-instructions", "tapenade",
                          ingredients=["black olives", "anchovy", "garlic"])
    print("INSTR-PROMPT:\n", p, "| end=", end)
