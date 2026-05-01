#!/usr/bin/env python3
"""
Persona Q&A — interactive CLI version of ask.ipynb.

Two modes per question:
  • RAG  (default)         — retrieves top-k chunks, cited answer in persona voice
  • voice (--voice / :v)   — no retrieval, just the persona's voice on the prompt

Usage
-----
    # interactive REPL (default)
    python ask.py

    # specific persona
    python ask.py --persona rohan

    # one-shot question
    python ask.py -q "What happened with Acme Corp?"

    # voice-only one-shot
    python ask.py --voice -q "Draft a reply asking Sarah for a 15-min Q2 review."

REPL commands
-------------
    :v <prompt>      voice-only mode for this prompt (no retrieval)
    :p <persona>     switch persona (priya / rohan)
    :k <number>      change retrieval k (default 8)
    :sources         toggle source listing
    :h / :help       help
    :q / Ctrl-D      quit

Prereqs
-------
    1. Ollama running with the persona model registered:
           ollama serve &
           ollama create priya -f Modelfile.priya
    2. FAISS index files at ../training/data/rag_index_<persona>.faiss
    3. pip install requests faiss-cpu sentence-transformers
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
import faiss
from sentence_transformers import SentenceTransformer


# ---------- Config ----------

DEFAULT_DRIVE = Path(
    os.environ.get(
        'PROJECT_ROOT',
        '/Users/kader/Library/CloudStorage/GoogleDrive-pentesterrepo202@gmail.com/'
        'My Drive/Projects/ProjectRecall',
    )
)
DEFAULT_DATA = DEFAULT_DRIVE / 'training/data'
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434/api/generate')
EMBED_MODEL = 'BAAI/bge-base-en-v1.5'


# ---------- Loaders ----------

class PersonaIndex:
    """Holds the FAISS index + chunk metadata for one persona."""

    def __init__(self, persona: str, data_dir: Path):
        self.persona = persona
        idx_path = data_dir / f'rag_index_{persona}.faiss'
        meta_path = data_dir / f'rag_meta_{persona}.jsonl'
        if not idx_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f'Missing index/meta for {persona!r} in {data_dir}'
            )
        self.index = faiss.read_index(str(idx_path))
        self.meta = [json.loads(l) for l in meta_path.open()]

    def __len__(self) -> int:
        return len(self.meta)


# ---------- Inference ----------

def call_ollama(model: str, prompt: str, max_tokens: int, temperature: float) -> str:
    r = requests.post(
        OLLAMA_URL,
        json={
            'model': model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'num_predict': max_tokens,
                'temperature': temperature,
                'top_p': 0.9,
            },
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()['response']


def ask(
    question: str,
    embedder,
    pidx: PersonaIndex,
    k: int = 8,
    max_tokens: int = 800,
    show_sources: bool = True,
):
    """RAG + Ollama. Retrieves top-k, asks the persona to answer with citations."""
    e = embedder.encode([question], normalize_embeddings=True).astype('float32')
    scores, idxs = pidx.index.search(e, k)

    sources = []
    chunks_block = []
    for i, j in enumerate(idxs[0]):
        if j < 0:
            continue
        m = pidx.meta[j]['meta']
        sources.append({
            'rank': i + 1,
            'score': float(scores[0][i]),
            'doc_id': m.get('doc_id', '?'),
            'date': m.get('date', '')[:10],
        })
        chunks_block.append(
            f"[Source {i+1}] {m.get('doc_id','?')} ({m.get('date','')[:10]})\n"
            f"{pidx.meta[j]['text']}"
        )

    prompt = (
        'Answer using ONLY the source documents. Cite [Source N] inline after each fact.\n\n'
        f'QUESTION: {question}\n\nSOURCES:\n' + '\n\n'.join(chunks_block)
    )
    answer = call_ollama(pidx.persona, prompt, max_tokens, 0.4)

    print('\n' + '=' * 70)
    print(f'ANSWER  [persona: {pidx.persona}, mode: RAG, k={k}]')
    print('=' * 70)
    print(answer)
    if show_sources:
        print('\n' + '-' * 70)
        print('SOURCES')
        print('-' * 70)
        for s in sources:
            print(f"  [{s['rank']}] {s['doc_id']:<40s} {s['date']}  score={s['score']:.3f}")
    print()
    return answer


def voice_only(
    prompt: str,
    pidx: PersonaIndex,
    max_tokens: int = 400,
    temperature: float = 0.5,
):
    """Direct call to Ollama, no RAG. Use for drafting tasks."""
    answer = call_ollama(pidx.persona, prompt, max_tokens, temperature)
    print('\n' + '=' * 70)
    print(f'ANSWER  [persona: {pidx.persona}, mode: voice-only]')
    print('=' * 70)
    print(answer)
    print()
    return answer


# ---------- REPL ----------

REPL_HELP = """
Commands:
  :v <prompt>      voice-only mode for this prompt (no retrieval)
  :p <persona>     switch persona (priya / rohan)
  :k <number>      change retrieval k (default 8)
  :sources         toggle source listing
  :h / :help       this help
  :q / Ctrl-D      quit

