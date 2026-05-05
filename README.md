<p align="center">
  <img src="docs/images/logo.png" alt="Employee Recall" width="220">
</p>

<h1 align="center">Employee Recall</h1>

<p align="center">An open recipe for capturing a departing employee's voice and memory in an AI successor.</p>

<p align="center">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <a href="LICENSE"><img alt="Corpus" src="https://img.shields.io/badge/corpus-CC0-lightgrey.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-3776AB.svg">
</p>

---

## The idea

When a senior employee leaves, two things go with them:

- **Voice** — how they wrote to customers, peers, executives.
- **Knowledge** — *why* they made the calls they made, what was promised, who's who.

Onboarding docs cover neither. This project is a working recipe for capturing both as a small, locally runnable model.

The architecture is two pieces glued together:

- A **LoRA adapter** trained on the persona's reply pairs holds the *voice*.
- A **FAISS vector index** over their corpus holds the *knowledge*.

At question time, retrieve the top relevant chunks from the index, hand them to the fine-tuned model with `[Source N]` labels, and return a cited reply in the persona's voice.

The repo ships with two synthetic demo personas — Priya (Senior CSM) and Rohan (Staff Engineer). Swap them out for your own and re-run.

---

## How training works

```
1. Persona JSON + corpus JSONL  ──►  prep_training_data.py
                                          │
                            ┌─────────────┴─────────────┐
                            ▼                           ▼
                     SFT pairs                    RAG chunks
                (incoming → reply)             (text + metadata)
                            │                           │
                            ▼                           ▼
                     train_lora.py             build_rag_index.py
                            │                           │
                            ▼                           ▼
                  LoRA adapter (~150 MB)        FAISS index (~50 MB)
                            │                           │
                            └─────────────┬─────────────┘
                                          ▼
                                   inference.py / ask.py
                                  (retrieve + generate)
```

Plain English:

