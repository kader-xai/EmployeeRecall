<p align="center">
  <img src="docs/images/logo.png" alt="Employee Recall" width="220">
</p>

<h1 align="center">Employee Recall</h1>

<p align="center">A persona-continuity LoRA + RAG pipeline. Synthetic dataset, full reproduction recipe, runs on a laptop.</p>

<p align="center">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <a href="LICENSE"><img alt="Corpus" src="https://img.shields.io/badge/corpus-CC0-lightgrey.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-3776AB.svg">
</p>

---

## What this is

When a senior employee leaves, two things go with them: how they wrote, and what they knew. Onboarding docs cover neither.

This repo is a working recipe for capturing both as a small, locally-runnable model:

- A LoRA adapter trained on the persona's reply pairs holds the **voice**.
- A FAISS index over their corpus holds the **knowledge**.
- A short system prompt holds the **identity**.

At inference time the three are stitched together: retrieve top-k chunks, hand them to the fine-tuned model with `[Source N]` labels, return a cited reply in the persona's voice.

The corpus is fully synthetic — no real employee data is used or required. Two demo personas ship with the repo (Priya, Senior CSM; Rohan, Staff Engineer). Swap them out for your own and re-run.

---

## Capabilities at a glance

### Synthetic data

- Hand-authored persona fingerprints (tone, vocab, decision style, response cadence, internal relationships, quirks).
- Three-tier corpus: hand-written storylines (depth) + dense per-account/project (realism) + bulk routine (volume).
- 18,978 documents across 4 simulated years, fully deterministic (`random.seed(42)` — same output on every run).
- Multi-format extraction: same content rendered to `.eml` / `.html` / `.ics` / `.vtt` / `.md` / `.txt` for demos that need real mailbox or calendar files.
- Cross-persona storylines: the same incident appears in both Priya's customer-comms history and Rohan's engineering postmortems.

### Training

- LoRA fine-tuning on Qwen2.5-7B (or 3B for free-tier Colab) via Unsloth + PEFT + TRL.
- 4-bit base load with bitsandbytes; rank-16 adapters on all attention + MLP linear layers.
- Training pipeline: prep → embed → train → merge → quantise. Runs end-to-end on a single A100 in ~30 minutes for ~$0.25.
- Per-persona output: ~150 MB LoRA adapter + ~75 MB FAISS index + ~4.5 GB Q4_K_M GGUF.
- Built-in 95/5 SFT train/eval split, deterministic.

### Retrieval

- BGE-base-en-v1.5 embedder, 768-dim, L2-normalised.
- FAISS `IndexFlatIP` (exact cosine search). Sub-5 ms per query for ~17k chunks.
- Type-aware chunking: emails kept whole, meetings split by section, RFCs split by markdown heading.
- Citations injected via `[Source N]` labels in the prompt; model is instructed to cite inline.
- Per-chunk metadata (doc_id, date, doc_type, related_account / related_project) preserved for provenance.

### Inference

- Three modes:
  - **RAG-grounded `ask()`** — retrieve top-k chunks and answer with citations.
  - **Voice-only `voice_only()`** — bypass retrieval for drafting tasks; voice intact via system prompt.
  - **Pure RAG (no LoRA)** — skip fine-tuning entirely for the safest deployment.
- Runs on Apple Silicon Metal via Ollama after merging + quantising the LoRA.
- Sub-second retrieval; ~5–15 s end-to-end per question on a Mac M-series.
- The same `ask()` logic available three ways:
  - Jupyter notebook (`local_inference/ask.ipynb`)
  - REST API with auto-generated Swagger docs (`local_inference/api.py` → `http://localhost:8000/docs`)
  - Single-script bot

### Integrations

- **Slack** via n8n + Cloudflare tunnel — slash commands `/ask-priya` and `/ask-rohan` reply in-channel with cited answers in seconds.
- **Telegram** via `python-telegram-bot` — one self-contained script using long-polling (no webhook or tunnel needed).
- **n8n importable workflow** with parallel ack-then-call pattern that meets Slack's 3-second response window.
- **FastAPI REST endpoints** (`/ask`, `/voice_only`, `/personas`, `/`) for any custom integration.
- Drop-in support for Cloudflared (recommended) or ngrok tunnels.

### Deployment patterns

The same pipeline supports a spectrum of deployments — pick by how personal the training data is:

| Pattern | LoRA | RAG | Risk |
|---|---|---|---|
| Pure company RAG | none | all docs | low — safest first deployment |
| Onboarding tutor | company brand voice | onboarding handbook | low |
| Role persona | aggregate of all CSMs | new hire's accounts | medium — depersonalised |
| Departing employee twin | one specific person | their corpus | high — needs full consent |
| Public digital twin | one public figure | their published work | very high — heavy legal review |

