# `ask.ipynb` — code walkthrough

Step-by-step explanation of the local inference notebook. Read this top to bottom and you should be able to read the notebook itself in two minutes.

---

## What the notebook does

```
your question
     │
     ▼  embed (BGE-base, on CPU)
question vector
     │
     ▼  FAISS top-k similarity search
ranked chunk IDs
     │
     ▼  hydrate text from rag_meta.jsonl
sources block "[Source 1] doc_id (date)\n…text…"
     │
     ▼  POST to Ollama on :11434
LoRA-merged Qwen-7B generates
     │
     ▼
cited answer in the persona's voice
```

Three pieces stay loaded in the kernel between questions:

| Object | What it is | First load |
|---|---|---|
| `embedder` | BGE-base-en-v1.5 sentence model | ~3 s, downloads ~500 MB on first run |
| `index` | FAISS `IndexFlatIP` of all chunk vectors | ~1 s |
| `meta` | Python list — chunk text + metadata, indexed by FAISS id | ~1 s |

Each subsequent question is ~5–10 s on Apple Silicon.

---

## Prerequisites

Before opening the notebook:

1. Ollama is running and has a persona model registered:
   ```bash
   brew install ollama
   ollama serve &
   ollama create priya -f Modelfile.priya
   ollama list             # priya should appear
   ollama run priya 'hi'   # pre-warms the model
   ```
2. The FAISS index files exist at `training/data/rag_index_<persona>.faiss` and `rag_meta_<persona>.jsonl` (output of `training/build_rag_index.py`).
3. Python deps are installed:
   ```bash
   pip install -r requirements.txt
   ```

---

## Cell 1 — Load the embedder and index

```python
import json, requests, faiss
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Edit if your project lives elsewhere
DRIVE = Path('/path/to/EmployeeRecall')
DATA  = DRIVE / 'training/data'

PERSONA = 'priya'   # or 'rohan'

embedder = SentenceTransformer('BAAI/bge-base-en-v1.5')
index    = faiss.read_index(str(DATA / f'rag_index_{PERSONA}.faiss'))
meta     = [json.loads(l) for l in (DATA / f'rag_meta_{PERSONA}.jsonl').open()]

print(f'Ready. {len(meta):,} chunks indexed.')
```

Things to know:

- **The embedder must match the one used to build the index.** BGE-base-en-v1.5 here, same in Colab prep. A different embedder produces vectors in a different space and similarity scores become meaningless.
- **`IndexFlatIP`** does inner product. Combined with L2-normalised vectors it equals cosine similarity. Exact search; sub-5 ms for 17k chunks.
- **`meta[i]` aligns with FAISS id `i`.** When `index.search` returns id 1234, `meta[1234]` is that chunk's text and metadata.

Run this cell once per session. Don't re-run unless you change `PERSONA`.

---

## Cell 2 — Define `ask()`

```python
def ask(question, k=8, model=None, max_tokens=800):
    model = model or PERSONA

    # 1. Embed the question
    e = embedder.encode([question], normalize_embeddings=True).astype('float32')

    # 2. Retrieve top-k
    scores, idxs = index.search(e, k)

    # 3. Build sources block
    sources = '\n\n'.join(
        f"[Source {i+1}] {meta[j]['meta'].get('doc_id')} ({meta[j]['meta'].get('date','')[:10]})\n{meta[j]['text']}"
        for i, j in enumerate(idxs[0]) if j >= 0
    )

    # 4. Compose prompt with citation instruction
    prompt = (
        "Answer using ONLY the source documents. Cite [Source N] inline after each fact.\n\n"
        f"QUESTION: {question}\n\nSOURCES:\n{sources}"
    )

    # 5. Call Ollama
    r = requests.post('http://127.0.0.1:11434/api/generate', json={
        'model': model, 'prompt': prompt, 'stream': False,
        'options': {'num_predict': max_tokens, 'temperature': 0.4, 'top_p': 0.9},
    }, timeout=180)
    r.raise_for_status()
    answer = r.json()['response']

    # 6. Print answer + citation table
    print('ANSWER\n' + '='*70)
    print(answer)
    print('\nSOURCES\n' + '='*70)
    for i, (s, j) in enumerate(zip(scores[0], idxs[0])):
        if j >= 0:
            m = meta[j]['meta']
            print(f"  [{i+1}] {m.get('doc_id'):40s} {m.get('date','')[:10]}  score={s:.3f}")
    return answer
```

What to know:

