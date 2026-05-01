"""
Telegram bot that wraps the persona RAG + Ollama pipeline.

Usage:
    pip install python-telegram-bot==21.6 sentence-transformers faiss-cpu requests
    export TELEGRAM_TOKEN="123456:ABC..."   # paste the BotFather token
    python telegram_bot.py

In Telegram:
    /start           → welcome
    /priya <question> → ask Priya (RAG)
    /rohan <question> → ask Rohan (RAG)
    plain text        → defaults to /priya

The bot uses long-polling — no webhook, no cloudflared, no public URL needed.
"""

import json
import os
import logging
from pathlib import Path

import requests
import faiss
from sentence_transformers import SentenceTransformer

from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- Config ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise SystemExit('Set TELEGRAM_TOKEN env var (paste your BotFather token).')

DRIVE = Path(os.environ.get('PROJECT_ROOT',
    '/Users/kader/Library/CloudStorage/GoogleDrive-pentesterrepo202@gmail.com/My Drive/Projects/ProjectRecall'))
DATA = DRIVE / 'training/data'
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/generate')

# --- Logging ---
logging.basicConfig(format='%(asctime)s %(name)s [%(levelname)s] %(message)s', level=logging.INFO)
log = logging.getLogger('persona-bot')

# --- Load embedder + indexes once at startup ---
log.info('Loading embedder + indexes...')
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
        log.info('  loaded %s: %d chunks', p, len(PERSONAS[p]['meta']))

if not PERSONAS:
    raise SystemExit(f'No persona indexes found in {DATA}.')


def ask(persona: str, question: str, k: int = 8, max_tokens: int = 700) -> tuple[str, list]:
    """Retrieve top-k, call Ollama, return (answer, sources)."""
    p = PERSONAS[persona]
    e = embedder.encode([question], normalize_embeddings=True).astype('float32')
    scores, idxs = p['index'].search(e, k)
    sources = []
    chunks_block = []
    for i, j in enumerate(idxs[0]):
        if j < 0: continue
        m = p['meta'][j]['meta']
        sources.append({
            'rank': i + 1,
            'score': float(scores[0][i]),
            'doc_id': m.get('doc_id', '?'),
            'date': m.get('date', '')[:10],
        })
        chunks_block.append(
            f"[Source {i+1}] {m.get('doc_id','?')} ({m.get('date','')[:10]})\n{p['meta'][j]['text']}"
        )
    prompt = (
        f"Answer using ONLY the source documents. Cite [Source N] inline after each fact.\n\n"
        f"QUESTION: {question}\n\nSOURCES:\n" + "\n\n".join(chunks_block)
    )
    r = requests.post(OLLAMA_URL, json={
        'model': persona, 'prompt': prompt, 'stream': False,
        'options': {'num_predict': max_tokens, 'temperature': 0.4, 'top_p': 0.9},
    }, timeout=180)
    r.raise_for_status()
    return r.json()['response'].strip(), sources


def format_reply(persona: str, answer: str, sources: list) -> str:
    """Telegram-flavoured Markdown."""
    lines = [f"*{persona}:*", "", answer, ""]
    if sources:
        lines.append("*Sources:*")
        for s in sources[:5]:
            lines.append(f"• `{s['doc_id']}` ({s['date']}) — score {s['score']:.2f}")
    text = "\n".join(lines)
    # Telegram caps messages at 4096 chars
    return text[:4000] + ("\n\n_[truncated]_" if len(text) > 4000 else "")


# --- Handlers ---

async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi — I'm a persona AI trained on Priya (CSM) and Rohan (Staff Eng).\n\n"
        "*Commands:*\n"
        "`/priya <question>` — ask Priya\n"
        "`/rohan <question>` — ask Rohan\n"
        "Plain text — defaults to Priya\n\n"
        "*Examples:*\n"
        "• What happened with Acme Corp?\n"
        "• /rohan Why are we using Postgres for events?\n"
        "• /priya Why did Rekall churn?",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, ctx)


async def _handle(update: Update, persona: str, question: str):
    if not question.strip():
        await update.message.reply_text(f"Ask me something. Example: `/{persona} What happened with Acme?`",
                                        parse_mode=constants.ParseMode.MARKDOWN)
        return
    log.info('[%s] @%s: %s', persona, update.effective_user.username or 'anon', question)
    msg = await update.message.reply_text(f"_Asking {persona} about: *{question}* ..._",
                                           parse_mode=constants.ParseMode.MARKDOWN)
    try:
        answer, sources = ask(persona, question)
        text = format_reply(persona, answer, sources)
        await msg.edit_text(text, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        log.exception('error')
        await msg.edit_text(f"💥 Error: `{e}`", parse_mode=constants.ParseMode.MARKDOWN)


async def cmd_priya(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _handle(update, 'priya', ' '.join(ctx.args))


async def cmd_rohan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _handle(update, 'rohan', ' '.join(ctx.args))


async def on_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    await _handle(update, 'priya', update.message.text or '')


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(CommandHandler('priya', cmd_priya))
    app.add_handler(CommandHandler('rohan', cmd_rohan))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info('Bot started — connect in Telegram, send /start')
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