### Evaluation

- Automated `eval.py` runs two metrics: history keyword recall (against gold answers) and style cosine similarity (against held-out replies).
- Per-question gold answers in `training/eval_questions.json` — extend with your own.
- Output written to `training/eval_results_<persona>.json` and `.md` for tracking across runs.

### Reproducibility

- Deterministic seeded generators — anyone can rebuild the corpus byte-identical.
- Saved SFT pairs alongside trained adapters — anyone can audit what data the model was trained on.
- Fully open: code under MIT, synthetic content under CC0, no proprietary tooling required.
- One-click Colab notebook: clone → open → Runtime → Run All.

### Privacy and governance hooks

- `.gitignore` excludes secrets, model artifacts, and Drive-sync duplicates by default.
- Documented patterns for: PII redaction at ingest, access-control tagging, citation thresholds, memorisation auditing, sunset planning, mandatory output disclaimers.
- Designed to be retired cleanly: corpus + adapter + index + checkpoints can all be purged together.

---

## Repo layout

```
personas/         persona JSON fingerprints (tone, vocab, decisions)
cast/             internal characters
accounts/         customer portfolio (40 accounts)
projects/         engineering projects (14)
corpus/           18,978 synthetic JSONL documents over 4 years
scripts/          deterministic corpus generators (seed=42)
training/         prep, train, RAG index, inference, eval, Colab notebook
local_inference/  Mac deployment: FastAPI server, notebook, Telegram bot
methodology/      methodology notes, lecture deck, technical detail
```

| Persona | Role | Storylines |
|---|---|---|
| Priya Sharma | Senior CSM, 40 accounts, $4.2M ARR | Acme billing dispute, Globex RFP, Umbrella SOC2, Hooli incident, Rekall churn |
| Rohan Iyer | Staff Engineer, Platform team | Postgres-vs-Mongo decision, rate-limiter rewrite, GraphQL gateway killed, May 2024 outage |

---

## Example

```
> What happened with Acme Corp?
```

```
Thanks for the patience while I dug into this. The seat-count on Acme's
Q1 invoice came in 31 seats over (388 vs 357), about $14k. Mike Reyes
(CFO) pushed on this in a working session on March 4 [Source 1]. We
landed on a partial credit ($4.2k applied to Q2) and Sarah Lin's team
agreed to run quarterly seat-deactivation reviews going forward
[Source 2]. The renewal is mid-April; Mike was clear that the credit
conversation and the renewal conversation are linked from his side.

SOURCES
  [1] meeting-acme-001     2025-03-04   score=0.74
  [2] email-acme-003       2025-03-03   score=0.71
  [3] meeting-acme-1on1    2025-10-16   score=0.70
```

---

## Architecture

```
Base model (Qwen2.5-7B, frozen)
  + LoRA adapter (~150 MB, trained on 1,287 reply pairs)
  + FAISS index (~50 MB, 17,663 chunks, BGE-base embeddings)
  + System prompt (text fingerprint)
  = persona-continuity model
```

See [methodology/PRESENTATION.md](methodology/PRESENTATION.md) for the longer write-up.

---

## Try it

### Use the demo personas (Colab, ~30 min, ~$0.25)

```bash
git clone https://github.com/kader-xai/EmployeeRecall.git
```

Open `training/Persona_Continuity_Colab.ipynb` in Colab, set runtime to A100, Run All.

See [training/COLAB.md](training/COLAB.md).

### Train on your own persona

1. Copy `personas/priya.json` to `personas/yourname.json` and edit the fingerprint fields (`tone_profile`, `vocab_fingerprint`, `signature_patterns`, etc.).
2. Drop your corpus into `corpus/yourname/` as JSONL — schema example in [corpus/priya/storyline_acme.jsonl](corpus/priya/storyline_acme.jsonl).
3. Run:

```bash
python training/prep_training_data.py --persona yourname
python training/build_rag_index.py    --persona yourname
python training/train_lora.py         --persona yourname
python training/inference.py          --persona yourname --interactive
```

### RAG only (no fine-tuning)

Skip `train_lora.py`. The inference script will retrieve and cite using only the base model. Safer for sensitive corpora — no parametric memorisation.

---

## Local deployment after training

```bash
brew install ollama
ollama serve &

cd local_inference
ollama create priya -f Modelfile.priya
ollama run priya
```

For RAG-grounded answers, run [local_inference/ask.ipynb](local_inference/ask.ipynb) or:

