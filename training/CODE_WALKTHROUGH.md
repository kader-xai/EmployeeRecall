# Training pipeline walkthrough

What each script in `training/` does, in order.

```
prep_training_data.py  →  build_rag_index.py  →  train_lora.py  →  inference.py
                                                                        ↓
                                                                     eval.py
```

---

## 1. `prep_training_data.py`

Takes the JSONL corpus and produces two artifacts:

- `sft_train_<persona>.jsonl` and `sft_eval_<persona>.jsonl` — chat-format `(incoming thread → persona reply)` pairs for LoRA fine-tuning. 95/5 split.
- `rag_docs_<persona>.jsonl` — every document chunked with metadata for the RAG index.

Also writes `system_prompt_<persona>.txt` from the persona JSON fingerprint.

### Key logic

**Thread reconstruction.** Emails are grouped by `thread_id`, sorted by `thread_position` then `date`. For every email authored by the persona that has at least one prior message in its thread, the prior context becomes the input and the persona's email becomes the target.

**Chunking is type-aware.**

| Doc type | Chunking |
|---|---|
| email | One chunk per email (or split by paragraph if > 1500 chars). Preamble has from/to/subject/date. |
| meeting_notes (structured) | One chunk per section: discussion, decisions, action_items. Decisions and actions get a higher retrieval boost in metadata. |
| meeting_notes (transcript) | Window of 8 segments per chunk, with timestamps and speakers. |
| rfc / adr / postmortem / design_doc | Split on markdown headings (`## ...`). One chunk per section. |

**System prompt template.** Pulls fields from the persona JSON: name, role, tone, top vocab phrases, decision stance, sign-off. Used at inference time to remind the model who it is.

```bash
python training/prep_training_data.py --persona priya
```

Output (Priya): 16,779 docs in → 1,287 SFT pairs (1,223 train + 64 eval) and 17,663 RAG chunks.

---

## 2. `build_rag_index.py`

Embeds every chunk with BGE-base-en-v1.5 and builds a FAISS index.

```python
embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
embs = embedder.encode(texts, normalize_embeddings=True, batch_size=128)
index = faiss.IndexFlatIP(embs.shape[1])
index.add(embs.astype("float32"))
faiss.write_index(index, str(out_path))
```

Notes:

- BGE-base produces 768-dim vectors. L2-normalised.
- `IndexFlatIP` does inner product — equivalent to cosine similarity on normalised vectors. Exact search; sufficient for ~17k chunks.
- For >1M chunks, switch to `IndexHNSWFlat` or `IndexIVFPQ`.
- The same embedder must be used at query time (see `inference.py`).

```bash
python training/build_rag_index.py --persona priya --batch-size 128
```

Outputs `rag_index_<persona>.faiss` (~50 MB) and `rag_meta_<persona>.jsonl` (chunk text + provenance).

---

## 3. `train_lora.py`

LoRA fine-tune of Qwen2.5-7B on the SFT pairs. Uses Unsloth for 2x speed and half VRAM.

### Config

```python
model = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
    max_seq_length=4096,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth",
)
```

| Hyperparameter | Value | Why |
|---|---|---|
| `r` | 16 | Standard; rank 32 marginally better, doubles adapter size |
| `lora_alpha` | 32 | 2× rank, conventional |
| target modules | all attention + MLP | Both matter for style |
| 4-bit base | yes | Fits 7B in ~14 GB VRAM |
| epochs | 3 | Voice converges by epoch 2-3, then overfits |
| batch | 4 × grad-accum 4 | Effective batch 16 on A100 40GB |
| LR | 2e-4, cosine, warmup 0.03 | Standard LoRA defaults |
| save_steps | 200 | Checkpoints survive Colab disconnects |

```bash
python training/train_lora.py --persona priya
```

Output: `training/checkpoints/<persona>/adapter_model.safetensors` (~150 MB).

---

## 4. `inference.py`

Loads the LoRA adapter on top of the base model, runs RAG, generates with citations.

### Three steps per query

```python
# 1. retrieve
q_emb = embedder.encode([question], normalize_embeddings=True).astype("float32")
scores, ids = index.search(q_emb, k=8)

# 2. compose prompt
sources = "\n\n".join(f"[Source {i+1}] ..." for i, chunk in enumerate(retrieved))
messages = [
    {"role": "system", "content": persona_system_prompt},
    {"role": "user",   "content": f"...QUESTION: {q}\n\nSOURCES:\n{sources}"},
]

# 3. generate
text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
out = model.generate(**inputs, max_new_tokens=800, temperature=0.4, top_p=0.9)
```

```bash
python training/inference.py --persona priya --interactive
```

For local Mac use after Colab → GGUF conversion, the same logic lives in [`local_inference/api.py`](../local_inference/api.py) and [`local_inference/ask.ipynb`](../local_inference/ask.ipynb), but calls Ollama via HTTP instead of holding the model in process.

---

## 5. `eval.py`

Two automated scores:

- **History recall.** Each `eval_questions.json` entry has a question + list of expected keywords. The model's answer is checked for keyword overlap fraction.
- **Style cosine.** For held-out reply pairs, compare the model's drafted reply to the real one via cosine similarity of their BGE embeddings.

```bash
python training/eval.py --persona priya --base-model Qwen/Qwen2.5-7B-Instruct
```

Outputs `eval_results_<persona>.json` and `.md`. Both gitignored.

A live run on Priya (3 epochs):

```
History keyword score: 0.30   (1.0 on hand-written storyline questions, 0.0 on bulk-only topics)
Style cosine:          0.735
```

The history score is bounded by the corpus shape: questions whose answers exist only in templated bulk content can't be answered correctly because the bulk content doesn't contain those facts.

---

## Path resolution

All scripts use:

```python
ROOT = Path(__file__).resolve().parent.parent
```

So they work regardless of where you invoke them from, as long as the `training/`, `corpus/`, `personas/` siblings are intact.
