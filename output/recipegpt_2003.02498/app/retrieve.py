"""
retrieve.py — nearest-neighbor similar-recipe retrieval (paper §4, evaluation UI).

RecipeGPT's system has TWO pillars: (1) bidirectional generation and (2) an
*evaluation module* that, alongside the metrics, shows the user the most similar
existing recipes so they can judge novelty/quality. In the paper that retrieval is
served by an **ElasticSearch index over the full 904k Recipe1M corpus** (paper §4,
"similar recipes" panel). We cannot ship that index here, so this is a labeled
SMALL-CORPUS STAND-IN: the exact same idea (rank a corpus by textual similarity to
a query recipe) implemented with classic IR scorers over the bundled sample recipes.

REAL here (deterministic, pure standard library — no deps):
  * TF-IDF vector-space cosine similarity (ElasticSearch's default is a TF-IDF/
    BM25 family scorer — this is the same principle).
  * Okapi BM25 (k1=1.5, b=0.75) — the scorer ElasticSearch actually uses since v5.
STAND-IN (labeled): the CORPUS is the tiny bundled sample set, not Recipe1M, and
there is no ElasticSearch server — the ranking math is real, the index scale is not.

Query = a recipe's ingredient list (and/or title). Documents = bundled recipes
serialized to text. Returns ranked (score, recipe) pairs.
"""

import json
import math
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "data", "sample_recipes.json")

_WORD = re.compile(r"[a-z0-9]+")

# minimal stopwords so measure words don't dominate the similarity
_STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "with", "for",
         "cup", "cups", "tablespoon", "tablespoons", "tbsp", "teaspoon",
         "teaspoons", "tsp", "ounce", "ounces", "pound", "pounds", "clove",
         "cloves", "large", "small", "medium"}


def _tokens(text):
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP and len(t) > 1]


def _doc_text(recipe):
    """Serialize a recipe to a bag-of-words document (title + ingredients + steps)."""
    parts = [recipe.get("title", "")]
    parts += [str(x) for x in recipe.get("ingredients", [])]
    parts.append(recipe.get("instructions", "") or "")
    return " ".join(parts)


def load_corpus(path=None):
    with open(path or SAMPLES, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# TF-IDF vector-space cosine similarity
# ---------------------------------------------------------------------------

def _build_idf(doc_tokens):
    N = len(doc_tokens)
    df = Counter()
    for toks in doc_tokens:
        for t in set(toks):
            df[t] += 1
    # smoothed idf
    return {t: math.log((N + 1) / (df_t + 1)) + 1.0 for t, df_t in df.items()}


def _tfidf_vec(tokens, idf):
    tf = Counter(tokens)
    vec = {t: (c / len(tokens)) * idf.get(t, 0.0) for t, c in tf.items()} if tokens else {}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def _cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def tfidf_rank(query_text, corpus):
    doc_tokens = [_tokens(_doc_text(r)) for r in corpus]
    idf = _build_idf(doc_tokens)
    q = _tfidf_vec(_tokens(query_text), idf)
    docs = [_tfidf_vec(toks, idf) for toks in doc_tokens]
    scored = [(_cosine(q, d), corpus[i]) for i, d in enumerate(docs)]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Okapi BM25 (the scorer ElasticSearch uses by default since v5)
# ---------------------------------------------------------------------------

def bm25_rank(query_text, corpus, k1=1.5, b=0.75):
    doc_tokens = [_tokens(_doc_text(r)) for r in corpus]
    N = len(doc_tokens)
    avgdl = sum(len(d) for d in doc_tokens) / N if N else 0.0
    df = Counter()
    for toks in doc_tokens:
        for t in set(toks):
            df[t] += 1
    idf = {t: math.log((N - n + 0.5) / (n + 0.5) + 1.0) for t, n in df.items()}
    q_terms = _tokens(query_text)
    scored = []
    for i, toks in enumerate(doc_tokens):
        tf = Counter(toks)
        dl = len(toks)
        s = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            f = tf[term]
            denom = f + k1 * (1 - b + b * dl / (avgdl or 1.0))
            s += idf.get(term, 0.0) * (f * (k1 + 1)) / denom
        scored.append((s, corpus[i]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def retrieve(query_text, corpus=None, method="bm25", top_k=3):
    corpus = corpus if corpus is not None else load_corpus()
    ranker = bm25_rank if method == "bm25" else tfidf_rank
    ranked = ranker(query_text, corpus)
    return ranked[:top_k]


if __name__ == "__main__":
    corpus = load_corpus()
    q = "black olives anchovy garlic capers olive oil lemon"
    print("QUERY:", q)
    for score, r in retrieve(q, corpus, method="bm25", top_k=3):
        print(f"  BM25={score:.4f}  {r['title']}")
    for score, r in retrieve(q, corpus, method="tfidf", top_k=3):
        print(f"  TFIDF={score:.4f}  {r['title']}")