1. **Prep** turns the corpus into two streams. Every email thread where the persona replied becomes one training pair (input = prior thread, target = persona's reply). Every document also gets chunked for retrieval.
2. **Train** fine-tunes Qwen2.5-7B with a tiny LoRA adapter on those pairs. Three epochs, ~30 minutes on an A100, ~$0.25 on Colab. The base model stays frozen; only the adapter learns the persona's style.
3. **Index** embeds every chunk with BGE-base-en-v1.5 and writes a FAISS index. Sub-5 ms search across ~17k chunks.
4. **Inference** pulls the top-k relevant chunks for a question, builds a prompt with `[Source N]` labels, sends it to Ollama (running the LoRA-merged model), and returns a cited answer.

The system prompt — set in the Ollama Modelfile — tells the model who it is impersonating.

---

## Files in this repo

```
personas/         persona JSON fingerprints (tone, vocab, decision style)
cast/             internal characters (~25 colleagues)
accounts/         customer portfolio (40 accounts)
projects/         engineering projects (14)
corpus/           18,978 synthetic JSONL documents over 4 simulated years
                  ├── priya/        emails, meetings, storylines
                  └── rohan/        emails, RFCs, ADRs, postmortems
scripts/          deterministic corpus generators (seed=42)

training/
  ├── prep_training_data.py     corpus → SFT pairs + RAG chunks
  ├── build_rag_index.py        chunks → FAISS index
  ├── train_lora.py             LoRA fine-tune (Colab / RunPod)
  ├── inference.py              RAG + generate, used by Colab
  ├── eval.py                   automated history + style scoring
  ├── eval_questions.json       gold demo questions
  ├── Persona_Continuity_Colab.ipynb     one-click Colab training
  ├── COLAB.md                  Colab quickstart
  └── RUNBOOK.md                cloud GPU training (RunPod / Vast)

local_inference/
  ├── api.py                    FastAPI server (Mac, port 8000)
  ├── ask.py                    interactive CLI
  ├── ask.ipynb                 interactive notebook
  ├── telegram_bot.py           Telegram bot (long-polling)
  ├── n8n_workflow.json         importable n8n workflow for Slack
  ├── Modelfile.priya           Ollama config for Priya GGUF
  ├── Modelfile.rohan           Ollama config for Rohan GGUF
  ├── SLACK_N8N_SETUP.md        Slack integration end-to-end
  └── requirements.txt

methodology/
  ├── METHODOLOGY.md            end-to-end methodology write-up
  ├── PRESENTATION.md           lecture deck (Marp)
  ├── CORPUS_TECHNICAL_DETAILS.md
  └── VIDEO_READING_NOTES.md    spoken script for video walkthrough
```

---

## Train a new persona

Overall Guide is available at https://github.com/kader-xai/EmployeeRecall/edit/main/README.md#:~:text=train%2Down%2D-,persona,-.md 

The system is fully parameterised. To train on your own person and corpus:

### 1. Create the persona fingerprint

Copy the template and edit:

```bash
cp personas/priya.json personas/yourname.json
```

Edit these fields in the new file:

- `id`, `full_name`, `email`, `role`, `company`
- `tone_profile` — register, verbosity, hedging style, humour
- `vocab_fingerprint` — phrases they reach for / phrases they avoid
- `signature_patterns` — greetings and sign-offs
- `decision_style` — how they say no, when they escalate
- `topics_owned` — what they're responsible for

The fields are documented inline in [`personas/priya.json`](personas/priya.json).

### 2. Add the corpus

Drop JSONL files into `corpus/yourname/`. Each line is one document:

```json
{
  "doc_id": "email-001",
  "doc_type": "email",
  "thread_id": "thread-42",
  "thread_position": 2,
  "date": "2024-06-15T10:00:00",
  "from": {"name": "Your Name", "email": "you@company.com"},
  "to":   [{"name": "Recipient", "email": "them@example.com"}],
  "subject": "Re: Project status",
  "body": "Quick context: ...",
  "tags": ["project-x", "status"]
}
```

Supported `doc_type` values: `email`, `meeting_notes`, `meeting_transcript`, `rfc`, `adr`, `postmortem`, `design_doc`. See [`corpus/priya/storyline_acme.jsonl`](corpus/priya/storyline_acme.jsonl) for full examples.

### 3. Run the pipeline

```bash
# 1. Prep — corpus → SFT pairs + RAG chunks
python training/prep_training_data.py --persona yourname

# 2. Build the FAISS index
python training/build_rag_index.py --persona yourname

# 3. Fine-tune the LoRA  (run on Colab A100, see training/COLAB.md)
python training/train_lora.py --persona yourname

# 4. Test it
python training/inference.py --persona yourname --interactive
```

For Colab, open [`training/Persona_Continuity_Colab.ipynb`](training/Persona_Continuity_Colab.ipynb), set runtime to A100, and Run All. ~30 minutes end-to-end.

The notebook also handles the merge → GGUF → quantise step that produces a portable model file (`yourname-q4_k_m.gguf`, ~4.5 GB) for local Mac inference.

---

## Run with RAG locally

After Colab produces the GGUF, run everything on your Mac.

### 1. Register the model with Ollama

```bash
brew install ollama
ollama serve &     # or open Ollama.app

cd local_inference

# Copy the GGUF from training output
cp ../training/yourname-q4_k_m.gguf .

# Paste the generated system prompt into Modelfile.<persona>
# (replace the SYSTEM "..." block with the contents of
#  ../training/data/system_prompt_yourname.txt)

ollama create yourname -f Modelfile.yourname
ollama list
```

### 2. Install Python deps

```bash
pip install -r requirements.txt
```

### 3. Ask questions

Three ways:

**Interactive CLI:**

```bash
python ask.py --persona yourname
[yourname] > What happened with Acme Corp?
```

REPL commands inside the prompt:
- `:v <prompt>` — voice-only mode (no retrieval, just drafts in the persona's voice)
- `:p <persona>` — switch persona
- `:k <number>` — change retrieval k (default 8)
- `:q` — quit

**Notebook:**

Open `local_inference/ask.ipynb` in VS Code or Jupyter, run cells top to bottom. Cell 1 loads the embedder + index; cell 2 defines `ask()`; cell 3 onward is `ask("...")` calls.

**REST API (for integrations):**

```bash
python api.py
# http://127.0.0.1:8000/docs   ← Swagger UI
```

POST `/ask` returns JSON with `answer` and `sources`. POST `/voice_only` returns a draft in the persona's voice without retrieval.

---

## Connect with Slack

Slack slash command → n8n → your local API → Ollama → reply in channel with citations.

Full setup in [`local_inference/SLACK_N8N_SETUP.md`](local_inference/SLACK_N8N_SETUP.md). Short version:

### 1. Run four things on your Mac

| Terminal | Command | What it does |
|---|---|---|
| 1 | `ollama serve` (or open Ollama.app) | Persona model |
| 2 | `cd local_inference && python api.py` | FastAPI on :8000 |
| 3 | `npm install -g n8n && n8n start` | Workflow engine on :5678 |
| 4 | `cloudflared tunnel --url http://localhost:5678` | Public HTTPS for Slack |

### 2. Import the workflow

Open `http://localhost:5678` → **Workflows → Import from File** → pick `local_inference/n8n_workflow.json`.

In the **Call Persona API** node, set the URL to `http://127.0.0.1:8000/ask`. Activate the workflow.

### 3. Create the Slack app

At <https://api.slack.com/apps> → **Create New App** → From scratch:

- **Slash Commands** → create `/ask-yourname` with Request URL = `https://<your-tunnel>.trycloudflare.com/webhook/slack-persona`
- **OAuth & Permissions** → add `chat:write` scope
- **Install to Workspace**

### 4. Try it

```
/ask-yourname What happened with Acme Corp?
```

Within ~10 seconds you should see a cited answer in the channel.

---

## License

- **Code** — MIT
- **Synthetic corpus and persona JSON** — Creative Commons CC0 (public domain)
- All persons, accounts, and events depicted are fictional.

See [LICENSE](LICENSE).

---

## Author

**Kader Mohideen**

- Website — [kader-xai.github.io](https://kader-xai.github.io)
- LinkedIn — [linkedin.com/in/kader-m-1a6023a6](https://linkedin.com/in/kader-m-1a6023a6)
- GitHub — [@kader-xai](https://github.com/kader-xai)
