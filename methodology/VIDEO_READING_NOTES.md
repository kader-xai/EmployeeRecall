# Video Reading Notes — Main.pptx (32 slides)

Spoken script for each slide. ~12–15 minute video at a relaxed pace. Curiosity-led: each slide opens with a hook, then delivers the substance, then bridges to the next.

Pacing legend: **(short)** ~10 s · **(medium)** ~25 s · **(long)** ~45 s.

---

## Slide 1 — Title: Ex-Employee Digital Twin (medium)

> Imagine the most senior person on your team — the one who knows everything, the one everyone messages on Slack — hands in their notice. In two weeks they're gone. What walks out the door with them?
>
> It's not just their job. It's the *way* they wrote to your biggest customer. The reason you chose Postgres in 2023 instead of Mongo. The exact tone they used to push back on procurement.
>
> This is **Ex-Employee Digital Twin** — a way to preserve that knowledge, reduce loss, and empower the team that stays. In the next ten minutes I'll show you exactly how it works, and you can build your own version for less than a dollar.

---

## Slide 2 — Worker Digital Twin: Persona Continuity for the AI Era (medium)

> Three pieces.
>
> **One — your work and knowledge.** Emails, meeting notes, project docs, the decisions you made.
>
> **Two — AI memory and intelligence.** A model that understands you, learns from you, and remembers you.
>
> **Three — a consistent AI assistant.** It answers in your style and acts in your context. Not a generic chatbot. A digital colleague.
>
> This isn't science fiction. It's three open-source pieces stitched together — and we'll see all three.

---

## Slide 3 — The scenario: Priya → Arjun (medium)

> Meet **Priya**. She's the VP of Customer Relations at a fictional company called Northwind SaaS. She has years of customer history in her head — every renewal, every escalation, every relationship.
>
> Priya is leaving. Her replacement is **Arjun**.
>
> What we want to build is the green box in the middle — Priya's digital twin. An AI that ingested all her documents, emails, web research, and notes. It does three things:
>
> 1. Understands her history.
> 2. Learns her role and her tasks.
> 3. Helps Arjun respond to customer requests *the way Priya would*.
>
> Arjun keeps Priya's institutional memory. Without retraining her for six months.

---

## Slide 4 — Three layers: Base Model + LoRA + RAG (long)

> Here's the architectural picture. Three layers stacked:
>
> **Bottom — the base model.** A large pre-trained LLM. We're using Qwen 2.5 7B. It already speaks fluent English, knows how to reason, knows what an email looks like. We never modify it.
>
> **Middle — LoRA adapters.** Tiny chips of fine-tuning that inject behaviour, tone, and style. Only about 0.1% of the parameter count of the base model. This is the "voice."
>
> **Top — RAG, retrieval augmented generation.** The persona's actual documents — emails, meeting notes, reports — embedded into a vector database for instant lookup. This is the "memory."
>
> All three feed into one persona icon at the top. Take any of the three away and the persona breaks differently. Together: a digital twin.

---

## Slide 5 — Human ↔ Employee Recall mapping (medium)

> Side-by-side analogy. On the left a real human; on the right our AI.
>
> The human's **brain** corresponds to the **base model** — Qwen 7B. Pure intelligence and language ability.
>
> The human's **personality** — how they write, the words they reach for — that's the **LoRA adapter**, only 150 megabytes.
>
> The human's **self-awareness and role** — "I am Priya, this is my job, these are my rules" — that's the **system prompt**, just text.
>
> The human's **meeting notes** — the references they bring to a conversation — that's the **RAG index**, about 50 megabytes.
>
> Four things in a person. Four equivalents in software. That's the whole design.

---

## Slide 6 — Problems when an employee leaves (short)

> Three categories of damage when someone walks out:
>
> **Customer discussions** they had verbally that nobody else heard.
>
> **Project history** — why we did things the way we did.
>
> **Implicit knowledge** — the stuff that lives only in their head.
>
> Let's look at each of those in turn.

---

## Slide 7 — Client Relationship Risk (medium)

> First risk: client relationships. When Priya leaves, you get a knowledge vacuum. That cascades into undocumented discussions:
>
> - Loss of verbal agreements — promises made on a call that nobody wrote down.
> - Erosion of client trust — customers feel like they're starting over with a stranger.
> - Missed relationship nuances — *"Mike doesn't like being CC'd on bad news"* never gets transferred.
>
> These are the things customers complain about silently. By the time you hear about it, the renewal is already in trouble.

