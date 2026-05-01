# Persona Continuity — Methodology

How to capture a departing employee's email + meeting history and turn it into an AI assistant that answers *"what happened with X?"* in their voice.

---

## The problem

Every time an experienced employee leaves, two things walk out the door:

1. **Style** — how they wrote, what tone they used with customers, how they said no diplomatically.
2. **History** — what was decided about Account X in 2023, why we picked Postgres over Mongo, who the champion was at Globex, what the open commitments are.

Org charts and ADRs capture the official version. The real institutional memory lives in their inbox and meeting notes.

This methodology shows how to capture both, in a way that's:
- **Consensual** (the employee agrees, in writing).
- **Auditable** (every model output is traceable to source documents).
- **Practical** (works on real mailbox formats: PST, Gmail Takeout, IMAP, Notion, Otter, Fathom, Zoom).
- **Local** (no customer data leaves the org).

---

## Architecture

We **do not** use a pure LoRA fine-tune. Pure LoRA is great at style but unreliable at facts — it will hallucinate dates and names. Instead:

```
question → retrieve relevant emails + meeting notes (vector DB)
        → feed retrieved docs + question into LoRA-tuned base model
        → answer in employee's voice, grounded in real history
        → return answer with source citations
```

| Need | Component |
|---|---|
| Sounds like the employee | LoRA fine-tune on (incoming → reply) pairs |
| Knows what happened | RAG retrieval over indexed mailbox + meeting corpus |
| Doesn't fabricate | Citations enforced — every claim must point to a source doc |
| Can be sunset cleanly | Single tenant, single corpus, retire on schedule |

### Components

- **Base model**: Qwen2.5-7B-Instruct or Llama-3.1-8B-Instruct.
- **Fine-tune**: LoRA `r=16, alpha=32` on attention + MLP projections.
- **Retrieval**: Sentence-Transformers (e.g. `all-MiniLM-L6-v2` or `BAAI/bge-base-en-v1.5`) → FAISS or Qdrant.
- **Re-ranker**: optional cross-encoder for top-k refinement.
- **Inference stack**: vLLM (server) + LangChain or LlamaIndex (orchestration).
- **UI**: Outlook/Gmail add-in, internal Slack bot, or a dedicated web app.

---

## Stage 1 — Consent & Scope (this is on screen for the video)

**Non-optional.** The single biggest reason this fails is consent and scope.

