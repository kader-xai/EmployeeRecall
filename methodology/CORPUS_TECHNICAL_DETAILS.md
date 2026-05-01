# Corpus — Technical Details

A walkthrough of every component in the Employee Recall corpus: what each file is, why it exists, how the pieces connect, and what gets fed into training.

---

## The Big Picture

The corpus is **5 layers** of data that build a fictional employee from the ground up:

```
1. WHO are they?          → personas/*.json
2. WHO do they work with? → cast/internal.json
3. WHAT do they own?      → accounts/*.json, projects/*.json
4. WHAT did they do?      → corpus/{persona}/*.jsonl   ← actual emails/meetings
5. HOW does it look?      → extraction_output/*        ← real-format files (.eml, .ics)
```

| Layer | Role | Footprint |
|---|---|---|
| 1–3: Hand-authored fingerprints | Parameters that drive everything | ~36 KB |
| 4: Semantic corpus (JSONL) | Fed into training | ~13 MB, 18,978 docs |
| 5: Multi-format extraction | Demo realism, not training | ~215 MB, 54,927 files |

---

## Layer 1: Personas — `personas/{name}.json`

The "DNA" of each fictional employee. ~5 KB each. Two personas: **Priya** (Senior CSM) and **Rohan** (Staff Engineer).

### Sections in `priya.json`

| Section | What it captures | Example |
|---|---|---|
| `id`, `full_name`, `email` | Identity | `priya.sharma@northwind-saas.com` |
| `company` | Where they work | "Northwind SaaS, B2B workflow automation" |
| `tenure` | Hire/departure dates, successor | Joined 2022-06-13, last day 2025-12-19 |
| `manager`, `reports`, `portfolio` | Org position | Reports to Lena Park; owns 40 accounts, $4.2M ARR |
| `tone_profile` | How they write | "warm-professional, medium verbosity, low hedging, rare exclamation" |
| `signature_patterns` | Greetings & sign-offs | `["Hi {name}, hope your week..."]`, `["Best,\nPriya"]` |
| `vocab_fingerprint` | Pet phrases — used and avoided | Uses "circling back", "quick one"; avoids "kindly", "per my last email" |
| `decision_style` | How they think | "Always pairs a no with a yes" |
| `response_latency` | When they reply | Internal <30 min, weekend only emergencies |
| `topics_owned` | Their domain | Renewals, QBRs, churn risk |
| `internal_relationships` | Who they trust, who they argue with | Lena = trusted; Marcus = "occasionally tense on handoff" |
| `personal_quirks` | Tells | "Names next concrete step at end of every email" |
| `topics_to_avoid` | What they won't write | "Internal politics in writing — saves for verbal" |

### Read at three points in the pipeline

1. **Bulk generators** template these phrases into emails so synthetic content sounds like the persona.
2. **`prep_training_data.py`** uses `tone_profile` and `vocab_fingerprint` to build the system prompt.
3. **Inference** loads the system prompt to remind the model who it's impersonating.

---

## Layer 2: Cast — `cast/internal.json`

The supporting characters. ~3 KB. About 25 people Priya and Rohan interact with.

### Structure

```json
{
  "lena_park": {
    "name": "Lena Park",
    "role": "VP Customer Success",
    "email": "lena.park@northwind-saas.com",
    "relationship_to_priya": "manager",
    "relationship_to_rohan": "occasional escalation",
    "voice_note": "concise, asks 'what's the ask?'"
  },
  "mike_reyes": {
    "name": "Mike Reyes",
    "role": "CFO at Acme Corp",
    "external": true,
    "voice_note": "terse, budget-focused"
  }
}
```

### Why it matters

When the corpus generator writes an email about an Acme renewal, it pulls Mike Reyes from the cast file so he behaves consistently across **40+ different documents** — same role, same tone, same email address. Without this, every generated email would invent a different CFO.

---

## Layer 3: Accounts & Projects

### `accounts/priya_accounts.json` — 15 KB, 40 customers

```json
{
  "acme_corp": {
    "tier": "enterprise",
    "arr": 240000,
    "industry": "logistics",
    "primary_contact": "Sarah Lin (VP Operations)",
    "exec_sponsor": "Mike Reyes (CFO)",
    "renewal_date": "2026-03-15",
    "health": "yellow",
    "storyline": "Q1 2025 billing dispute over seat-count overage; resolved with $4.2k credit; expansion conversation in progress; soft commit on Premium upgrade Q2."
  }
}
```

### `projects/rohan_projects.json` — 8 KB, 14 projects

```json
{
  "events-store-rfc": {
    "title": "Events Service datastore selection — Postgres vs MongoDB",
    "year": "2023-Q3",
    "status": "decided — Postgres",
    "decision": "Postgres. ClickHouse re-evaluation gated on >50M events/day.",
    "people": ["Rohan", "Maya Williams", "Devika Rao"],
    "deep_storyline": true
  }
}
```

