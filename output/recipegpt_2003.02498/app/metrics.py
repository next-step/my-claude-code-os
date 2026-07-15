"""
metrics.py — RecipeGPT evaluation module (the paper's real, deterministic core).

Faithful pure-Python reimplementations of the metrics in
github.com/LARC-CMU-SMU/RecipeGPT-exp (utils/metrics.py, utils/tree.py,
utils/evaluation.py, analysis/multi-bleu.perl):

  * ingredient_f1  — set-based precision/recall/F1 over root nouns (utils/metrics.py).
                     Supports F1@k (truncate predicted ingredient set to top-k).
  * bleu           — Moses multi-bleu style corpus BLEU (up to 4-gram) + brevity penalty.
  * rouge_l        — LCS-based ROUGE-L F-measure.
  * nted           — Normalized Tree Edit Distance: parse instructions into a
                     vertical action-spine tree (each action the leftmost child of
                     the previous, ingredient leaves attached), matching repo
                     utils/tree.py build_tree, run Zhang-Shasha tree edit distance,
                     normalize by (nodes_a + nodes_b) (utils/evaluation.py).
  * jaccard_consistency — root-noun overlap between generated instructions and
                     input ingredients (paper's field-consistency Jaccard).
  * highlight_overlap — root-noun ingredient highlighting (utils/spacy_func.py).

STAND-IN (clearly labeled where used):
  * root-noun extraction uses a lightweight rule-based lemmatizer instead of spaCy.
  * NTED node update-cost uses a token-level string similarity instead of the
    repo's word2vec cosine. The tree structure + Zhang-Shasha algorithm are REAL.
Everything else is a faithful, exact reimplementation.
"""

import math
import re
from collections import Counter

# ---------------------------------------------------------------------------
# Tokenization + lightweight lemmatizer (STAND-IN for spaCy)
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z]+")

# Common cooking measure / filler words that are not ingredients (root nouns).
_STOP = {
    "cup", "cups", "tablespoon", "tablespoons", "tbsp", "teaspoon", "teaspoons",
    "tsp", "ounce", "ounces", "oz", "pound", "pounds", "lb", "lbs", "gram",
    "grams", "g", "kg", "ml", "l", "pinch", "dash", "clove", "cloves", "slice",
    "slices", "can", "cans", "package", "packages", "pkg", "jar", "bunch",
    "handful", "piece", "pieces", "large", "small", "medium", "fresh", "dried",
    "chopped", "minced", "diced", "sliced", "grated", "ground", "whole",
    "boneless", "skinless", "ripe", "raw", "cooked", "hot", "cold", "warm",
    "and", "or", "of", "to", "the", "a", "an", "with", "for", "into", "in",
    "on", "at", "cut", "peeled", "optional", "taste", "extra", "virgin",
    "all", "purpose", "unsalted", "softened", "melted", "beaten", "warmed",
}

_IRREGULAR = {
    "leaves": "leaf", "loaves": "loaf", "potatoes": "potato",
    "tomatoes": "tomato", "berries": "berry", "cherries": "cherry",
    "chilies": "chili", "chillies": "chili",
}

# ---------------------------------------------------------------------------
# Optional HIGH-FIDELITY backend (real spaCy noun-chunks + gensim word2vec).
# Injected by main.py --real-nlp via set_nlp_backend(); None => rule-based STAND-IN.
# ---------------------------------------------------------------------------
_NOUNS_BACKEND = None   # object with .ingredient_nouns / .text_nouns / .lemmatize
_COST_BACKEND = None    # object with .cost(label_a, label_b)


def set_nlp_backend(nouns_backend=None, cost_backend=None):
    """Enable the real-NLP path. Pass None,None to revert to the stand-ins."""
    global _NOUNS_BACKEND, _COST_BACKEND
    _NOUNS_BACKEND = nouns_backend
    _COST_BACKEND = cost_backend


def using_real_nlp():
    return _NOUNS_BACKEND is not None or _COST_BACKEND is not None


def lemmatize(word: str) -> str:
    """Very small rule-based lemmatizer (STAND-IN for spaCy lemmatization)."""
    w = word.lower()
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ses") or w.endswith("shes") or w.endswith("ches"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _content_tokens(s):
    """All lemmatized content tokens of a string (stopwords/measures removed)."""
    return [lemmatize(t) for t in _WORD.findall(s.lower())
            if lemmatize(t) not in _STOP and len(lemmatize(t)) > 2]


