# Video Script — Persona Continuity LoRA

Suggested length: **6–8 minutes**. Structure follows the methodology stages but condensed for a viewer who isn't an ML engineer.

Format: each section has on-screen action, voiceover (V/O), and B-roll suggestions.

---

## OPENING — The Problem (45 sec)

**On screen**: Empty office desk, a laptop with an out-of-office reply on the screen, slow zoom.

**V/O**: *When an experienced employee leaves, two things walk out the door with them. The first is how they wrote — their tone, their style, how they said no diplomatically. The second is bigger. It's everything they knew. Why we picked Postgres. What was actually happening with the Acme account. Who the real champion at Globex was. Why we killed the GraphQL gateway in 2024. None of that lives in your wiki. It lives in their inbox and their meeting notes.*

**On screen change**: Cut to a cluttered transcript file scrolling past — Otter, Fathom, mbox files.

**V/O**: *Today, that knowledge is just gone. We're going to show you how to bring it back — as an AI assistant, in their voice, that answers questions about their work using their actual history.*

---

## ACT 1 — The Setup (60 sec)

**On screen**: The persona card for **Priya Sharma**.
- Name, role (Senior CSM), 3-year tenure, 40 accounts, $4.2M ARR.
- Departure date.
- A "consent on file ✓" badge.

**V/O**: *Meet Priya. She's a fictional Senior Customer Success Manager at a fictional B2B SaaS company. Three years on the job, forty customer accounts, four-point-two million in ARR she's responsible for. She's leaving in December. Her successor, Arjun, inherits her book cold.*

**On screen**: Arjun's "first day on the account" empty inbox.

**V/O**: *Without help, Arjun's looking at six months of "wait, who is this person?" and "what did we agree to in March?" The accounts that survive are the ones where someone wrote it down. Most don't.*

**On screen**: Cut to second persona card — **Rohan Iyer**, Staff Engineer.

**V/O**: *And here's Rohan. Five years on the platform team. He owns the events service, the rate limiter, the SSO architecture. The reasons behind every major architecture decision live in his head and his email threads. He's leaving the same December.*

---

## ACT 2 — The Pipeline (90 sec)

**On screen**: Animated diagram, build out left-to-right as V/O describes each stage.

```
Mailbox + Meeting sources
    ↓
[Extract] PST, Gmail, Otter, Fireflies, Notion, Zoom
    ↓
[Normalize] unified JSONL schema
    ↓
[Persona profile] tone, vocab, decision style, relationships
    ↓
[Two parallel slices]
    ├── (LoRA dataset) (incoming → reply) pairs
    └── (RAG index) chunked + embedded
    ↓
[Train LoRA] Qwen-7B + adapter, ~$25 of GPU
    ↓
[Deploy] local inference, draft-only, audit-logged
```

**V/O**:
- *We pull from the actual sources real workplaces use. PST files from Outlook. mbox from Gmail. Transcripts from Otter, Fireflies, Fathom. Meeting notes from Notion and Confluence.*
- *Everything lands in one schema. Emails, structured meeting notes, AI-generated transcripts, quick scribbles — all unified.*
- *Then we build a persona fingerprint. Not just "warm" or "formal" — the actual filler phrases she uses, how long her sentences are, how she pushes back when she has to say no.*
- *From the same corpus we build two things in parallel. One: training pairs for a LoRA fine-tune that captures her voice. Two: a vector index over every email and every meeting, so the system can retrieve real history — not memorize, remember.*

**On screen**: Show the persona fingerprint JSON for Priya — the vocab list ("circling back", "quick context", "where I landed") highlighted.

**V/O**: *The fingerprint goes into the model's system prompt at training time and at inference time. The retrieval index keeps her actual records.*

---

## ACT 3 — The Demo (Use Case 1: CSM, 90 sec)

**On screen**: The web app. Title: "Persona Continuity — Priya Sharma". Search box in the middle.

**Action**: Type the question slowly: *"What happened with Acme Corp?"*

**Wait beat. Then the answer types out, in Priya's voice:**

> *"Acme has been a steady mid-market account since January 2023, ARR around $84,000. The main contact is Sarah Lin, VP Operations — she's friendly but slow to respond, you usually need to nudge her twice. The CFO Mike Reyes is the economic buyer; respects directness, do not BS him.*
>
> *Q1 2025 was the big story. Mike pushed back on a thirty-one-seat overage on the Q1 invoice — about fourteen thousand dollars. We dug into it with our RevOps team, found that eighteen of those seats were dormant accounts that Acme should have deprovisioned. We issued a $4.2k credit applied to the Q2 invoice and proposed new billing terms — monthly active billed user instead of event-active. Mike accepted on a working call March 4, and that became the new contract language.*
>
> *Renewal closed in early April at flat ARR with a soft commitment to revisit Premium-tier upgrade in Q3 if SSO shipped — which it did. They greenlit Premium in July, +$18k. The account is now at $102k effective ARR, renewing April 2026.*
>
> *Watch out for: Mike is sensitive to billing surprises. The relationship has scar tissue around invoicing. Over-communicate any billing change."*

**On screen**: As the answer renders, a "Sources" panel expands at the bottom showing **12 cited emails + 5 meeting docs**, dated across 2025.