---

## Slide 8 — Operational Intelligence Loss (medium)

> Second risk: operational intelligence. The history-and-context gap manifests three ways:
>
> - **Technical debt hidden in legacy code** — only the original engineer knew why a workaround was a workaround.
> - **Loss of the "why" behind past decisions** — the new team rebuilds the case from scratch, sometimes the wrong way.
> - **Incomplete project documentation** — there's always 20% that lives in someone's head.
>
> This is how companies re-litigate the same architectural debate every two years.

---

## Slide 9 — Persona & Culture Erasure (medium)

> Third risk: persona and culture. You lose:
>
> - Their unique problem-solving approach.
> - Subject-matter expertise — the SME gap.
> - Internal team dynamics — the unwritten *"this is how we run a standup"*.
>
> Three risks, one cause. Knowledge that lived in one person's head doesn't transfer just because you ran a 30-minute handover meeting.

---

## Slide 10 — Pipeline part 1: Data → Cleaning → Pairs → LoRA → GGUF (medium)

> So how do we capture all that? Step by step.
>
> **Step 1 — collect the data**: emails, meeting notes, decision documents.
>
> **Step 1.1 — clean and prep it**: not all of it is gold. Some of it is signature blocks and meeting boilerplate.
>
> **Step 1.2 — turn it into pairs**: every time the persona replied to an incoming message, that's a training example.
>
> **Step 2 — LoRA fine-tune**: feed the pairs to the base model. About thirty minutes on an A100.
>
> **Step 3 — package it as a GGUF file**: a portable model format that runs anywhere.
>
> **Step 4 — separately, all the documents become RAG chunks**, ready for retrieval. That's the parallel branch on the top right.

---

## Slide 11 — Pipeline part 2: FAISS + Model + Prompt → Cited Answers (medium)

> Three things come together at inference time.
>
> The **FAISS index** holds every chunk of every document.
> The **fine-tuned model** holds the voice.
> The **system prompt** tells the model who it's pretending to be.
>
> When a question comes in, the `ask` function pulls the relevant chunks from FAISS, hands them to the model with citation markers, and the model produces a cited answer drawn from real history.
>
> Voice, memory, identity — answered with sources you can verify.

---

## Slide 12 — Sample input: meeting notes JSON (medium)

> What does the data actually look like? Here's one meeting note.
>
> Notice the structure: doc_id, date, title, attendees, agenda, discussion, decisions, action_items.
>
> This is the "Acme — Q1 invoice working session" from March 4. Three attendees. Specific decisions: Northwind to issue $4.2k credit. Specific action items: Priya to confirm credit with Lena by EOD.
>
> Every field is searchable. Every decision is grounded. This is what gets indexed.

---

## Slide 13 — Sample input: incident postmortem (short)

> Same structure, different document type. This is a **postmortem** from May 2024 — Rohan's engineering side. The Hooli burst-traffic outage. Author, reviewers, body, tags. All structured.
>
> The model can answer questions like *"What was the May 2024 incident?"* by retrieving this exact document and quoting from it.

---

## Slide 14 — Sample input: email JSON (short)

> And the most common document type: emails. From, to, subject, body, thread position, tags. Plain JSON.
>
> If you can extract emails into this shape — and most mail clients can — you can put them straight into the pipeline.

---

## Slide 15 — Total corpus footprint (medium)

> Let's talk volume. The fictional dataset that ships with this project:
>
> 18,978 documents. Across two personas — Priya the CSM has about 16,000, Rohan the engineer has about 2,000.
>
> 54,927 multi-format extraction files (emails as `.eml`, meetings as `.ics`, transcripts as `.vtt`) — the same content rendered as if it came out of Mail.app and Calendar.
>
> Total project size: 135 megabytes. **A four-year career in 135 megabytes.**

---

## Slide 16 — GPU choice on Google Colab (short)

> To train, you need a GPU. We use Google Colab. Pick A100. Forty gigabytes of VRAM. About a dollar an hour on Colab Pro.
>
> Total training cost per persona: roughly twenty-five cents.

---

## Slide 17 — How LoRA works (long)

> Quick visual on what LoRA actually does.
>
> A normal large model has a giant weight matrix W. To fine-tune it the old way, you'd update every value in W — billions of parameters, expensive, slow.
>
> LoRA's trick: leave W frozen. Add two tiny matrices A and B beside it. The "update" becomes W plus B times A. A and B together are tiny — maybe one tenth of one percent of the original parameters.
>
> You only train A and B. You're efficient. You're memory-friendly. You're fast. And you can swap in different LoRAs for different personas without touching the base model.
>
> The right side of the slide is the actual training code: load Qwen 7B, attach LoRA adapters, prepare data, configure with `SFTTrainer`, train, save the adapter. About 30 lines of Python.

