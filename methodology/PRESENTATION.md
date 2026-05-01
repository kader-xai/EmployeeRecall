---
marp: true
theme: default
paginate: true
size: 16:9
header: 'Employee Recall'
footer: 'methodology/PRESENTATION.md'
---

<!-- Render: VS Code → Marp extension → Export, or
     npx @marp-team/marp-cli@latest methodology/PRESENTATION.md -o deck.pdf -->

# Employee Recall

### Capturing a Departing Employee's Voice and Knowledge in an AI Successor

A reproducible methodology for training a persona-continuity LoRA, end to end.

---

## The Problem

When a senior employee leaves, two things go with them:

1. **Voice** — how they wrote to customers, peers, executives.
2. **Historical knowledge** — *why* did we pick Postgres in 2023? Why did Acme get a $4,200 credit?

Onboarding documents cover neither.

---

## Two Demo Use Cases

| | Priya Sharma — Senior CSM | Rohan Iyer — Staff Engineer |
|---|---|---|
| Tenure | 3.5 yr at Northwind SaaS | 5 yr on Platform team |
| Owns | 40 customer accounts, $4.2M ARR | Event pipeline, auth, gateway, rate limiter |
| Voice | Warm-professional, no jargon | Terse, dry, "fwiw / nit / ftr" |
| Sample question | "What's the renewal posture for Globex?" | "Why are we on Postgres for events?" |

---

## Core Thesis

Style and knowledge need different machinery.

- **Style** is parametric. Bake it into model weights via LoRA fine-tuning on reply pairs.
- **Knowledge** is retrieval. Embed every doc into a vector index and look up at inference time.

LoRA gives you the voice. RAG gives you the receipts.

---

## End-to-End Architecture

```
                 personas / cast / accounts / projects
                                │
   hand-written storylines + bulk generators
                                │
                                ▼
                   prep_training_data.py
                  ┌──────────┴──────────┐
            sft_*.jsonl          rag_docs_*.jsonl
                  │                    │
            train_lora.py       build_rag_index.py
                  │                    │
        checkpoints/{persona}    rag_index_*.faiss
                  └─────────┬──────────┘
                            ▼
                   inference.py / eval.py
```

---

## The Synthetic Corpus — Three Layers

| Layer | Purpose | Volume |
|---|---|---|
| Hand-written storylines | Demo material — the questions that need to land | 8 threads, ~50 docs |
| Dense per-account / per-project | Realism — frequent cadence with named entities | ~150 docs/year |
| Bulk routine | Ambient volume — generic emails, weekly syncs | ~16,000 total |

Storylines drive recall. Bulk drives realism. Dense bridges the two.

---

## Five Metadata Files Drive Everything

```
personas/priya.json    voice fingerprint, decision style, vocab
personas/rohan.json    signature patterns, response latency
cast/internal.json     ~25 colleagues, relationships, roles
accounts/priya_acc...  40 customer accounts + storylines
projects/rohan_pro...  14 engineering projects + decisions
```

`personas/priya.json` is **deterministic input**, not just docs:

```json
"vocab_fingerprint": {
  "filler_phrases_high_frequency":
    ["circling back", "quick one", "to flag", "worth a call"],
  "filler_phrases_avoided":
    ["per my last email", "as discussed", "kindly"]
}
```

---

## Volume

| | Count |
|---|---|
| Semantic documents (JSONL) | 18,978 |
| Multi-format files (.eml, .ics, .vtt) | 54,927 |
| Hand-written storylines | 8 |
| Customer accounts | 40 |
| Engineering projects | 14 |

---

## prep_training_data.py — Two Outputs From One Pass

```python
def main():
    persona = load_persona(args.persona)
    docs    = load_corpus(persona_dir)

    # Output 1: SFT pairs for the LoRA
    threads   = build_thread_index(docs)
    sft_pairs = make_sft_pairs(threads, persona["email"])
    sysprompt = system_prompt_for(persona)
    chat      = [to_chat_format(p, sysprompt) for p in sft_pairs]

    # Output 2: RAG chunks for retrieval
    for d in docs:
        for chunk_text, meta in chunk_doc(d):
            f.write(json.dumps({"text": chunk_text, "meta": meta}))
```

---

## SFT Pair Construction

