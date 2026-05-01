"""
Tiny FastAPI server that exposes ask() and voice_only() over HTTP.

Used by n8n / Slack / any other tool that wants to talk to your trained personas.

Run:
    pip3 install fastapi uvicorn
    python3 api.py        # listens on http://localhost:8000

Endpoints:
    GET  /                      → health check
    GET  /personas              → which personas are loaded
    POST /ask                   → RAG-grounded answer with citations
    POST /voice_only            → drafting in the persona voice (no RAG)

Example:
    curl -X POST http://localhost:8000/ask \\
         -H 'Content-Type: application/json' \\
         -d '{"persona":"priya", "question":"What happened with Acme?"}'
"""
import json
import requests
import faiss
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# ---- Config ----
DRIVE = Path('/Users/kader/Library/CloudStorage/GoogleDrive-pentesterrepo202@gmail.com/My Drive/Projects/ProjectRecall')
DATA = DRIVE / 'training/data'
OLLAMA_URL = 'http://localhost:11434/api/generate'

# ---- Load all available personas at startup ----
print('Loading embedder...')
embedder = SentenceTransformer('BAAI/bge-base-en-v1.5')

PERSONAS = {}
for p in ('priya', 'rohan'):
    idx_path = DATA / f'rag_index_{p}.faiss'
    meta_path = DATA / f'rag_meta_{p}.jsonl'
    if idx_path.exists() and meta_path.exists():
        PERSONAS[p] = {
            'index': faiss.read_index(str(idx_path)),
            'meta': [json.loads(l) for l in meta_path.open()],
        }
        print(f'  loaded {p}: {len(PERSONAS[p]["meta"]):,} chunks')

if not PERSONAS:
    raise RuntimeError(f'No persona indexes found in {DATA}. Run prep first.')

# ---- API ----
app = FastAPI(title='ProjectRecall Persona API')


class AskRequest(BaseModel):
    persona: str
    question: str
    k: int = 8
    max_tokens: int = 800


class VoiceOnlyRequest(BaseModel):
    persona: str
    prompt: str
    max_tokens: int = 400


def _retrieve(persona: str, question: str, k: int):
    p = PERSONAS[persona]
    e = embedder.encode([question], normalize_embeddings=True).astype('float32')
    scores, idxs = p['index'].search(e, k)
    chunks = []
    for i, j in enumerate(idxs[0]):
        if j < 0: continue
        m = p['meta'][j]
        chunks.append({
            'rank': i + 1,
            'score': float(scores[0][i]),
            'doc_id': m['meta'].get('doc_id'),
            'date': m['meta'].get('date', '')[:10],
            'doc_type': m['meta'].get('doc_type'),
            'text': m['text'],
        })
    return chunks


def _ollama(model: str, prompt: str, max_tokens: int, temperature: float):
    r = requests.post(OLLAMA_URL, json={
        'model': model, 'prompt': prompt, 'stream': False,
        'options': {'num_predict': max_tokens, 'temperature': temperature, 'top_p': 0.9},
    }, timeout=180)
    r.raise_for_status()
    return r.json()['response']


@app.get('/')
def health():
    return {'status': 'ok', 'personas': list(PERSONAS.keys())}


@app.get('/personas')
def personas():
    return {p: {'chunks': len(PERSONAS[p]['meta'])} for p in PERSONAS}


@app.post('/ask')
def ask(req: AskRequest):
    if req.persona not in PERSONAS:
        raise HTTPException(404, f'persona {req.persona} not loaded; have {list(PERSONAS)}')

    chunks = _retrieve(req.persona, req.question, req.k)
    sources_block = '\n\n'.join(
        f"[Source {c['rank']}] {c['doc_id']} ({c['date']})\n{c['text']}" for c in chunks
    )
    prompt = (
        f"Answer using ONLY the source documents. Cite [Source N] inline after each fact.\n\n"
        f"QUESTION: {req.question}\n\nSOURCES:\n{sources_block}"
    )
    answer = _ollama(req.persona, prompt, req.max_tokens, 0.4)
    return {
        'persona': req.persona,
        'question': req.question,
        'answer': answer,
        'sources': [{k: v for k, v in c.items() if k != 'text'} for c in chunks],
    }


@app.post('/voice_only')
def voice_only(req: VoiceOnlyRequest):
    if req.persona not in PERSONAS:
        raise HTTPException(404, f'persona {req.persona} not loaded')
    answer = _ollama(req.persona, req.prompt, req.max_tokens, 0.5)
    return {'persona': req.persona, 'answer': answer}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='::', port=8000)