### Why it matters

Each account/project has a one-paragraph **`storyline`** field — what really happened with this customer or this engineering decision. The bulk generator uses these as seeds: it writes an email *about* the Acme billing dispute, *about* the Postgres decision, populated with the named people from the cast.

---

## Layer 4: The Actual Corpus — `corpus/{persona}/*.jsonl`

This is what gets fed into training. **18,978 documents** total, all JSONL (one JSON object per line). Two persona folders.

### Priya's files (~13 MB)

| File | Type | Count | Purpose |
|---|---|---|---|
| `storyline_acme.jsonl` | hand-written | 22 | Full Acme saga — exec disputes, billing change, credit, expansion. **Demo material.** |
| `storyline_globex.jsonl` | hand-written | 5 | RFP + exec sponsor relationship |
| `storyline_umbrella.jsonl` | hand-written | 7 | SOC2 security questionnaire saga |
| `storyline_hooli_incident.jsonl` | hand-written | 8 | The May 2025 outage — cross-persona (Rohan also has docs about this) |
| `storyline_initech_rekall.jsonl` | hand-written | 6 | Initech expansion + Rekall churn |
| `dense_routine_{2022..2025}.jsonl` | generated | ~150/yr | Dense per-account cadence — touches each of the 40 accounts |
| `dense_meetings_{2022..2025}.jsonl` | generated | ~100/yr | QBR transcripts + 1:1s |
| `bulk_routine_{2023..2025}.jsonl` | generated | ~5,000/yr | Generic emails — internal updates, expense reports, scheduling |
| `bulk_weekly_syncs_{2023..2025}.jsonl` | generated | ~150/yr | Templated weekly team syncs |

### Rohan's files (~5 MB)

| File | Type | Count | Purpose |
|---|---|---|---|
| `storyline_events_store.jsonl` | hand-written | RFC + ADR + review | Postgres vs MongoDB decision |
| `storyline_rate_limiter.jsonl` | hand-written | incident + v2 + 2025 incident | Rate-limiter saga |
| `storyline_sso_graphql.jsonl` | hand-written | SSO ADR + GraphQL kill | Two architecture calls |
| `dense_eng_{2022..2025}.jsonl` | generated | ~150/yr | Engineering routine — code reviews, design discussions |
| `bulk_routine_{2023..2025}.jsonl` | generated | ~5,000/yr | Generic engineering emails |

### What a single document looks like

```json
{
  "doc_id": "email-acme-003",
  "doc_type": "email",
  "thread_id": "thread-acme-billing-q1-2025",
  "thread_position": 3,
  "date": "2025-03-03T10:55:00-05:00",
  "from": {"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"},
  "to": [{"name": "Mike Reyes", "email": "mike.reyes@acme.com"}],
  "cc": [{"name": "Sarah Lin", "email": "sarah.lin@acme.com"}],
  "subject": "Re: Q1 invoice — seat count discrepancy",
  "body": "Hi Mike,\n\nThanks for the patience while I dug into this...",
  "tags": ["billing", "credit", "acme"],
  "related_account": "acme_corp"
}
```

### Document types

| `doc_type` | Description | Used by |
|---|---|---|
| `email` | One message in a thread | Both personas |
| `meeting_notes` | Structured: discussion, decisions, action_items | Both personas |
| `meeting_transcript` | Time-stamped speaker segments (QBRs, all-hands) | Both personas |
| `rfc` | Engineering design doc | Rohan only |
| `adr` | Architecture Decision Record | Rohan only |
| `postmortem` | Incident retrospective | Rohan only (Hooli incident, rate-limiter outage) |
| `design_doc` | Lighter-weight than RFC | Rohan only |

### The three corpus tiers

```
HAND-WRITTEN STORYLINES (8 files, ~50 docs)
   ↓ depth, narrative arc, named entities
DENSE GENERATED (per-account / per-project)
   ↓ realistic frequency, references storylines
BULK GENERATED (templated routine)
   ↓ ambient volume — fills the inbox
```

#### Why three tiers

- **Pure bulk corpus** → model trains fine but sounds generic. Demo falls flat.
- **Pure storyline corpus** → too sparse, model overfits to 50 hand-written examples.
- **Three-tier mix** → enough volume to learn the voice + enough depth to answer specific questions.

We measured this: the eval scores **1.0** on hand-written storyline questions and **0.0** on the same-topic questions whose answers exist only in bulk-generated content. **Hand-write what the demo will ask, generate the rest.**

---

## Layer 5: Extraction Output — `extraction_output/`

The same content as Layer 4, expanded into real mailbox/calendar formats. **54,927 files, 215 MB.** This layer doesn't feed training — it's for visual realism in demos and for testing real extraction pipelines.

