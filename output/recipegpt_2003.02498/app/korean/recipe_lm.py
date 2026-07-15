"""
recipe_lm.py — a Korean recipe language model built FROM SCRATCH.

NO pretrained GPT-2 / KoGPT2. This is a character-level LSTM defined and trained
here, on the Korean recipe corpus (KoreanRecipeGPT data), from random init.

Field format in the corpus (one recipe per line), our OWN markers:
  <n>음식명</n><i>재료$재료$...</i><r>조리법</r>

Data is our own hand-written Korean recipe corpus (data/ko_recipes.txt) — NOT
from any external repo or pretrained model.

Usage:
  python recipe_lm.py train --data data/ko_recipes.txt --steps 4000 --out ckpt.pt
  python recipe_lm.py gen   --ckpt ckpt.pt --dish "김치볶음밥" --ingredients "밥,김치,계란,파,참기름"

Only dependency: torch. Vocabulary is built from the training data; nothing is
downloaded.
"""
import argparse, json, math, os, sys, time
import torch
import torch.nn as nn

D0, D1, I0, I1, R0, R1 = "<n>", "</n>", "<i>", "</i>", "<r>", "</r>"


# ------------------------------- model (from scratch) -------------------------
class CharLSTM(nn.Module):
    def __init__(self, vocab, embed=128, hidden=512, layers=2, dropout=0.1):
        super().__init__()
        self.emb = nn.Embedding(vocab, embed)
        self.lstm = nn.LSTM(embed, hidden, layers, batch_first=True,
                            dropout=dropout if layers > 1 else 0.0)
        self.head = nn.Linear(hidden, vocab)
        self.hidden, self.layers = hidden, layers

    def forward(self, x, state=None):
        e = self.emb(x)
        out, state = self.lstm(e, state)
        return self.head(out), state


# ------------------------------- data ----------------------------------------
def load_text(path, max_lines=None):
    lines = []
    with open(path, encoding="utf-8") as f:
        for i, ln in enumerate(f):
            ln = ln.strip()
            if ln:
                lines.append(ln)
            if max_lines and len(lines) >= max_lines:
                break
    return "\n".join(lines) + "\n"


def build_vocab(text):
    chars = sorted(set(text))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    return stoi, itos


# ------------------------------- train ---------------------------------------
def train(args):
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    text = load_text(args.data, args.max_lines)
    stoi, itos = build_vocab(text)
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long)
    V = len(stoi)
    print(f"[data] chars={len(data):,}  vocab={V}  device={dev}", flush=True)

    model = CharLSTM(V, args.embed, args.hidden, args.layers).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[model] char-LSTM from scratch · params={n_params:,}", flush=True)

    T, B = args.seq, args.batch
    def get_batch():
        ix = torch.randint(0, len(data) - T - 1, (B,))
        x = torch.stack([data[i:i + T] for i in ix]).to(dev)
        y = torch.stack([data[i + 1:i + 1 + T] for i in ix]).to(dev)
        return x, y

    lossf = nn.CrossEntropyLoss()
    model.train()
    t0 = time.time()
    for step in range(1, args.steps + 1):
        x, y = get_batch()
        logits, _ = model(x)
        loss = lossf(logits.reshape(-1, V), y.reshape(-1))
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % args.log == 0 or step == 1:
            ppl = math.exp(min(loss.item(), 20))
            print(f"step {step:>5}/{args.steps}  loss {loss.item():.3f}  ppl {ppl:7.1f}"
                  f"  {(time.time()-t0)/step*1000:.0f} ms/step", flush=True)
        if args.ckpt_every and step % args.ckpt_every == 0:
            _save(args.out, model, stoi, itos, args)
    _save(args.out, model, stoi, itos, args)
    print(f"[done] saved {args.out}  ({time.time()-t0:.0f}s)", flush=True)


def _save(path, model, stoi, itos, args):
    torch.save({"model": model.state_dict(),
                "stoi": stoi, "itos": {int(k): v for k, v in itos.items()},
                "cfg": {"embed": args.embed, "hidden": args.hidden, "layers": args.layers}},
               path)


# ------------------------------- generate ------------------------------------
@torch.no_grad()
def _sample(model, stoi, itos, prompt, dev, max_new=400, temp=0.8, top_k=40, stop=R1):
    ids = [stoi[c] for c in prompt if c in stoi]
    x = torch.tensor([ids], dtype=torch.long, device=dev)
    logits, state = model(x)
    out = list(prompt)
    stop_buf = ""
    for _ in range(max_new):
        logit = logits[0, -1] / temp
        if top_k:
            v, _ix = torch.topk(logit, min(top_k, logit.size(-1)))
            logit[logit < v[-1]] = -float("inf")
        probs = torch.softmax(logit, -1)
        nid = torch.multinomial(probs, 1).item()
        ch = itos[nid]
        out.append(ch)
        stop_buf = (stop_buf + ch)[-len(stop):]
        if stop_buf == stop:
            break
        logits, state = model(torch.tensor([[nid]], device=dev), state)
    return "".join(out)


def gen(args):
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ck = torch.load(args.ckpt, map_location=dev)
    stoi, itos, cfg = ck["stoi"], ck["itos"], ck["cfg"]
    model = CharLSTM(len(stoi), cfg["embed"], cfg["hidden"], cfg["layers"]).to(dev)
    model.load_state_dict(ck["model"]); model.eval()

    ings = "$".join([s.strip() for s in args.ingredients.split(",") if s.strip()]) + "$"
    prompt = f"{D0}{args.dish}{D1}{I0}{ings}{I1}{R0}"
    text = _sample(model, stoi, itos, prompt, dev, args.max_new, args.temp, args.top_k)
    # pretty print the fields
    body = text
    dish = _slice(body, D0, D1)
    ingr = _slice(body, I0, I1)
    recipe = _slice(body, R0, R1)
    print("=" * 64)
    print("직접 학습한 char-LSTM (from scratch · no pretrained GPT)")
    print("=" * 64)
    print(f"음식명 : {dish}")
    print(f"재료   : {', '.join(x for x in ingr.split('$') if x)}")
    print("조리법 :")
    for i, s in enumerate([s for s in recipe.replace('. ', '.\n').split('\n') if s.strip()], 1):
        print(f"  {i}. {s.strip()}")


def _slice(t, a, b):
    if a in t:
        t = t.split(a, 1)[1]
    if b in t:
        t = t.split(b, 1)[0]
    return t.strip()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    tr = sub.add_parser("train")
    tr.add_argument("--data", required=True)
    tr.add_argument("--out", default="ckpt.pt")
    tr.add_argument("--steps", type=int, default=4000)
    tr.add_argument("--batch", type=int, default=32)
    tr.add_argument("--seq", type=int, default=160)
    tr.add_argument("--embed", type=int, default=128)
    tr.add_argument("--hidden", type=int, default=512)
    tr.add_argument("--layers", type=int, default=2)
    tr.add_argument("--lr", type=float, default=3e-3)
    tr.add_argument("--log", type=int, default=100)
    tr.add_argument("--ckpt-every", type=int, default=1000, dest="ckpt_every")
    tr.add_argument("--max-lines", type=int, default=None, dest="max_lines")
    g = sub.add_parser("gen")
    g.add_argument("--ckpt", default="ckpt.pt")
    g.add_argument("--dish", required=True)
    g.add_argument("--ingredients", default="")
    g.add_argument("--max-new", type=int, default=400, dest="max_new")
    g.add_argument("--temp", type=float, default=0.8)
    g.add_argument("--top-k", type=int, default=40, dest="top_k")
    a = ap.parse_args()
    (train if a.cmd == "train" else gen)(a)
