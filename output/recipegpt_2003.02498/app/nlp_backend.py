"""
nlp_backend.py — the HIGH-FIDELITY (real-NLP) path for RecipeGPT evaluation.

By default metrics.py uses lightweight, dependency-free STAND-INs:
  * root-noun extraction  -> a small rule-based lemmatizer  (STAND-IN for spaCy)
  * NTED node relabel cost -> token string similarity        (STAND-IN for word2vec)

This module replaces BOTH stand-ins with the REAL components the official repo
(github.com/LARC-CMU-SMU/RecipeGPT-exp) uses:

  * SpacyNouns  -> spaCy noun-chunk *root* lemmas (utils/spacy_func.py uses spaCy)
  * W2VCost     -> gensim Word2Vec cosine for the tree-edit relabel cost
                   (utils/tree.py update_cost = 1 - word2vec_cosine)

Turn it on with `python main.py --mode evaluate --real-nlp`. If spaCy / gensim
(or the spaCy model) are not installed, we print an honest notice and fall back
to the rule-based path — no fake "used spaCy" claims.

Install the real path:
    pip install spacy gensim
    python -m spacy download en_core_web_sm
"""

import re

_WORD = re.compile(r"[a-z]+")


def available():
    """Return (ok, reason). ok=True only if spaCy + its model + gensim import."""
    try:
        import spacy  # noqa
    except Exception as e:
        return False, f"spaCy not installed ({e}); `pip install spacy`"
    try:
        import gensim  # noqa
    except Exception as e:
        return False, f"gensim not installed ({e}); `pip install gensim`"
    try:
        spacy.load("en_core_web_sm")
    except Exception as e:
        return False, (f"spaCy model 'en_core_web_sm' missing ({e}); "
                       "`python -m spacy download en_core_web_sm`")
    return True, "spaCy + gensim + en_core_web_sm available"


class SpacyNouns:
    """
    REAL spaCy noun extraction (replaces metrics.py rule-based lemmatizer).

    * ingredient LINE  -> the lemma of the *root* token of its (last) noun chunk,
      i.e. the head noun. "1 cup pitted black olives" -> "olive".
    * free TEXT        -> lemmas of every noun-chunk root (all mentioned nouns).

    This mirrors utils/spacy_func.py, which parses with spaCy and keys on
    noun-chunk heads.
    """

    def __init__(self):
        import spacy
        # only tagger+parser+lemmatizer needed for noun chunks
        self.nlp = spacy.load("en_core_web_sm", disable=["ner"])

    def _chunk_heads(self, s):
        doc = self.nlp(s)
        return [ch.root.lemma_.lower() for ch in doc.noun_chunks
                if ch.root.lemma_.isalpha()]

    def ingredient_nouns(self, items):
        out = set()
        for item in items:
            heads = self._chunk_heads(str(item))
            if heads:
                out.add(heads[-1])          # head noun of the ingredient line
        return out

    def text_nouns(self, text):
        return set(self._chunk_heads(str(text)))

    def lemmatize(self, word):
        doc = self.nlp(str(word))
        return doc[0].lemma_.lower() if len(doc) else str(word).lower()


class W2VCost:
    """
    REAL gensim Word2Vec cosine for the NTED node relabel cost
    (replaces metrics._update_cost string similarity).

    cost(a, b) = 1 - max(0, cosine(vec_a, vec_b)), clamped to [0, 1].

    Vectors come from either:
      * a pretrained KeyedVectors file passed as `vectors_path`, OR
      * a gensim Word2Vec model TRAINED HERE on the supplied recipe corpus
        (the real CBOW/skip-gram algorithm, just on a small in-repo corpus).
    OOV tokens fall back to a character-set Jaccard so the metric never crashes.
    """

    def __init__(self, sentences=None, vectors_path=None, dim=64, epochs=40):
        from gensim.models import Word2Vec, KeyedVectors
        if vectors_path:
            self.kv = KeyedVectors.load(vectors_path, mmap="r")
            self.trained_on = f"pretrained:{vectors_path}"
        else:
            toks = [_WORD.findall(s.lower()) for s in (sentences or [])]
            toks = [t for t in toks if t]
            if not toks:                     # degenerate corpus -> tiny stub
                toks = [["recipe"]]
            self.model = Word2Vec(sentences=toks, vector_size=dim, window=5,
                                  min_count=1, workers=1, sg=1, epochs=epochs,
                                  seed=0)
            self.kv = self.model.wv
            self.trained_on = f"trained on {len(toks)} in-corpus sentences"

    def cost(self, a, b):
        if a == b:
            return 0.0
        ta = [w for w in _WORD.findall(a.lower()) if w in self.kv]
        tb = [w for w in _WORD.findall(b.lower()) if w in self.kv]
        if not ta or not tb:                 # OOV -> string-set fallback
            sa, sb = set(a), set(b)
            if not sa and not sb:
                return 0.0
            return 1.0 - len(sa & sb) / len(sa | sb)
        # average phrase vector cosine (n_similarity handles multi-token labels)
        try:
            sim = self.kv.n_similarity(ta, tb)
        except Exception:
            return 1.0
        return max(0.0, min(1.0, 1.0 - max(0.0, float(sim))))


def build(sentences=None, vectors_path=None):
    """
    Construct (SpacyNouns, W2VCost) if the real deps are present.
    Returns (nouns_backend, cost_backend, note). On failure returns
    (None, None, reason) so callers can fall back honestly.
    """
    ok, reason = available()
    if not ok:
        return None, None, reason
    nouns = SpacyNouns()
    cost = W2VCost(sentences=sentences, vectors_path=vectors_path)
    return nouns, cost, f"spaCy noun-chunks + gensim word2vec ({cost.trained_on})"


if __name__ == "__main__":
    ok, reason = available()
    print("real-NLP available:", ok, "-", reason)
    if ok:
        nb, cb, note = build(sentences=[
            "combine the olives garlic and capers into a paste",
            "blend olives with garlic and olive oil until smooth",
            "mix anchovy fillets with lemon juice",
        ])
        print("note:", note)
        print("ingredient heads:",
              nb.ingredient_nouns(["1 cup pitted black olives",
                                   "2 anchovy fillets", "3 tbsp olive oil"]))
        print("text nouns:", nb.text_nouns(
            "Combine the olives and garlic, then blend with olive oil."))
        print("w2v cost(olive,olives):", round(cb.cost("olive", "olives"), 3))
        print("w2v cost(blend,mix):", round(cb.cost("blend", "mix"), 3))
