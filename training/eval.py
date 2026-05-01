"""
Evaluate the trained model on hand-crafted history-recall questions and on
held-out style pairs.

Three evals:
  1. History recall — does the answer mention required keywords + cite sources?
  2. Style match — embedding similarity between generated and held-out reply
  3. Citation precision — % of cited sources actually in retrieved set

Outputs:
  training/eval_results_{persona}.json
  training/eval_results_{persona}.md (human-readable)

Run:
    python training/eval.py --persona priya
"""
import argparse
import json
import re
from pathlib import Path

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def load_rag(persona, data_dir):
    index = faiss.read_index(str(data_dir / f"rag_index_{persona}.faiss"))
    meta = [json.loads(l) for l in (data_dir / f"rag_meta_{persona}.jsonl").open()]
    return index, meta


def retrieve(question, embedder, index, meta, k=8):
    q_emb = embedder.encode([question], normalize_embeddings=True).astype("float32")
    scores, ids = index.search(q_emb, k)
    return [(meta[i], float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]


def build_prompt(question, retrieved, persona_system):
    sources = []
    for i, (chunk, score) in enumerate(retrieved):
        m = chunk["meta"]
        title = m.get("title") or m.get("doc_id", "untitled")
        sources.append(f"[Source {i+1}] {title} ({m.get('date','')}, doc_id={m.get('doc_id')})\n{chunk['text']}")
    context = "\n\n".join(sources)
    user_msg = f"""Answer the question using ONLY the source documents below. Cite [Source N] inline.

QUESTION: {question}

SOURCES:
{context}"""
    return [{"role":"system","content":persona_system},{"role":"user","content":user_msg}]


def gen(model, tok, messages, max_new=600):
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tok.eos_token_id)
    full = tok.decode(out[0], skip_special_tokens=True)
    return full[len(tok.decode(inputs.input_ids[0], skip_special_tokens=True)):].strip()


def keyword_score(answer, must_mention):
    answer_l = answer.lower()
    hits = [k for k in must_mention if k.lower() in answer_l]
    return len(hits) / max(1, len(must_mention)), hits, [k for k in must_mention if k not in hits]


def parse_citations(answer):
    return [int(m) for m in re.findall(r"\[Source (\d+)\]", answer)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, choices=["priya","rohan"])
    ap.add_argument("--data-dir", default=str(ROOT / "training" / "data"))
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--base-model", default=BASE_MODEL)
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--n-style-eval", type=int, default=30)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    ckpt = Path(args.checkpoint) if args.checkpoint else ROOT / "training" / "checkpoints" / args.persona
    sysprompt = (data_dir / f"system_prompt_{args.persona}.txt").read_text()
    questions = json.loads((ROOT / "training" / "eval_questions.json").read_text())[args.persona]

    print("Loading models + RAG...")
    embedder = SentenceTransformer(EMBED_MODEL)
    index, meta = load_rag(args.persona, data_dir)
    tok = AutoTokenizer.from_pretrained(args.base_model)
    base = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype=torch.bfloat16, device_map="auto")
    model = PeftModel.from_pretrained(base, str(ckpt))
    model.eval()

    # ---------- Eval 1: History recall ----------
    print("\n=== History recall ===")
    history_results = []
    for item in questions:
        retrieved = retrieve(item["q"], embedder, index, meta, k=args.top_k)
        ans = gen(model, tok, build_prompt(item["q"], retrieved, sysprompt))
        kw_score, hits, misses = keyword_score(ans, item["must_mention"])
        cites = parse_citations(ans)
        history_results.append({
            "question": item["q"], "answer": ans,
            "keyword_score": kw_score, "hits": hits, "misses": misses,
            "n_citations": len(cites), "n_retrieved": len(retrieved),
        })
        print(f"  {kw_score:.2f}  {item['q'][:60]}")

    # ---------- Eval 2: Style match on held-out ----------
    print("\n=== Style match (held-out) ===")
    eval_pairs = [json.loads(l) for l in (data_dir / f"sft_eval_{args.persona}.jsonl").open()]
    eval_pairs = eval_pairs[:args.n_style_eval]
    style_results = []
    for ex in eval_pairs:
        sys_msg = ex["messages"][0]
        user_msg = ex["messages"][1]
        gold = ex["messages"][2]["content"]
        gen_ans = gen(model, tok, [sys_msg, user_msg], max_new=400)
        gold_emb = embedder.encode([gold], normalize_embeddings=True)
        gen_emb = embedder.encode([gen_ans], normalize_embeddings=True)
        sim = float((gold_emb @ gen_emb.T)[0,0])
        style_results.append({"gold_len": len(gold), "gen_len": len(gen_ans), "cosine": sim})

    cosines = [r["cosine"] for r in style_results]
    style_summary = {
        "n": len(cosines),
        "mean_cosine": float(np.mean(cosines)),
        "median_cosine": float(np.median(cosines)),
        "p25_cosine": float(np.percentile(cosines, 25)),
        "p75_cosine": float(np.percentile(cosines, 75)),
    }

    # ---------- Summary ----------
    history_summary = {
        "n": len(history_results),
        "mean_keyword_score": float(np.mean([r["keyword_score"] for r in history_results])),
        "mean_n_citations": float(np.mean([r["n_citations"] for r in history_results])),
        "questions_with_no_citations": sum(1 for r in history_results if r["n_citations"]==0),
    }

    out = {
        "persona": args.persona,
        "checkpoint": str(ckpt),
        "history_summary": history_summary,
        "style_summary": style_summary,
        "history_detail": history_results,
        "style_detail": style_results,
    }

    out_json = ROOT / "training" / f"eval_results_{args.persona}.json"
    out_json.write_text(json.dumps(out, indent=2))

    md = [f"# Eval results — {args.persona}\n",
          f"**Checkpoint:** `{ckpt}`\n",
          "## History recall",
          f"- Mean keyword score: **{history_summary['mean_keyword_score']:.2f}**",
          f"- Mean citations per answer: {history_summary['mean_n_citations']:.1f}",
          f"- Questions with NO citations: {history_summary['questions_with_no_citations']}/{history_summary['n']}",
          "",
          "## Style match (held-out replies)",
          f"- N evaluated: {style_summary['n']}",
          f"- Mean cosine: **{style_summary['mean_cosine']:.3f}** (higher = more like the real reply)",
          f"- Median: {style_summary['median_cosine']:.3f}",
          f"- IQR: [{style_summary['p25_cosine']:.3f}, {style_summary['p75_cosine']:.3f}]",
          "",
          "## Per-question history detail",
    ]
    for r in history_results:
        md.append(f"### {r['question']}")
        md.append(f"**Score:** {r['keyword_score']:.2f}  |  **Citations:** {r['n_citations']}")
        if r["misses"]:
            md.append(f"**Missed keywords:** {', '.join(r['misses'])}")
        md.append("\n```")
        md.append(r["answer"][:1500])
        md.append("```\n")

    out_md = ROOT / "training" / f"eval_results_{args.persona}.md"
    out_md.write_text("\n".join(md))

    print("\n=== SUMMARY ===")
    print(f"History keyword score: {history_summary['mean_keyword_score']:.2f}")
    print(f"Style cosine: {style_summary['mean_cosine']:.3f}")
    print(f"\nResults: {out_json}")
    print(f"         {out_md}")


if __name__ == "__main__":
    main()