Required artifacts:
1. **Written consent** from the departing employee covering use of their mailbox + meeting archive for an AI assistant.
2. **Data minimization plan** — strip personal threads, redact PII (other people's contact data, financials, HR-sensitive content).
3. **Scope agreement** — model is **draft-only**, never auto-send, every output audit-logged.
4. **Retention policy** — when the LoRA + corpus retire after departure (recommended: 12 months, then archive only).
5. **Jurisdictional review** — GDPR (EU), CCPA (CA), India DPDP, HIPAA (if applicable to their work), GLBA (financial).
6. **Audit trail** — every model query and response is logged, attributable, and reviewable.

The video should explicitly call out that the synthetic Priya/Rohan corpus is fictional, with all consent steps simulated for demo purposes.

---

## Stage 2 — Data Extraction

Multiple parallel extractors.

### Email extractors
| Source | Tool | Output |
|---|---|---|
| Outlook PST/OST | `libpst` (`readpst`) | one .eml per message |
| Gmail | Google Takeout (.mbox) | mbox file |
| Exchange / O365 | `exchangelib` (Python) or Graph API | structured JSON |
| IMAP | `imap_tools` (Python) | structured JSON |

### Meeting extractors
| Source | Tool / format | Output |
|---|---|---|
| Notion | Notion API | Markdown |
| Confluence | Confluence REST API | XHTML → Markdown |
| Google Docs | Drive API + Docs API | structured JSON |
| OneNote | Graph API | XML → Markdown |
| Otter.ai | Otter export | .txt + .vtt |
| Fireflies | Fireflies API | structured JSON + .vtt |
| Fathom | Fathom export | structured JSON |
| Zoom | Cloud recording → transcript .vtt | .vtt + summary |
| Microsoft Teams | Graph API → Teams Copilot transcripts | structured JSON |
| Apple Notes / OneNote (manual) | apple-notes-exporter, OneNote SDK | text + image OCR |

### Normalizer
All extractors feed a single Python pipeline that produces JSONL in this schema:

```jsonc
{
  "doc_id": "...",
  "doc_type": "email" | "meeting_notes" | "transcript" | "rfc" | "adr" | "postmortem",
  "format": "structured" | "transcript" | "quick_notes" | "design_doc",
  "thread_id": "...",          // for emails
  "thread_position": 1,        // for emails
  "date": "ISO-8601",
  "from": {"name": "...", "email": "..."},   // emails
  "to": [...], "cc": [...],
  "subject": "...",
  "body": "...",
  "attendees": [{"name": "...", "company": "..."}],   // meetings
  "duration_min": 30,                                 // meetings
  "agenda": [...], "discussion": "...",
  "decisions": [...], "action_items": [...],
  "transcript_segments": [{"t": "...", "speaker": "...", "text": "..."}],
  "raw_body": "...",                                  // quick notes
  "related_threads": [...], "related_account": "...", "related_project": "...",
  "tags": [...]
}
```

This is the same schema the synthetic corpus uses — so the methodology is end-to-end testable on the synthetic data.

### Privacy filters (apply before training)
- Drop messages tagged `personal:*` in mailbox metadata.
- Run PII detection (e.g. Microsoft Presidio) and redact phone numbers, SSNs, government IDs, financial account numbers, salaries.
- Drop messages from senders the employee blocked or filtered.
- Honor any "do not retain" tags the employee applies during the export review.

---

## Stage 3 — Persona Profiling

Before training, extract a **persona fingerprint** from the corpus. Stored as JSON, used both at training time (for filtering/weighting) and at inference time (in the system prompt).

Components:
- **Tone register** (warm-professional, terse-direct, formal, casual, etc.) — derived from style classifier.
- **Greeting/sign-off patterns** — top-K extracted via simple regex over outgoing messages.
- **Sentence statistics** — average length, exclamation density, hedging frequency.
- **Vocabulary fingerprint** — top filler phrases, characteristic constructions, avoided phrases.
- **Decision style** — extracted by tagging messages with action-types (escalate, push back, defer, commit) and computing distribution.
- **Response latency profile** — median time-to-reply by recipient type, hour-of-day distribution.
- **Topic ownership** — top-K customers, projects, themes by message volume.
- **Internal relationships** — who they emailed most, who they cc'd, who they cross-referenced in meeting notes.

See `personas/priya.json` and `personas/rohan.json` for the concrete shape.

The persona profile is also a great visual artifact for the video — show it on screen as a "fingerprint."

---

## Stage 4 — Dataset Construction

Build training data from the corpus. Two complementary slices.

### Slice A — style fine-tune pairs (LoRA training)

Each pair: `(incoming context → outgoing reply by employee)`.

Source: emails where the employee replied. Filter to messages where the employee actually authored the reply (not forwarded, not auto-reply).

```jsonc
{
  "incoming": {"from": "...", "subject": "...", "body": "...", "thread_history": [...]},
  "context": {"persona_profile": {...}, "relationship": "external_client|internal_peer|leadership", "thread_age_days": 2},
  "reply": "..."
}
```

Target volume: **5,000–20,000 pairs**. LoRA training on 5k well-curated pairs beats 50k noisy ones.

Categories to balance (each ~8–12% of the dataset):
1. Quick acknowledgments
2. Detailed explanations / customer FAQ
3. Internal coordination
4. Escalations / pushback
5. Status updates to leadership
6. Saying no diplomatically
7. Cross-functional clarifications
8. Calendar/meeting negotiation
9. Out-of-scope / forwarding
10. Personal warmth (birthdays, condolences, congrats)

### Slice B — RAG retrieval index (history recall)

Every doc in the corpus → chunked → embedded → indexed.

Chunking strategy:
- **Emails** — chunked by message (one chunk per email, with a small thread-context preamble).
- **Meeting notes** — chunked by section (decisions, action items, discussion are separate chunks).
- **Transcripts** — chunked by ~5–10 segment windows, with speaker context preserved.
- **RFCs/ADRs** — chunked by heading, with title + author preamble.

Boost weights:
- `decisions` and `action_items` sections weighted 2x in retrieval.
- Recent docs weighted 1.5x for the first 6 months after ingest, decaying.
- Docs the employee authored weighted 1.3x over docs they only received.

---

## Stage 5 — Training

### LoRA configuration
```yaml
base_model: Qwen/Qwen2.5-7B-Instruct  # or Llama-3.1-8B-Instruct
lora:
  r: 16
  alpha: 32
  target_modules: [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj]
  dropout: 0.05
training:
  epochs: 2-3
  learning_rate: 2e-4
  scheduler: cosine
  max_seq_length: 4096
  per_device_batch_size: 4
  gradient_accumulation_steps: 4
  bf16: true
  flash_attn: true
data:
  format: chat (system / user / assistant)
  system_prompt_template: |
    You are KaliCoach... (substitute persona-aware prompt)
```

System prompt at training time injects the persona profile so the model learns to produce replies *given that fingerprint*. At inference time the same system prompt is used.

### Compute & cost
- 1× A100 40GB or 2× RTX 4090 — 6–12 hours for 10k pairs at 3 epochs.
- Cost on RunPod / Vast: **$15–35 total** for the demo dataset.

### Data efficiency
With 10k high-quality pairs, expect:
- Style match (vs base model) on held-out: substantial.
- Factual accuracy on un-RAG questions: **poor** — this is by design. Facts come from RAG.

---

## Stage 6 — Evaluation

Three test types; all should land in the demo video.

### 6.1 Style match (LoRA quality)
- Hold out 5% of email pairs.
- For each held-out pair: run the model with the same incoming context, compare generated reply to the actual reply.
- Metrics:
  - Embedding cosine similarity (Sentence-Transformers).
  - BLEU-4 (rough but useful).
  - Stylometric match: sentence length distribution, vocab overlap, sign-off match.
- Report median + 25th/75th percentile.

### 6.2 History recall (RAG quality)
- Hand-craft **30 questions** across the corpus that have specific factual answers ("What was the credit amount on the Acme Q1 dispute?", "Why did we kill the GraphQL gateway?", "Who owns rate limiter v2.1?").
- For each: model answer compared against ground-truth answer + cited sources.
- Metrics:
  - **Citation precision** — % of cited docs that actually contain the answer.
  - **Citation recall** — % of relevant docs that were cited.
  - **Answer correctness** — manual grade 1–5.
  - **Hallucination rate** — % of answers containing facts not in cited docs.

### 6.3 Blind human eval (the video money shot)
- Show 10 colleagues 10 question/answer pairs each.
- For each pair, two answers — one is the model, one is the actual employee's known reply or document.
- Ask: *which is which?*
- If colleagues are at chance (50%), the model has captured the voice convincingly.

---

## Stage 7 — Deployment

### Surface
- **Outlook add-in** / **Gmail add-in** / **Slack bot** — "Suggest draft in [Employee]'s voice" button. Always opens a draft, never auto-sends.
- **Web app** — search-style: ask a question, get an answer with citations. For the "what happened with X?" use case.

### Backend
- Local: Ollama or vLLM. No customer data leaves the org.
- Optional VPC deployment (AWS/GCP/Azure) for orgs that don't want on-prem.

### Audit logging
- Every query logged: timestamp, user, question, retrieved doc IDs, model output.
- Logs queryable by the security team or the original employee (if they want oversight).

### Sunset
- Pre-agreed retirement date in the consent doc.
- Recommended default: 12 months active, 12 months read-only archive, then deletion.
- Final report at retirement: usage stats, value delivered, anything to extract permanently into team documentation.

---

## Two Real Use Cases We Demonstrate

### Use Case 1 — Customer Account Continuity
**Persona**: Priya Sharma, Senior CSM at Northwind SaaS, 40-account portfolio, 3-year tenure, departing Dec 2025.
**User**: Arjun Mehta, her successor.
**Demo question**: *"What happened with Acme Corp?"*
**Expected answer**: Multi-year timeline — Q1 2025 billing dispute, $4.2k credit, renewal terms change, Q3 Premium upgrade, contact map, handoff posture for the next renewal cycle. With citations to 12+ emails and 5 meeting notes.

### Use Case 2 — Engineering Decision Memory
**Persona**: Rohan Iyer, Staff Engineer (Platform), 5-year tenure, departing Dec 2025.
**User**: Maya Williams, his successor as Tech Lead.
**Demo question**: *"Why are we using Postgres for the events service instead of MongoDB?"*
**Expected answer**: 2023 RFC outcome — relational join requirements, 2022 billing-off-Mongo migration scars, ClickHouse as future contingency above 50M/day, citations to ADR-0017 + the architecture review meeting + the email threads.

Both demonstrate the same architecture and pipeline.

---

## File Map

```
persona-continuity/
├── personas/
│   ├── priya.json            # CSM persona fingerprint
│   └── rohan.json            # Staff Engineer persona fingerprint
├── cast/internal.json        # all internal characters
├── accounts/priya_accounts.json  # 40 customer accounts
├── projects/rohan_projects.json  # 14 engineering projects
├── corpus/
│   ├── priya/                # emails + meetings + storylines
│   └── rohan/                # emails + meetings + RFCs + postmortems
├── extraction_output/        # PST-extraction-style multi-format files (.eml, .html, .ics, .vtt, .md)
├── scripts/
│   ├── generate_bulk_corpus.py
│   ├── generate_bulk_corpus_v2.py
│   └── inflate_to_real_extraction.py
└── methodology/
    └── METHODOLOGY.md  ← you are here
```

---

## What's NOT in this methodology (and why)

- **Auto-send** — never. The model drafts; humans send.
- **Cloud LLM inference** — incompatible with most NDAs and several jurisdictions. Local-only is a feature.
- **Full impersonation outside the inbox** — we model writing style + history. We don't model voice, video, or behavioral simulation. Out of scope and ethically dubious.
- **Cross-employee corpus mixing** — each LoRA is per-departing-employee. Mixing voices produces unconvincing output and complicates consent.

---

## Notes on the synthetic data

The corpus shipped under `corpus/` and `extraction_output/` is **synthetic**. All names, accounts, and events are fictional. Generation pipelines are reproducible (seed 42 / seed 2026).

For a real deployment:
- Volume scales naturally — a senior employee with 5 years of tenure and active inbox usage typically extracts to **1–3 GB** of plaintext (10–30 GB after HTML/headers/attachments). Our 44 MB synthetic corpus is intentionally tighter.
- Quality of the hand-written storylines is better than what you'd get from any algorithmic generator — they exist to give the LoRA something narratively coherent to learn from.

The methodology is identical at production scale. Run the same pipeline, wait longer, get better results.