```
extraction_output/
├── emails/
│   ├── priya/   46,587 files   (.eml + .html + .txt per email)
│   └── rohan/    3,864 files
└── meetings/
    ├── priya/    2,672 files   (.ics + .md + .vtt per meeting)
    └── rohan/    1,804 files
```

### Three files per email

| Format | What it is | Used by |
|---|---|---|
| `.eml` | RFC 5322 raw mail with headers, MIME boundaries | What an IMAP fetch returns |
| `.html` | Rendered HTML body | What Outlook/Gmail renders |
| `.txt` | Plain text body | For grep/search |

### Three files per meeting

| Format | What it is | Used by |
|---|---|---|
| `.ics` | iCalendar format | What your calendar app shows |
| `.md` | Markdown notes | What Notion/Confluence shows |
| `.vtt` | WebVTT transcript with timestamps | What Zoom/Otter produces |

### Why it matters

When you give a video demo, you can show *real `.eml` files in Mail.app* and *real calendar entries in Calendar.app* — proves the methodology applies to a production extraction pipeline, not just to a custom JSON format.

---

## How It All Connects

```
Hand-authored fingerprints
(personas, cast, accounts, projects)
       │
       ▼
generate_bulk_corpus.py + v2.py
(deterministic, seed=42)
       │
       ▼
corpus/{priya,rohan}/*.jsonl   ←  18,978 semantic docs
       │
       ├──► prep_training_data.py        ──► training/data/sft_*.jsonl + rag_docs_*.jsonl
       │
       └──► inflate_to_real_extraction.py ──► extraction_output/  (54,927 files)
```

### Determinism

All generators use `random.seed(42)`. Two runs from scratch produce **byte-identical output**. This matters for reproducibility — anyone can regenerate the corpus and verify that the trained model came from this exact data.

---

## What Each Generator Does

| Script | Purpose | Output |
|---|---|---|
| `scripts/generate_bulk_corpus.py` | v1: sparse synthetic baseline (~1 MB) | Bulk routine emails for both personas |
| `scripts/generate_bulk_corpus_v2.py` | v2: dense expansion (~13 MB) | Per-account dense routines, dense meetings, weekly syncs |
| `scripts/inflate_to_real_extraction.py` | Multi-format expander | Converts JSONL docs into `.eml`/`.html`/`.ics`/`.vtt`/`.md`/`.txt` |

### Reproducing from scratch

```bash
cd Employee Recall
python3 scripts/generate_bulk_corpus.py
python3 scripts/generate_bulk_corpus_v2.py
python3 scripts/inflate_to_real_extraction.py
```

That regenerates **all of Layer 4 and Layer 5**. Layers 1–3 are hand-authored — never regenerate them; edit by hand.

---

## What Gets Consumed by Training

After running `prep_training_data.py --persona priya`, the corpus produces two derived datasets in `training/data/`:

| Output file | Source | Used by |
|---|---|---|
| `sft_train_priya.jsonl` | Reply pairs from threads where Priya is the author | LoRA fine-tune (voice) |
| `sft_eval_priya.jsonl` | 5% held-out from the same | Validation during training |
| `rag_docs_priya.jsonl` | Every doc, chunked ≤1500 chars + metadata | RAG index build |
| `system_prompt_priya.txt` | Generated from `personas/priya.json` | Inference time |

### Numbers (from a real prep run)

```
Loaded 16,779 docs from corpus/priya
Built 1,287 SFT pairs (threads where Priya replied to a prior message)
Wrote 1,223 train, 64 eval pairs
Wrote 17,663 RAG chunks
```

---

## Cheat Sheet — Where to Look for What

| Question | File to check |
|---|---|
| What's the persona's tone fingerprint? | `personas/{name}.json` → `tone_profile`, `vocab_fingerprint` |
| Who is character X? | `cast/internal.json` |
| What's the storyline for account X? | `accounts/priya_accounts.json` → `[X].storyline` |
| What did engineering decide about X? | `projects/rohan_projects.json` → `[X].decision` |
| Is this a hand-written storyline? | Filename starts with `storyline_` |
| Are these synthetic emails realistic? | Yes — see `extraction_output/emails/{persona}/*.eml` |
| Can I regenerate this from scratch? | Yes — all scripts are deterministic with `random.seed(42)` |

---

## Five Things to Remember

1. **Personas + cast + accounts + projects** = the parameters that make synthetic content feel real.
2. **`corpus/{persona}/*.jsonl`** = the 18,978 docs that train the model. Three tiers: storylines (depth) + dense (frequency) + bulk (volume).
3. **`extraction_output/`** = the same content in real file formats. For demos, not training.
4. **Storylines drive recall, bulk drives realism.** A hand-written storyline is worth 100 bulk emails for demo quality.
5. **Determinism (seed=42)** means anyone can reproduce exactly the same corpus from scratch.