Anything else is treated as a RAG question to the active persona.
"""


def run_repl(persona: str, data_dir: Path, k: int = 8):
    print(f'Loading embedder ({EMBED_MODEL})...')
    embedder = SentenceTransformer(EMBED_MODEL)

    print(f'Loading {persona} index from {data_dir}...')
    pidx = PersonaIndex(persona, data_dir)
    print(f'Ready: {len(pidx):,} chunks indexed.')
    print(f"Type a question, or :h for commands, :q to quit.\n")

    show_sources = True
    while True:
        try:
            line = input(f'[{pidx.persona}] > ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue

        # Commands
        if line in (':q', ':quit', ':exit'):
            break
        if line in (':h', ':help'):
            print(REPL_HELP)
            continue
        if line == ':sources':
            show_sources = not show_sources
            print(f'sources: {show_sources}')
            continue
        if line.startswith(':p '):
            new_persona = line[3:].strip()
            try:
                pidx = PersonaIndex(new_persona, data_dir)
                print(f'switched to {pidx.persona} ({len(pidx):,} chunks)')
            except FileNotFoundError as e:
                print(f'!! {e}')
            continue
        if line.startswith(':k '):
            try:
                k = int(line[3:].strip())
                print(f'k = {k}')
            except ValueError:
                print('!! :k expects a number')
            continue
        if line.startswith(':v '):
            voice_only(line[3:].strip(), pidx)
            continue

        # default: RAG
        try:
            ask(line, embedder, pidx, k=k, show_sources=show_sources)
        except requests.RequestException as e:
            print(f'!! Ollama call failed: {e}')


# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(
        description='Persona Q&A — RAG + LoRA via Ollama.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument('--persona', '-p', default='priya', help='priya | rohan')
    ap.add_argument('--data-dir', default=str(DEFAULT_DATA),
                    help=f'FAISS + meta directory (default: {DEFAULT_DATA})')
    ap.add_argument('--question', '-q', default=None, help='Run a single question and exit')
    ap.add_argument('--voice', action='store_true',
                    help='With -q: voice-only mode (no retrieval)')
    ap.add_argument('--k', type=int, default=8, help='Retrieval k (default: 8)')
    ap.add_argument('--no-sources', action='store_true',
                    help='Hide source listing')
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        sys.exit(f'!! data dir not found: {data_dir}')

    # One-shot
    if args.question is not None:
        print(f'Loading embedder + {args.persona} index...')
        embedder = SentenceTransformer(EMBED_MODEL)
        pidx = PersonaIndex(args.persona, data_dir)
        if args.voice:
            voice_only(args.question, pidx)
        else:
            ask(args.question, embedder, pidx, k=args.k,
                show_sources=not args.no_sources)
        return

    # Interactive
    run_repl(args.persona, data_dir, k=args.k)


if __name__ == '__main__':
    main()
