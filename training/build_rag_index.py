"""
Embed RAG chunks with sentence-transformers and build a FAISS index.

Outputs:
  training/data/rag_index_{persona}.faiss
  training/data/rag_meta_{persona}.jsonl

Run:
    python training/build_rag_index.py --persona priya
"""
import argparse
import json
from pathlib import Path

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent

EMBED_MODEL = "BAAI/bge-base-en-v1.5"  # 768-dim, strong general-purpose


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, choices=["priya","rohan"])
    ap.add_argument("--data-dir", default=str(ROOT / "training" / "data"))
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    in_path = data_dir / f"rag_docs_{args.persona}.jsonl"
    out_index = data_dir / f"rag_index_{args.persona}.faiss"
    out_meta = data_dir / f"rag_meta_{args.persona}.jsonl"

    print(f"Loading chunks from {in_path}")
    chunks = [json.loads(l) for l in in_path.open()]
    print(f"  {len(chunks)} chunks")

    print(f"Loading embedder: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)

    print("Embedding...")
    texts = [c["text"] for c in chunks]
    emb = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,  # so we can use inner-product = cosine
        convert_to_numpy=True,
    ).astype("float32")

    dim = emb.shape[1]
    print(f"  embeddings shape: {emb.shape}")

    # Inner-product index over normalized vectors == cosine similarity
    index = faiss.IndexFlatIP(dim)
    index.add(emb)
    faiss.write_index(index, str(out_index))
    print(f"Wrote FAISS index to {out_index}")

    with out_meta.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    print(f"Wrote metadata to {out_meta}")


if __name__ == "__main__":
    main()