def ingredient_nouns(items):
    """
    Root noun per ingredient LINE (head-noun heuristic: last content token).
    STAND-IN for utils/spacy_func.py (spaCy noun-chunk head + lemmatize).
    e.g. "1 cup pitted black olives" -> "olive".
    Uses the REAL spaCy backend instead when --real-nlp is active.
    """
    if _NOUNS_BACKEND is not None:
        return _NOUNS_BACKEND.ingredient_nouns(list(items))
    nouns = set()
    for item in items:
        content = _content_tokens(item)
        if content:
            nouns.add(content[-1])
    return nouns


def text_nouns(text):
    """
    All root nouns mentioned in FREE TEXT (e.g. instructions): every content
    token, lemmatized, stopwords removed. STAND-IN for spaCy noun extraction.
    Uses the REAL spaCy noun-chunk backend instead when --real-nlp is active.
    """
    if _NOUNS_BACKEND is not None:
        return _NOUNS_BACKEND.text_nouns(text)
    return set(_content_tokens(text))


def root_nouns(text):
    """
    Dispatch: a list/tuple is an ingredient list (head noun per line); a plain
    string is free text (all nouns). This matches how the repo treats the
    ingredient field (line-structured) vs the directions field (prose).
    """
    if isinstance(text, (list, tuple)):
        return ingredient_nouns(text)
    return text_nouns(text)


# ---------------------------------------------------------------------------
# Ingredient F1 (utils/metrics.py) — set precision/recall/f1, with F1@k
# ---------------------------------------------------------------------------

def split_ingredient_items(text):
    """
    Split a generated ingredient field into individual items (for counting the
    avg number of generated ingredients, paper avg = 7.8). Accepts a list or a
    string delimited by newlines / ';' / ',' / '|'.
    """
    if isinstance(text, (list, tuple)):
        return [str(i).strip() for i in text if str(i).strip()]
    return [p.strip() for p in re.split(r"[\n;,|]+", text or "") if p.strip()]


def ingredient_f1(pred, ref, k=None):
    """
    Set-based precision/recall/F1 over ingredient root nouns.
    pred, ref: list or string of ingredients. k: optional top-k truncation of
    predicted ingredients (F1@k). Returns dict.
    """
    def _as_items(x):
        if isinstance(x, (list, tuple)):
            return [str(i) for i in x]
        return [p for p in re.split(r"[\n;,|]+", x) if p.strip()]

    pred_items = _as_items(pred)
    ref_items = _as_items(ref)
    if k is not None:
        pred_items = pred_items[:k]
    P = ingredient_nouns(pred_items)
    R = ingredient_nouns(ref_items)
    if not P and not R:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0,
                "n_pred": 0, "n_ref": 0, "k": k}
    inter = len(P & R)
    precision = inter / len(P) if P else 0.0
    recall = inter / len(R) if R else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {"precision": precision, "recall": recall, "f1": f1,
            "n_pred": len(P), "n_ref": len(R), "k": k}


# ---------------------------------------------------------------------------
# BLEU (Moses multi-bleu.perl style) + brevity penalty
# ---------------------------------------------------------------------------

def _tokens(s):
    return _WORD.findall(s.lower()) if isinstance(s, str) else \
        _WORD.findall(" ".join(s).lower())


def _ngrams(tokens, n):
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def bleu(hypotheses, references, max_n=4):
    """
    Corpus BLEU with uniform n-gram weights and standard brevity penalty,
    matching Moses multi-bleu.perl (used by analysis/09-model-performances.ipynb).
    Returns BLEU on a 0-100 scale (paper reports 8.34) plus components.

    hypotheses, references: list of strings (parallel) OR single strings.
    """
    if isinstance(hypotheses, str):
        hypotheses = [hypotheses]
    if isinstance(references, str):
        references = [references]
    clipped = [0] * max_n
    total = [0] * max_n
    hyp_len = ref_len = 0
    for hyp, ref in zip(hypotheses, references):
        h = _tokens(hyp)
        r = _tokens(ref)
        hyp_len += len(h)
        ref_len += len(r)
        for n in range(1, max_n + 1):
            h_ng = _ngrams(h, n)
            r_ng = _ngrams(r, n)
            for ng, c in h_ng.items():
                clipped[n - 1] += min(c, r_ng.get(ng, 0))
                total[n - 1] += c
    precisions = []
    for n in range(max_n):
        precisions.append(clipped[n] / total[n] if total[n] else 0.0)
    if min(precisions) > 0:
        log_avg = sum((1.0 / max_n) * math.log(p) for p in precisions)
        geo_mean = math.exp(log_avg)
    else:
        geo_mean = 0.0
    if hyp_len == 0:
        bp = 0.0
    elif hyp_len > ref_len:
        bp = 1.0
    else:
        bp = math.exp(1 - ref_len / hyp_len)
    score = bp * geo_mean * 100.0
    return {"bleu": score, "brevity_penalty": bp,
            "precisions": precisions, "hyp_len": hyp_len, "ref_len": ref_len}


