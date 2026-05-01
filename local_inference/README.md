# Local inference

Run trained personas on a Mac via Ollama, with RAG-grounded citations, from a notebook or REST API.

## Files

| File | Purpose |
|---|---|
| `ask.ipynb` | Notebook for interactive Q&A |
| `api.py` | FastAPI wrapper around `ask()` |
| `telegram_bot.py` | Telegram bot |
| `n8n_workflow.json` | Importable n8n workflow for Slack integration |
| `Modelfile.priya`, `Modelfile.rohan` | Ollama model configs |
| `requirements.txt` | Python deps |
| `CODE_WALKTHROUGH.md` | `ask.ipynb` reference |
| `SLACK_N8N_SETUP.md` | Slack + n8n + Cloudflare end-to-end setup |

## Setup

### 1. Install Ollama

```bash
brew install ollama
ollama serve &        # or open Ollama.app
```

### 2. Drop the GGUFs in this folder

After running the conversion cells in the Colab notebook, the GGUFs land in `../training/`. Copy them next to the Modelfiles:

```bash
cp ../training/priya-q4_k_m.gguf .
# cp ../training/rohan-q4_k_m.gguf .
```

### 3. Set the persona system prompt in each Modelfile

The Modelfiles ship with a placeholder `SYSTEM` block. Replace with the generated system prompt:

```bash
sed -i '' "s|SYSTEM .*|SYSTEM \"\"\"$(cat ../training/data/system_prompt_priya.txt)\"\"\"|" Modelfile.priya
```

Or open `Modelfile.priya` and paste the contents of `../training/data/system_prompt_priya.txt` into the `SYSTEM """..."""` block.

### 4. Register the model with Ollama

```bash
ollama create priya -f Modelfile.priya
ollama list
```

### 5. Install Python deps

```bash
pip install -r requirements.txt
```

### 6. Open the notebook

```bash
code ask.ipynb
```

Select Python kernel → run cells top to bottom. After cell 2, every cell is `ask("...")`. Re-run with any question.

## Daily use

```python
ask("What happened with Acme Corp?")
```

The embedder loads in ~3 s; subsequent questions are 5–10 s on Apple Silicon.

## Switching persona

Edit cell 1 — change `PERSONA = 'priya'` to `'rohan'` and re-run cell 1.

## Voice-only mode

For drafting tasks where retrieval would add noise:

```python
voice_only("Draft a reply asking Sarah to schedule a Q2 review.")
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ConnectionError` on 11434 | Ollama not running. `ollama serve &` |
| `model 'priya' not found` | Run `ollama create priya -f Modelfile.priya` in this folder |
| Generic answers, no voice | Modelfile `SYSTEM` block still placeholder — replace with `system_prompt_priya.txt` |
| Slow first call | Ollama loading the model. Pre-warm: `ollama run priya 'hi'` |
| `ECONNREFUSED ::1:8000` | Use `127.0.0.1` not `localhost` in your code |
| Out of memory | 7B Q4_K_M needs ~6 GB RAM. Close other apps or use Q3_K_M (~3.8 GB) |

## Storage on disk

```
local_inference/
├── ask.ipynb
├── Modelfile.priya
├── priya-q4_k_m.gguf      ~4.5 GB after copy
└── ...

~/.ollama/models/          ~5 GB (Ollama-managed copy after `ollama create`)
```

You can delete the GGUF from this folder after `ollama create` — Ollama keeps its own copy.