```bash
pip install -r local_inference/requirements.txt
python local_inference/api.py        # FastAPI on :8000, Swagger at /docs
```

Telegram bot in [local_inference/telegram_bot.py](local_inference/telegram_bot.py); n8n + Slack workflow in [local_inference/SLACK_N8N_SETUP.md](local_inference/SLACK_N8N_SETUP.md).

---

## Footprint

| Layer | Size |
|---|---|
| Persona / cast / accounts / projects JSON | ~36 KB |
| Synthetic corpus JSONL | ~13 MB |
| Trained LoRA adapter | ~150 MB |
| FAISS index + metadata | ~75 MB |
| Quantised GGUF (Q4_K_M) | ~4.5 GB |

Total per persona on disk after deploy: ~5 GB.

---

## Cost

| Step | Where | Time | Cost |
|---|---|---|---|
| Generate corpus | local | ~30s | $0 |
| Prep / index | local | ~1 min | $0 |
| LoRA fine-tune | Colab A100 | ~30 min | ~$0.25 |
| Merge + GGUF + quantise | Colab A100 | ~10 min | ~$0.10 |
| Daily inference | Mac | — | $0 |

---

## Deployment patterns

The same pipeline supports a range of deployments. Choose by how personal the training data is:

| Pattern | LoRA | RAG | Use for |
|---|---|---|---|
| Pure company RAG | none | all docs | Safest first deployment |
| Onboarding tutor | company brand voice | onboarding docs | New-hire ramp |
| Role persona | aggregate of all CSMs | new hire's accounts | Avoids cloning a specific person |
| Departing employee twin (this demo) | one person | their corpus | Senior succession; needs full consent |
| Public digital twin | one public figure | their published work | Personal-brand bot; needs heavy legal review |

---

## Privacy and consent

The demo corpus is fictional. For real deployment with real employees:

- Get written consent from the persona, scoped to specific corpora and successor users.
- Set a sunset date or condition for the model.
- Redact PII at ingest (Microsoft Presidio or similar).
- Tag every document with a clearance tier; filter retrieval per asker.
- Log every query, retrieval, and output.
- Run a memorisation audit before release (sample outputs, n-gram-check against training).
- Refuse to answer when no source exceeds a similarity threshold.
- Add a disclaimer to every output: "Drafted in the voice of X by an AI; not authored by X."

The technical pipeline is the easy part. Governance is the rest.

---

## Demo questions

Priya:

- What happened with Acme Corp?
- Why did we credit Acme $4,200 in Q1 2025?
- What's the renewal posture for Globex?
- Why did Rekall churn?
- Who is Mike Reyes and how should I handle him?
- What was the May 2025 Hooli incident from the customer side?

Rohan:

- Why are we using Postgres for events instead of MongoDB?
- What was the May 2024 incident?
- Why did we kill the GraphQL gateway?
- What's the trigger to revisit ClickHouse?
- What does ADR-0023 say?

Cross-persona: ask both *"What was the May 2025 Hooli incident?"* — Priya answers from the customer-comms angle, Rohan from the root-cause angle.

---

## Stack

| Layer | Tool |
|---|---|
| Base model | [Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) |
| LoRA training | [Unsloth](https://github.com/unslothai/unsloth) + [PEFT](https://github.com/huggingface/peft) + [TRL](https://github.com/huggingface/trl) |
| 4-bit base loading | [bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes) |
| Embeddings | [BGE-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5) |
| Vector index | [FAISS](https://github.com/facebookresearch/faiss) |
| GGUF conversion | [llama.cpp](https://github.com/ggerganov/llama.cpp) |
| Local inference | [Ollama](https://ollama.com) |
| API | [FastAPI](https://fastapi.tiangolo.com) |
| Workflow / Slack | [n8n](https://n8n.io) |

---

## License

Code: MIT. Synthetic corpus and persona JSON: Creative Commons CC0. All persons, accounts, and events depicted are fictional.

---

## References

- Hu et al., 2021 — [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685)
- Xiao et al., 2023 — [C-Pack: Packed Resources For General Chinese Embeddings (BGE)](https://arxiv.org/abs/2309.07597)
- Johnson et al., 2017 — [Billion-scale similarity search with GPUs (FAISS)](https://arxiv.org/abs/1702.08734)

---

## Author

**Kader M.**

- Website — [kader-xai.github.io](https://kader-xai.github.io)
- LinkedIn — [linkedin.com/in/kader-m-1a6023a6](https://linkedin.com/in/kader-m-1a6023a6)
- GitHub — [@kader-xai](https://github.com/kader-xai)

For questions, deployment war-stories, or to share what you built on top of this — feel free to reach out via LinkedIn or open an issue.