# ---------------------------------------------------------------------------
# ROUGE-L (LCS-based F-measure)
# ---------------------------------------------------------------------------

def _lcs_len(a, b):
    m, n = len(a), len(b)
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        ai = a[i - 1]
        for j in range(1, n + 1):
            tmp = dp[j]
            if ai == b[j - 1]:
                dp[j] = prev + 1
            elif dp[j - 1] > dp[j]:
                dp[j] = dp[j - 1]
            prev = tmp
    return dp[n]


def rouge_l(hypothesis, reference, beta=1.2):
    """LCS-based ROUGE-L F-measure (paper reports 0.36)."""
    h = _tokens(hypothesis)
    r = _tokens(reference)
    if not h or not r:
        return {"rouge_l": 0.0, "precision": 0.0, "recall": 0.0}
    lcs = _lcs_len(h, r)
    prec = lcs / len(h)
    rec = lcs / len(r)
    if prec + rec == 0:
        f = 0.0
    else:
        f = ((1 + beta ** 2) * prec * rec) / (rec + beta ** 2 * prec)
    return {"rouge_l": f, "precision": prec, "recall": rec, "lcs": lcs}


# ---------------------------------------------------------------------------
# NTED — instruction tree + Zhang-Shasha edit distance (utils/tree.py)
# ---------------------------------------------------------------------------

class Node:
    __slots__ = ("label", "children")

    def __init__(self, label, children=None):
        self.label = label
        self.children = children or []


def instr_tree(instructions):
    """
    Parse instructions into a tree, matching repo utils/tree.py build_tree:
    action nodes form a VERTICAL SPINE (each subsequent action is inserted as
    the LEFTMOST child of the previous action, repo `addkid(..., before=True)`),
    with that action's ingredient/noun leaves as the remaining children. The
    FIRST action node is the tree root (there is no synthetic ROOT node).

        action_0
        ├─ action_1
        │  ├─ action_2
        │  │  └─ (leaves of action_2)
        │  └─ (leaves of action_1)
        └─ (leaves of action_0)

    Action node label = first verb-like token (lemmatized) of the step.
    Leaves = root nouns mentioned in the step.
    STAND-IN for spaCy dependency parse; TOPOLOGY now matches repo build_tree
    (the previous flat siblings-under-ROOT form deviated from the repo).
    """
    steps = [s for s in re.split(r"[.;\n]+", instructions) if s.strip()]
    parsed = []
    for step in steps:
        toks = _WORD.findall(step.lower())
        if not toks:
            continue
        # imperative verb heads a cooking step (real spaCy lemma when --real-nlp)
        action = (_NOUNS_BACKEND.lemmatize(toks[0])
                  if _NOUNS_BACKEND is not None else lemmatize(toks[0]))
        nouns = root_nouns(step)
        leaves = [Node(n) for n in sorted(nouns)]
        parsed.append((action, leaves))
    if not parsed:
        return Node("ROOT")
    # First action = root; chain the rest vertically as leftmost children
    # (repo build_tree: myroot.addkid(next_action, before=True); descend).
    action0, leaves0 = parsed[0]
    root = Node(action0, list(leaves0))
    cur = root
    for action, leaves in parsed[1:]:
        nxt = Node(action, list(leaves))
        cur.children.insert(0, nxt)   # before=True -> leftmost child (action spine)
        cur = nxt
    return root


def _count_nodes(node):
    return 1 + sum(_count_nodes(c) for c in node.children)


def _update_cost(a, b):
    """
    Node relabel cost for the tree-edit distance (utils/tree.py update_cost).
    Repo uses 1 - word2vec_cosine. When --real-nlp is active we call the REAL
    gensim word2vec backend; otherwise a token-level string-similarity STAND-IN
    (0 identical, up to 1 fully different).
    """
    if a == b:
        return 0.0
    if _COST_BACKEND is not None:
        return _COST_BACKEND.cost(a, b)
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    jacc = len(sa & sb) / len(sa | sb)
    return 1.0 - jacc


def _postorder(node, nodes, ids):
    for c in node.children:
        _postorder(c, nodes, ids)
    ids[id(node)] = len(nodes)
    nodes.append(node)