```python
def make_sft_pairs(threads, persona_email):
    pairs = []
    for tid, msgs in threads.items():
        for i, msg in enumerate(msgs):
            if i == 0: continue
            if msg["from"]["email"] != persona_email: continue
            history = "\n\n---\n\n".join(format(m) for m in msgs[:i])
            reply   = msg["body"].strip()
            if len(reply) < 20: continue
            pairs.append({"incoming": history, "reply": reply, ...})
```

The full prior thread is the input; the persona's reply is the target. After training, the model learns the *shape* of replies — opens with "Quick context", closes with "Thanks, Priya".

---

## RAG Chunking — Type-Aware

```python
def chunk_doc(doc, max_chars=1500):
    if doc["doc_type"] == "email":
        # one chunk per email; split by paragraph if too long
    elif doc["doc_type"] == "meeting_notes":
        if doc.get("transcript_segments"):
            # window of 8 segments per chunk
        else:
            # per-section chunks; decisions and action_items get a boost
    elif doc["doc_type"] in ("rfc", "adr", "postmortem"):
        sections = re.split(r"\n## ", body)
        # one chunk per markdown heading
```

Naive fixed-size chunking destroys structure. Type-aware chunking keeps decisions and actions whole.

---

## build_rag_index.py — 30 Lines

```python
chunks   = [json.loads(l) for l in (data_dir / f"rag_docs_{persona}.jsonl").open()]
embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
embs     = embedder.encode([c["text"] for c in chunks],
                            normalize_embeddings=True, batch_size=128)

index = faiss.IndexFlatIP(embs.shape[1])
index.add(embs.astype("float32"))
faiss.write_index(index, str(data_dir / f"rag_index_{persona}.faiss"))
```

`IndexFlatIP` on normalised vectors = cosine similarity. Exact search. ~5 ms per query for 17k chunks.

---

## train_lora.py — The Heart in 25 Lines

```python
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
    max_seq_length=4096,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj","k_proj","v_proj","o_proj",
                    "gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth",
)
```

Rank-16 LoRA on all attention + MLP linear layers. ~0.1% of base parameters trained. Rest is frozen.

---

## Training Config — Why These Numbers

```python
SFTConfig(
    num_train_epochs=3,                  # voice converges by 2-3, then overfits
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,       # effective batch 16
    learning_rate=2e-4,                  # standard LoRA LR; cosine
    warmup_ratio=0.03,
    bf16=True,                           # A100 native
    save_steps=200,                      # checkpoints survive disconnects
)
```

Cost on A100 40GB: ~25–40 min per persona, ~$0.25 spot.

---

## inference.py — Three Steps

```python
# 1. Retrieve
q_emb = embedder.encode([question], normalize_embeddings=True)
scores, ids = index.search(q_emb.astype("float32"), k=8)

# 2. Compose prompt
sources = "\n\n".join(f"[Source {i+1}] {chunk['text']}" for i, chunk in retrieved)
messages = [
    {"role": "system", "content": persona_system},
    {"role": "user",   "content": f"...QUESTION: {q}\n\nSOURCES:\n{sources}"},
]

# 3. Generate
out = model.generate(**inputs, max_new_tokens=800, temperature=0.4, top_p=0.9)
```

Citations come from the prompt instruction. The model is told to cite `[Source N]`.

---

## eval.py — Two Automated Scores

```python
# History recall — keyword overlap with gold answer
score = sum(kw in answer.lower() for kw in gold["keywords"]) / len(gold["keywords"])

# Style match — cosine similarity vs persona's real reply
style_cos = cosine(embed(answer), embed(gold_reply))
```

Live numbers (Priya, 7B / 3 epochs):

```
History keyword score: 0.30   strong on hand-written storylines, weak on bulk-only
Style cosine:          0.735  solid voice match
```

---

## Sample Output — "What happened with Acme?"

> Thanks for the patience while I dug into this. The seat-count on Acme's Q1 invoice came in 31 seats over (388 vs 357), about $14k. **Mike Reyes (CFO)** pushed on this in a working session on March 4 [Source 1]. We landed on a partial credit (**$4.2k**) and Sarah Lin's team agreed to run quarterly seat-deactivation reviews going forward [Source 2]…