---

## Slide 18 — Post-LoRA pipeline: Merge → GGUF → Quantize → Run (medium)

> After training, four steps to get from your LoRA to a model anyone can run.
>
> **Merge**: combine the LoRA adapter with the base model. Output is a full 14-gigabyte fp16 model.
>
> **Convert**: turn that HuggingFace model into a GGUF file — the format llama.cpp and Ollama understand.
>
> **Quantize**: shrink fp16 down to Q4_K_M. From 14 gigabytes to 4 to 5 gigabytes. Quality stays high; size drops three times.
>
> **Run**: start it up locally with Ollama or llama.cpp.
>
> All four steps are tiny Python wrappers. The slide shows the actual code.

---

## Slide 19 — RAG and `build_rag_index.py` (long)

> Now the other half — RAG, retrieval augmented generation.
>
> Six steps. Ingest your documents. Chunk them into roughly 1,500-character pieces. Embed each chunk into a vector — we use BGE-base, an open-source embedder. Store the vectors in a FAISS index. At query time, embed the user's question and find the top-k most similar chunks. Hand those to the model as context.
>
> The right side of the slide is `build_rag_index.py` — about 60 lines. Load chunks, embed them, build the FAISS index, save the metadata. That's it.
>
> Sub-five-millisecond search across 17,000 chunks. Faster than a database query.

---

## Slide 20 — Full Architecture Overview (long)

> Zoom out. This is the entire system on one slide.
>
> Top-left — **LoRA Training**. Persona data goes in, base model gets adapted, you save a LoRA adapter, you optionally merge it into a full model.
>
> Bottom-left — **RAG Index Building**. Documents chunked, embedded, stored in a vector database with metadata.
>
> Bottom-right — **Inference Loop**. User asks a question. Embed the question. Retrieve top-k from FAISS. Build a prompt that combines system prompt, sources, and the question. Send to the LoRA-tuned model. Get a cited answer.
>
> The full code lives in the repo at `inference.py`. About a hundred lines.
>
> The bottom-right caption sums it up: **RAG brings the right information. LoRA brings the right behaviour. Together they produce answers that are accurate and personalised.**

---

## Slide 21 — Run LoRA GGUF model locally (long)

> Seven steps to run the trained persona on your own laptop.
>
> One. Install Ollama — one command on a Mac.
>
> Two. Register the GGUF as an Ollama model.
>
> Three. Install Python dependencies — requests, faiss, sentence-transformers. That's it.
>
> Four. Confirm the FAISS index and metadata are on disk.
>
> Five. Write a small glue script — `ask_local.py`. Ten lines: load the embedder, load FAISS, load metadata, define an `ask` function that embeds the question, retrieves chunks, builds a prompt, calls Ollama.
>
> Six. Run it. Sample output appears in the slide — you ask "what happened with Acme?", you get a paragraph in Priya's voice with citation lines below.
>
> Seven. Make it interactive: a tiny REPL loop so you can keep asking.
>
> The whole thing runs on your machine. No data leaves your computer.

---

## Slide 22 — Use case: list every customer (medium)

> Real demo. Real output.
>
> *"List every customer in your knowledge base and their renewal date, sorted by ARR descending."*
>
> Eleven seconds. Five customers come back. Acme Corp, BuyNLarge, ENCOM, Abstergo, Wonka. Each with a renewal date. Each with a source citation.
>
> Below that the **sources** — eight document IDs, each with a similarity score. You can open any one of them on disk and verify the answer is real.
>
> No hallucination. No invented data. Grounded in the actual corpus.

---

## Slide 23 — Use case: project issues (long)

> Harder question. *"Why did we credit Acme $4,200? Give me a bullet-point list of reasons, and cite the source documents inline."*
>
> The model answers in three points. Eighteen of 31 contested seats were dormant for over 60 days at billing snapshot. Nine were single-event logins — *check this thing then close*. So the credit reflects 18 dormant seats at roughly $250 each plus half of nine single-event logins.
>
> The model is not just retrieving — it's **synthesising** from multiple emails and meeting notes, doing the arithmetic, and citing each piece.
>
> This is the kind of question where a successor would normally take an hour digging through emails. The persona twin answers in 24 seconds.