**V/O**: *This isn't memorized. The model isn't reciting. Watch the sources panel — every claim it just made is grounded in a specific email or meeting note from Priya's archive. The CFO's name, the credit amount, the soft commit, the upgrade trigger — all citable, all traceable. If a fact isn't in the corpus, the model says it doesn't know.*

**Hover over a citation** — opens a side panel showing the actual email or meeting transcript snippet. **Click through it briefly** to show it's a real document, not a prop.

**V/O**: *And it sounds like Priya. The "Quick context", the "Watch out for", the "do not BS him" — that's her fingerprint, learned from three years of how she actually wrote.*

---

## ACT 4 — The Demo (Use Case 2: Engineer, 60 sec)

**On screen**: Same UI, switched to Rohan's persona. Question: *"Why are we using Postgres for events instead of MongoDB?"*

**Answer (in Rohan's voice)**:

> *"This was decided in September 2023. There was an RFC and an architecture review on Sept 14. The short version: relational queries against users and subscriptions made Mongo a bad fit — we'd either denormalize, which makes Mongo your ETL target, or do application-side joins, which is slow and bug-prone. We had also already paid the cost of moving billing OFF Mongo in 2022 — Tarun has the scars.*
>
> *We considered ClickHouse but rejected it as premature. Final decision is in ADR-0017. Re-evaluation triggers are sustained 50 million events per day, OR analytical query latency p99 over 5 seconds on the read replica. Tarun ran a ClickHouse spike in May 2025; volume was 42M/day at the time, and the speedup wasn't enough to migrate. We deferred. If you hit the trigger, the spike doc is the place to start, not a fresh evaluation."*

**Sources panel**: ADR-0017, the September 14 meeting transcript, the original RFC, two email threads, and the May 2025 spike document.

**V/O**: *Same system. Same architecture. Different voice, different domain. The model knows the ADR number. It knows Tarun ran the spike. It knows the trigger conditions and tells you exactly what to do if you hit them. None of this is in the wiki. All of it was in Rohan's emails and meeting notes.*

---

## ACT 5 — The Hard Stuff (60 sec)

**On screen**: Black slide, white text appearing one bullet at a time:

- ✓ Written consent from the departing employee
- ✓ Data minimization — PII redaction, personal threads dropped
- ✓ Draft-only — never auto-sent, every output reviewed by a human
- ✓ Audit logging — every query and answer recorded
- ✓ Local inference — no customer data leaves the org
- ✓ Sunset on schedule — 12 months active, then archive, then deletion

**V/O**: *None of this works without consent. The methodology starts with a written agreement — the employee opts in to having their corpus used, knows the scope, knows when it retires. Personal threads are stripped. PII is redacted. Every model output is a draft that a human reviews before it goes anywhere. Every query is logged and auditable, including by the original employee if they want oversight. And inference runs locally — no customer data ever leaves the company. Do this any other way and you're building a liability, not a product.*

---

## ACT 6 — The Numbers (30 sec)

**On screen**: Four big numbers, animated counts:

- **18,978** — semantic documents (emails + meetings) in the synthetic corpus
- **54,927** — extracted artifact files (.eml, .html, .ics, .vtt, .md)
- **228 MB** — total extraction footprint (a real 5-year senior employee corpus is typically **1–3 GB**)
- **$25** — total GPU cost to fine-tune a 7B LoRA on this dataset

**V/O**: *The synthetic corpus we built for this demo has nearly nineteen thousand documents — emails, meeting transcripts, RFCs, postmortems, calendar invites — extracted into fifty-five thousand artifact files. A real employee leaving after five years gives you one to three gigabytes. The fine-tune itself? Twenty-five dollars of GPU.*

---

## CLOSING (30 sec)

**On screen**: Slow zoom into the search box on the web app. Type one final question: *"What's the one thing I should know about Mike Reyes?"*

**Answer**: *"He doesn't tolerate billing surprises. Over-communicate every change, especially anything that affects an invoice. He'll respect you for it — he stops respecting you the moment a number lands without warning."*

**Cut to a clean black screen with text only**:

> Persona Continuity LoRA
> *Capturing what walks out the door.*

**V/O**: *The institutional knowledge isn't gone the moment they leave. It's gone the moment we stop preserving it. Build the assistant before the goodbye email goes out.*

---

## Production Notes

**B-roll suggestions**:
- Rotating screens of mailbox software (Outlook, Gmail, Apple Mail) — shows the variety of sources.
- File-tree animation showing the corpus directory expanding.
- Terminal window running the bulk generator with output streaming.
- vLLM server log streaming during inference.
- A whiteboard sketch of the architecture from V/O Act 2.

**On-screen text style**: Monospace for code/file paths, sans-serif for prose. Citations should look clickable.

**Pacing**: Don't rush ACT 3 — the Acme demo. Let viewers read the answer. The eight seconds of silence while the answer renders and they take in the sources panel is the most valuable eight seconds in the video.

**Things NOT to say**:
- "Replace your employees with AI" — this is about continuity, not replacement. Frame as bridging the gap.
- "Auto-respond on their behalf" — never. This is draft-only, human-reviewed.
- "100% accurate" — say grounded, traceable, citation-backed. Don't oversell.

**Music**: Calm, building. Pause on the demo answer reveal — let the silence sell.

**Total runtime target**: 6:30. If you go over 8:00, cut from Act 5 (the consent/legal section) by trimming the on-screen list to four bullets and shortening the V/O.