```
SOURCES:
  [1] meeting-acme-001     2025-03-04   score=0.74
  [2] email-acme-003       2025-03-03   score=0.71
  [3] meeting-acme-1on1    2025-10-16   score=0.70
```

Voice + facts + citations. No invented details.

---

## Comparison vs Alternatives

| Approach | Voice | Facts | Update cost | Privacy | Cost |
|---|---|---|---|---|---|
| GPT-4 + system prompt only | ✗ generic | ✗ none | — | poor | $$$ |
| GPT-4 + RAG | ✗ generic | ✓ | low | poor | $$$ |
| Full fine-tune of GPT-4 | ✓ | ✓ stale | very high | poor | $$$$ |
| Full fine-tune of open model | ✓ | ✓ stale | high | good | $$ |
| LoRA + RAG (this) | ✓ | ✓ fresh | low | good | $0.25 |

---

## Hardware & Cost — A100 Defaults

| Tier | GPU | Time per persona | Cost |
|---|---|---|---|
| A100 40GB | NVIDIA A100 | 25–40 min | ~$0.25 |
| L4 24GB | NVIDIA L4 | 90–120 min | ~$0.50 |
| T4 16GB (free Colab, 3B model) | NVIDIA T4 | 60–90 min | $0 |

```bash
python training/prep_training_data.py --persona priya
python training/build_rag_index.py     --persona priya
python training/train_lora.py          --persona priya
python training/inference.py           --persona priya --interactive
```

---

## Use Cases Beyond the Demo

- Outgoing executive — board correspondence, investor updates
- Domain expert leaving / retiring
- Sales handoff at scale
- Onboarding accelerator
- Internal coaching

The constraint is organisational, not technical: consent, audit, sunset planning.

---

## Limitations

- Synthetic only. Real deployment requires real consent and a real audit trail.
- Bulk content is templated; the hand-written storylines do most of the heavy lifting.
- Voice ≠ judgement. The model writes in the persona's voice but is not the persona.
- Memorisation risk — a LoRA on real correspondence can regurgitate verbatim. Audit before release.
- Voice drifts; humans evolve. Plan to retrain quarterly.

---

## Production Deployment Checklist

- Consent signed by the persona, scoped to specific corpora
- Provenance log — every training run records data hash, model hash, who triggered it
- Citation enforcement — refuse to answer if retrieval returns no sources above threshold
- Memorisation audit — sample 100 outputs, n-gram check vs corpus
- Rate limiter on inference (per-user)
- Voice attribution disclaimer on every output: "Drafted in the voice of X by an AI; not authored by X."
- Sunset plan — when does the model retire?

---

## What You Get After Training

```
training/checkpoints/priya/
├── adapter_config.json          LoRA hyperparameters
├── adapter_model.safetensors    ~150 MB of trained weights
├── checkpoint-200/              rolling backups
└── tokenizer.json

training/data/
├── rag_index_priya.faiss        ~50 MB FAISS vector index
├── rag_meta_priya.jsonl         ~25 MB chunk metadata (provenance)
├── system_prompt_priya.txt      runtime persona prompt
├── sft_train_priya.jsonl        for reproducibility
└── sft_eval_priya.jsonl
```

~250 MB per persona; runs anywhere a 7B 4-bit model loads.

---

## Recap

1. Two failures of departure: voice walks out, knowledge walks out.
2. One architectural insight: LoRA the voice, RAG the knowledge.
3. One pipeline: prep → embed → train → infer → eval. Five scripts, ~800 lines.
4. One A100, 30 minutes, $0.25 per persona.
5. One question to ask: did you earn the right to do this?

---

## Further Reading

| File | Contents |
|---|---|
| README.md | Overview + reproduction |
| methodology/METHODOLOGY.md | End-to-end methodology, design rationale |
| methodology/CORPUS_TECHNICAL_DETAILS.md | Every corpus layer explained |
| methodology/VIDEO_SCRIPT.md | 6–8 min demo script |
| training/CODE_WALKTHROUGH.md | Training pipeline reference |
| training/RUNBOOK.md | Cloud GPU training (RunPod / Vast) |
| training/COLAB.md | Colab quickstart |
| local_inference/CODE_WALKTHROUGH.md | `ask.ipynb` reference |
| local_inference/SLACK_N8N_SETUP.md | Slack + n8n integration |