def zhang_shasha(t1, t2):
    """
    Ordered-tree edit distance (Zhang & Shasha 1989), the algorithm used by the
    `zss` library that the repo calls. insert/delete cost = 1, relabel via
    _update_cost. Returns total edit distance.
    """
    def prep(tree):
        nodes, idmap = [], {}
        _postorder(tree, nodes, idmap)
        n = len(nodes)
        # leftmost leaf descendant (postorder index) for each node
        lmld = [0] * n
        parent = [-1] * n
        for node in nodes:
            for c in node.children:
                parent[idmap[id(c)]] = idmap[id(node)]
        for i, node in enumerate(nodes):
            if not node.children:
                lmld[i] = i
            else:
                lmld[i] = lmld[idmap[id(node.children[0])]]
        # keyroots
        seen = {}
        keyroots = []
        for i in range(n - 1, -1, -1):
            if lmld[i] not in seen:
                seen[lmld[i]] = i
                keyroots.append(i)
        keyroots.sort()
        return nodes, lmld, keyroots

    n1, l1, kr1 = prep(t1)
    n2, l2, kr2 = prep(t2)
    N, M = len(n1), len(n2)
    INF = float("inf")
    treedist = [[0.0] * M for _ in range(N)]

    for ki in kr1:
        for kj in kr2:
            fi = l1[ki]
            fj = l2[kj]
            m = ki - fi + 2
            n = kj - fj + 2
            fd = [[0.0] * n for _ in range(m)]
            for i in range(1, m):
                fd[i][0] = fd[i - 1][0] + 1  # delete
            for j in range(1, n):
                fd[0][j] = fd[0][j - 1] + 1  # insert
            for i in range(1, m):
                for j in range(1, n):
                    ai = fi + i - 1
                    bj = fj + j - 1
                    if l1[ai] == fi and l2[bj] == fj:
                        cost = _update_cost(n1[ai].label, n2[bj].label)
                        fd[i][j] = min(fd[i - 1][j] + 1,
                                       fd[i][j - 1] + 1,
                                       fd[i - 1][j - 1] + cost)
                        treedist[ai][bj] = fd[i][j]
                    else:
                        p = l1[ai] - fi
                        q = l2[bj] - fj
                        fd[i][j] = min(fd[i - 1][j] + 1,
                                       fd[i][j - 1] + 1,
                                       fd[p][q] + treedist[ai][bj])
    return treedist[N - 1][M - 1]


def nted(instr_a, instr_b):
    """
    Normalized Tree Edit Distance (paper reports 0.52).
    NTED = ZS(tree_a, tree_b) / (nodes_a + nodes_b)   (utils/evaluation.py norm_dist)
    """
    ta = instr_tree(instr_a)
    tb = instr_tree(instr_b)
    d = zhang_shasha(ta, tb)
    denom = _count_nodes(ta) + _count_nodes(tb)
    return {"nted": d / denom if denom else 0.0, "edit_distance": d,
            "nodes_a": _count_nodes(ta), "nodes_b": _count_nodes(tb)}


# ---------------------------------------------------------------------------
# Jaccard field-consistency + ingredient highlight (utils/spacy_func.py)
# ---------------------------------------------------------------------------

def jaccard_consistency(instructions, ingredients):
    """
    Field-consistency Jaccard: root nouns mentioned in the (generated) directions
    vs the input ingredient set (paper: generated 0.53 vs human 0.49).
    """
    instr_nouns = root_nouns(instructions)
    ingr_nouns = root_nouns(ingredients)
    if not instr_nouns and not ingr_nouns:
        return {"jaccard": 1.0, "shared": [], "n_instr": 0, "n_ingr": 0}
    inter = instr_nouns & ingr_nouns
    union = instr_nouns | ingr_nouns
    return {"jaccard": len(inter) / len(union) if union else 0.0,
            "shared": sorted(inter), "n_instr": len(instr_nouns),
            "n_ingr": len(ingr_nouns)}


def highlight_overlap(instructions, ingredients):
    """
    Ingredient-overlap highlighting (utils/spacy_func.py ingr()/instr()):
    return the input ingredient root nouns that also appear in the directions.
    """
    ingr_nouns = root_nouns(ingredients)
    instr_nouns = root_nouns(instructions)
    used = sorted(ingr_nouns & instr_nouns)
    missing = sorted(ingr_nouns - instr_nouns)
    return {"used": used, "missing": missing,
            "coverage": len(used) / len(ingr_nouns) if ingr_nouns else 0.0}


if __name__ == "__main__":
    pred = ["olives", "anchovies", "garlic", "capers", "olive oil"]
    ref = ["black olives", "anchovy fillets", "garlic cloves", "capers", "lemon juice"]
    print("F1:", ingredient_f1(pred, ref))
    print("F1@3:", ingredient_f1(pred, ref, k=3))
    a = "Combine the olives and garlic. Blend with olive oil until smooth."
    b = "Mix olives with garlic. Process adding oil until smooth."
    print("BLEU:", bleu(a, b))
    print("ROUGE-L:", rouge_l(a, b))
    print("NTED:", nted(a, b))
    print("Jaccard:", jaccard_consistency(a, ref))
    print("Highlight:", highlight_overlap(a, ref))
