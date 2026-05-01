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
