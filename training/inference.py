"""
RAG + LoRA inference loop with citations.

Loads:
  - the FAISS index for the persona
  - the chunk metadata
  - the LoRA-tuned base model

Usage:
    python training/inference.py --persona priya --question "What happened with Acme?"
    python training/inference.py --persona priya --interactive
"""
import argparse
import json
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
    """Inject retrieved docs as context."""
    sources = []
    for i, (chunk, score) in enumerate(retrieved):
        m = chunk["meta"]
        title = m.get("title") or m.get("doc_id", "untitled")
        date = m.get("date","")
        sources.append(f"[Source {i+1}] {title} ({date}, doc_id={m.get('doc_id')})\n{chunk['text']}")
    context = "\n\n".join(sources)

    user_msg = f"""You will answer a question using ONLY the source documents below. Cite sources inline as [Source N]. If the answer is not in the sources, say so.

QUESTION:
{question}

SOURCES:
{context}

Answer in your natural voice, with [Source N] citations after each fact."""

    return [
        {"role": "system", "content": persona_system},
        {"role": "user", "content": user_msg},
    ]


def generate(model, tokenizer, messages, max_new_tokens=800):
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.4,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )
    full = tokenizer.decode(out[0], skip_special_tokens=True)
    # strip the prompt
    return full[len(tokenizer.decode(inputs.input_ids[0], skip_special_tokens=True)):].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, choices=["priya","rohan"])
    ap.add_argument("--data-dir", default=str(ROOT / "training" / "data"))
    ap.add_argument("--checkpoint", default=None,
                    help="Path to LoRA adapter dir. Default: training/checkpoints/{persona}")
    ap.add_argument("--base-model", default=BASE_MODEL)
    ap.add_argument("--question", default=None)
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--top-k", type=int, default=8)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    ckpt = Path(args.checkpoint) if args.checkpoint else ROOT / "training" / "checkpoints" / args.persona
    sysprompt = (data_dir / f"system_prompt_{args.persona}.txt").read_text()

    print("Loading RAG index...")
    index, meta = load_rag(args.persona, data_dir)
    embedder = SentenceTransformer(EMBED_MODEL)

    print(f"Loading base model {args.base_model} + LoRA from {ckpt}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base, str(ckpt))
    model.eval()

    def answer(q):
        retrieved = retrieve(q, embedder, index, meta, k=args.top_k)
        messages = build_prompt(q, retrieved, sysprompt)
        ans = generate(model, tokenizer, messages)
        print("\n" + "="*70 + "\nANSWER\n" + "="*70)
        print(ans)
        print("\n" + "="*70 + f"\nSOURCES (top {len(retrieved)})\n" + "="*70)
        for i, (chunk, score) in enumerate(retrieved):
            m = chunk["meta"]
            print(f"[{i+1}] {m.get('doc_id'):40s} {m.get('date','')} score={score:.3f}")

    if args.question:
        answer(args.question)
    elif args.interactive:
        print(f"Persona: {args.persona}. Type questions, Ctrl-C to exit.")
        while True:
            try:
                q = input("\n> ").strip()
                if not q: continue
                answer(q)
            except (KeyboardInterrupt, EOFError):
                print()
                break
    else:
        print("Pass --question or --interactive")


if __name__ == "__main__":
    main()