- **No system prompt is sent here.** The persona voice is baked into the GGUF via Ollama's Modelfile `SYSTEM` block. Changing the system prompt requires `ollama create` again.
- **Use `127.0.0.1`, not `localhost`.** Some clients resolve `localhost` to IPv6 first; Uvicorn binds IPv4. Skip this and you'll get `ECONNREFUSED ::1:11434`.
- **`temperature=0.4`** keeps the voice consistent. Drop to 0.2 for tighter factual answers, raise to 0.6 for more drafty replies.
- **`k=8`** is a good default for 7B + 4 k context. Bump to 16 for broader questions.

---

## Cell 3+ — Ask anything

```python
ask("What happened with Acme Corp?")
```

Each question is one cell. Re-run any cell to re-ask. Edit the string to ask your own.

Sample output:

```
ANSWER
======================================================================
Thanks for the patience while I dug into this. The seat-count on Acme's
Q1 invoice came in 31 seats over (388 vs 357), about $14k. Mike Reyes
(CFO) pushed on this in a working session on March 4 [Source 1]. We
landed on a partial credit ($4.2k applied to Q2)…

SOURCES
======================================================================
  [1] meeting-acme-001                         2025-03-04  score=0.74
  [2] email-acme-003                           2025-03-03  score=0.71
  [3] meeting-acme-1on1-2025-10                2025-10-16  score=0.70
```

---

## Voice-only mode (no RAG)

For drafting where retrieval would just add noise:

```python
def voice_only(prompt, model=None, max_tokens=400):
    r = requests.post('http://127.0.0.1:11434/api/generate', json={
        'model': model or PERSONA, 'prompt': prompt, 'stream': False,
        'options': {'num_predict': max_tokens, 'temperature': 0.5, 'top_p': 0.9},
    }, timeout=120)
    return r.json()['response']

voice_only("Draft a reply asking Sarah to schedule a Q2 review.")
```

Same Ollama call, no FAISS step. The Modelfile `SYSTEM` block still applies, so the voice is intact — only the source-grounding is gone.

---

## Debug helper — what was retrieved?

If `ask()` returns a strange answer, it's almost always bad retrieval. Inspect what FAISS pulled before calling the model:

```python
def debug_retrieve(question, k=8, preview=300):
    e = embedder.encode([question], normalize_embeddings=True).astype('float32')
    scores, idxs = index.search(e, k)
    for i, j in enumerate(idxs[0]):
        if j < 0: continue
        m = meta[j]['meta']
        print(f"[{i+1}] {scores[0][i]:.3f}  {m.get('doc_id')}  ({m.get('date','')[:10]})")
        print(f"    {meta[j]['text'][:preview]}...")

debug_retrieve("What happened with Acme Corp?")
```

If the top scores are all <0.5 the question is too far from anything in the corpus — rephrase, try synonyms, or check that the persona's corpus actually contains an answer.

---

## Switching persona

Edit cell 1 — change `PERSONA = 'priya'` to `PERSONA = 'rohan'`. Re-run cell 1 (the embedder is reused). Cell 2 is unchanged. Re-run any question cell.

Both persona Ollama models must be registered separately:

```bash
ollama create priya -f Modelfile.priya
ollama create rohan -f Modelfile.rohan
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ConnectionError` on 11434 | Ollama not running | `ollama serve &` |
| `model 'priya' not found` | Model not registered | `ollama create priya -f Modelfile.priya` |
| Generic answers, no voice | Modelfile `SYSTEM` block still placeholder | Replace with contents of `system_prompt_priya.txt` |
| Citations look irrelevant | Embedder mismatch | Cell 1 must use `BAAI/bge-base-en-v1.5` |
| Slow first generation | Ollama loading model | Normal once. Pre-warm: `ollama run priya 'hi'` |
| `Killed: 9` on Mac | Out of RAM | 7B Q4_K_M needs ~6 GB. Close other apps or use Q3_K_M |
| `ECONNREFUSED ::1:11434` | IPv6 resolution | Use `127.0.0.1` not `localhost` |
| Drive path not found | Project moved | Edit `DRIVE` in cell 1 |

---

## Where this fits in the whole pipeline

```
Colab:    train_lora.py  →  merge  →  GGUF (Q4_K_M)
                                          │
                                          ▼ download
Mac:      ollama create  →  GGUF in ~/.ollama/models/
                                          ↑
                                     ask.ipynb  ←  FAISS index + metadata (from prep)
```

The notebook is the read side. Training and indexing happen in Colab; the notebook only consumes the artifacts.