---

## Slide 24 — Use case: renewal discussions (short)

> Slightly different angle. The same `ask` function answering a different question — listing customers and their renewal dates.
>
> Notice the model honestly says *"Abstergo Industries — not a named customer, no renewal date found in the provided context."*
>
> When the corpus doesn't have an answer, it says so. It doesn't invent.

---

## Slide 25 — Challenges: hallucination and edge cases (medium)

> But it's not perfect. Here we asked *"what happened with the Hoolie incident?"* — and the model gave a short polite reply rather than a deep dive.
>
> Why? Look at the sources. Top similarity score is 0.71 — strong on the surface. But the model interpreted the question as a customer-comms reply, not a postmortem question.
>
> Lesson one: phrasing matters.
> Lesson two: low retrieval scores mean low confidence. The eval pipeline catches this and lets you tune.
>
> Imperfect, but transparent — and *that's* the difference between a real assistant and a hallucinating chatbot.

---

## Slide 26 — Slack integration (medium)

> Let's plug this into where people actually work — Slack.
>
> A user types `/ask-priya` and a question. Slack sends the slash command to a Cloudflare tunnel, which forwards it to **n8n** — a visual workflow engine running on your machine.
>
> n8n parses the payload, immediately acks Slack within three seconds (Slack's hard limit), then in parallel calls our local `api.py`. The model thinks for ten seconds, formats the answer with citations, posts back to Slack.
>
> The user sees an instant *"Asking Priya about..."* message, then ten seconds later the real cited answer. It feels native.

---

## Slide 27 — n8n pipeline visual (short)

> Here's the n8n workflow itself. Six nodes:
>
> **Slack Slash Command** webhook → **Parse Payload** → branches into **Ack Slack** (instant) and **Call Persona API** (slow path) → **Format Reply** → **Post to Slack**.
>
> Drag-and-drop. Fully importable from the repo. JSON in, JSON out.

---

## Slide 28 — Slack live demo screenshot (short)

> Here's what it looks like in Slack itself. User asks the renewals question. Within seconds, Priya replies — in voice, with sources cited beneath the message. Each source link is a real document ID with a similarity score.
>
> This is the moment your team sees a "departing employee" still answering questions in their own voice. The reaction is the same every time.

---

## Slide 29 — DEMO interlude (short)

> Brief demo break. *Run the live notebook here. Ask three questions: "what happened with Acme?", "why did Rekall churn?", "what was the May 2025 Hooli incident from the customer side?"* — and then the cross-persona kicker: ask Rohan the same Hooli question. Same event, two completely different perspectives.

---

## Slide 30 — Option 1 vs Option 2: One Employee Twin vs Company Model (long)

> Now the question every viewer has: *do I have to clone every single employee?*
>
> No. There are choices. Two of them on this slide.
>
> **Option 1 — One employee digital twin.** Personalised AI for each individual. LoRA trains on Priya's data. RAG indexes Priya's docs. Best for: executive assistants, sales rep memory, productivity tools, departing-employee succession. Highly personalised and realistic. Higher consent bar.
>
> **Option 2 — One company model + shared RAG.** A consistent assistant for everyone. LoRA trains on the company's general culture and tone. RAG indexes all company documents. Best for: HR, IT, policy assistants, onboarding, support, company-wide Q&A. Scalable, consistent, easy to maintain.
>
> Same architecture. Different scope.

---

## Slide 31 — Option 3 vs Option 4: Public LLM + RAG vs Hybrid (long)

> Two more options.
>
> **Option 3 — Public LLM plus private RAG.** No fine-tuning at all. Just retrieve from your docs and ask GPT-4 or Gemini. Best for: quick MVPs, knowledge search, FAQ bots, cost-effective solutions. Fastest to deploy. Doesn't capture voice — uses the model's default tone.
>
> **Option 4 — Hybrid: LoRA for behaviour plus RAG for knowledge. The recommended balance.** RAG provides facts, LoRA ensures the right tone. Best for: enterprise AI assistants, customer-facing bots, employee productivity tools, **digital twins at scale**.
>
> So: four configurations of the same underlying technology. Pick one based on cost, control, and how personalised you need it.

---

## Slide 32 — Conclusion (long)

> Quick recap. **Four things you've now seen.**
>
> One — what we built: a persona-driven AI that speaks in a consistent voice, gives grounded answers from real documents, runs 100% locally, and uses fine-tuning plus quantisation for fast local performance.
>
> Two — why this approach is powerful: privacy first, accurate and reliable, fast and efficient, personalised, fully ownable.
>
> Three — you can build your own. Five steps in the slide: define persona, collect documents, fine-tune, merge and quantise, run locally and chat. No coding wizardry needed — easy steps with examples in the documentation.
>
> Four — it's open source. Repository link on the slide. Synthetic dataset included. Less than 25 cents to train. Two demo personas: a CSM and a Staff Engineer. Methodology covers the privacy and consent governance you need before deploying with real data.
>
> The four risk callouts at the bottom are the ones to take seriously: PII exposure, cross-department data exposure, compliance / consent risk, and wrong information being presented as fact. The repo documents how to mitigate each.
>
> So — go and build your own employee digital twin. The link is on the slide. The full repo is at **github.com/kader-xai/EmployeeRecall**. Star it if it's useful.

---

# Production tips for the recording

## Timing target
- Slides 1–9: **the problem** — ~3 min total
- Slides 10–14: **the data** — ~2 min
- Slides 15–20: **the architecture** — ~3 min
- Slides 21–25: **demos** — ~2 min
- Slides 26–28: **Slack integration** — ~1.5 min
- Slides 29–32: **options + close** — ~2 min

Total ~13–14 minutes at a measured pace.

## Voice and tone
- Conversational, not lecturing. End most slides with a one-line bridge.
- Two pacing rules:
  - When you show a code slide (17, 18, 19, 21), **slow down** — let the viewer scan it.
  - When you show a results slide (22, 23, 24), **let the answer breathe** — read out the citation list slowly so the audience sees the IDs match.
- Use specific numbers — "$4,200", "30 minutes", "25 cents", "150 megabytes". Specific numbers beat adjectives.

## Things to verbally emphasise

| Slide | Emphasis line (read in a slightly lower register) |
|---|---|
| 4 | "Take any of the three away and the persona breaks differently." |
| 11 | "Voice, memory, identity — answered with sources you can verify." |
| 17 | "You only train A and B." |
| 21 | "No data leaves your computer." |
| 22 | "No hallucination. No invented data." |
| 26 | "It feels native." |
| 32 | "Less than 25 cents to train." |

## On-screen overlays to add in post

- Slide 1: animate "Preserve Knowledge / Reduce Loss / Empower Teams" icons in sequence.
- Slide 4: animate the three layers stacking bottom-to-top with a fade.
- Slide 17: zoom on the `W = W + B·A` formula at 0:30 into the slide.
- Slide 21: highlight each numbered step with a coloured box as you read it.
- Slide 22: highlight the citation IDs with a pulse — that's the "trust moment" of the demo.
- Slide 28: animate the *"Asking priya about..."* line, then the full answer, then the source list — three sequential reveals.

## Cuts and B-roll

| Slide | Suggested B-roll |
|---|---|
| 1 | Stock office desk + sunset, 5 sec |
| 6–9 | Quick cuts of empty chair, half-erased whiteboard, lonely coffee cup |
| 16 | Screen recording of Colab GPU selection menu |
| 20 | Live screen recording of the ask.ipynb notebook running |
| 26 | Recording of the actual Slack workspace receiving an answer |
| 29 | Switch to live demo capture |

## Closing CTA (over slide 32 or as a bumper after)

> "If you build something on top of this, open an issue with what you learned. Repo link in the description. Thanks for watching."

---

# Quick reference — what's where

| Section of video | Slides | Key fact to land |
|---|---|---|
| Hook | 1–3 | When senior people leave, voice and history walk out with them |
| Architecture | 4–5 | LoRA + RAG + System Prompt = persona |
| Problem detail | 6–9 | Three risks: client, operational, culture |
| Pipeline | 10–11 | Two parallel branches: train the voice, index the knowledge |
| Data shape | 12–14 | Emails, meetings, postmortems — all JSON |
| Volume | 15–16 | 19k docs, 135 MB total, A100 30 min |
| LoRA mechanics | 17 | Train only A and B, freeze W |
| Local deploy | 18, 21 | Merge → GGUF → Quantize → Ollama |
| RAG mechanics | 19–20 | Chunk → embed → FAISS → retrieve top-k |
| Live demos | 22–25 | Real questions, real cited answers |
| Slack integration | 26–28 | Productionise into the team's chat |
| Choosing a pattern | 30–31 | Four options from "twin" to "pure RAG" |
| Close | 32 | Open source, $0.25, link in description |
