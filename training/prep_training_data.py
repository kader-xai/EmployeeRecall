"""
Convert the JSONL corpus into:
  1. LoRA training pairs (chat format) — for the style fine-tune
  2. RAG documents (chunked + with metadata) — for the retrieval index
  3. Eval set (held-out 5%)

Outputs:
  training/data/sft_train.jsonl
  training/data/sft_eval.jsonl
  training/data/rag_docs.jsonl

Run:
    python training/prep_training_data.py --persona priya
    python training/prep_training_data.py --persona rohan
"""
import argparse
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
random.seed(42)


def load_persona(name):
    return json.loads((ROOT / "personas" / f"{name}.json").read_text())

def load_corpus(persona_dir):
    docs = []
    for jsonl in sorted(persona_dir.glob("*.jsonl")):
        for line in jsonl.open():
            d = json.loads(line)
            d["_source_file"] = jsonl.name
            docs.append(d)
    return docs


def build_thread_index(emails):
    """Group emails by thread_id."""
    threads = {}
    for d in emails:
        if d.get("doc_type") != "email":
            continue
        tid = d.get("thread_id")
        if not tid:
            continue
        threads.setdefault(tid, []).append(d)
    for tid, msgs in threads.items():
        msgs.sort(key=lambda x: (x.get("thread_position", 0), x.get("date","")))
    return threads


def make_sft_pairs(threads, persona_email):
    """
    For each email authored by the persona where there's a prior message in the
    thread, create a (prior thread context -> persona reply) pair.
    """
    pairs = []
    for tid, msgs in threads.items():
        for i, msg in enumerate(msgs):
            if i == 0:
                continue  # need a prior message
            if msg.get("from", {}).get("email") != persona_email:
                continue
            # build the incoming context = all messages before this one
            history = []
            for prev in msgs[:i]:
                hdr = (
                    f"From: {prev['from']['name']} <{prev['from']['email']}>\n"
                    f"To: {', '.join(p['name'] for p in prev.get('to', []))}\n"
                    f"Subject: {prev.get('subject','')}\n"
                    f"Date: {prev.get('date','')}\n\n"
                    f"{prev.get('body','')}"
                )
                history.append(hdr)
            incoming = "\n\n---\n\n".join(history)
            reply = msg.get("body", "").strip()
            if len(reply) < 20:
                continue  # skip stubs
            pairs.append({
                "thread_id": tid,
                "doc_id": msg.get("doc_id"),
                "incoming": incoming,
                "reply": reply,
                "subject": msg.get("subject",""),
                "tags": msg.get("tags", []),
                "related_account": msg.get("related_account"),
            })
    return pairs


PERSONA_SYSTEM_PROMPT_TPL = """You are an AI assistant that drafts email replies in the voice of {full_name}, who held the role of {role} at {company}. You have been trained on {full_name}'s past emails.

Voice fingerprint:
- Register: {register}
- Verbosity: {verbosity}
- Decision style: {decision_style}
- Common opening phrases: {openers}
- Sign-off: {signoff}

Reply rules:
- Match {full_name}'s tone, structure, and vocabulary.
- Keep replies the length they would write (not longer).
- Do not invent facts not present in the incoming context. If a fact is missing, ask or hedge.
- Output the reply body only — no headers, no quoted email."""


def system_prompt_for(persona):
    return PERSONA_SYSTEM_PROMPT_TPL.format(
        full_name=persona["full_name"],
        role=persona["role"],
        company=persona["company"]["name"],
        register=persona["tone_profile"]["register"],
        verbosity=persona["tone_profile"]["verbosity"],
        decision_style=persona["decision_style"]["default_stance"],
        openers=", ".join(persona["vocab_fingerprint"].get("filler_phrases_high_frequency", persona["vocab_fingerprint"].get("high_frequency", []))[:5]),
        signoff=", ".join(persona["signature_patterns"].get("external_signoff", persona["signature_patterns"].get("email_signoff", []))[:2]),
    )


def to_chat_format(pair, system_prompt):
    """Qwen / Llama chat format."""
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Draft a reply to the following email thread:\n\n{pair['incoming']}"},
            {"role": "assistant", "content": pair["reply"]},
        ],
        "meta": {
            "thread_id": pair["thread_id"],
            "doc_id": pair["doc_id"],
            "tags": pair["tags"],
            "related_account": pair.get("related_account"),
        },
    }


# ---------- RAG chunking ----------

def chunk_doc(doc, max_chars=1500):
    """Return list of (chunk_text, chunk_metadata) tuples."""
    chunks = []
    base_meta = {
        "doc_id": doc.get("doc_id"),
        "doc_type": doc.get("doc_type"),
        "date": doc.get("date"),
        "thread_id": doc.get("thread_id"),
        "related_account": doc.get("related_account"),
        "related_project": doc.get("related_project"),
        "tags": doc.get("tags", []),
        "title": doc.get("title") or doc.get("subject"),
    }
    if doc.get("doc_type") == "email":
        # Single chunk per email with thread preamble
        preamble = f"[EMAIL on {doc.get('date','')}] From {doc['from']['name']} to {', '.join(p['name'] for p in doc.get('to', []))}.\nSubject: {doc.get('subject','')}\n\n"
        body = doc.get("body","")
        text = preamble + body
        if len(text) <= max_chars:
            chunks.append((text, base_meta))
        else:
            # split by paragraphs
            paras = body.split("\n\n")
            cur = preamble
            for p in paras:
                if len(cur) + len(p) + 2 > max_chars and cur != preamble:
                    chunks.append((cur, base_meta))
                    cur = preamble
                cur += p + "\n\n"
            if cur.strip() != preamble.strip():
                chunks.append((cur, base_meta))
    elif doc.get("doc_type") in ("meeting_notes",):
        # Per-section chunks; transcripts get window chunks
        title = doc.get("title", "Meeting")
        date = doc.get("date","")
        attendees = ", ".join(a.get("name","?") for a in doc.get("attendees",[]))
        preamble = f"[MEETING on {date}] {title}\nAttendees: {attendees}\n\n"

        if doc.get("transcript_segments"):
            # window of 8 segments
            segs = doc["transcript_segments"]
            for i in range(0, len(segs), 8):
                window = segs[i:i+8]
                text = preamble + "\n".join(f"[{s.get('t','')}] {s.get('speaker','?')}: {s.get('text','')}" for s in window)
                meta = {**base_meta, "section": f"transcript_{i}"}
                chunks.append((text, meta))
        else:
            for section in ("discussion","raw_body"):
                if doc.get(section):
                    text = preamble + f"## {section.replace('_',' ').title()}\n{doc[section]}"
                    chunks.append((text, {**base_meta, "section": section}))
            if doc.get("decisions"):
                text = preamble + "## Decisions\n" + "\n".join(f"- {d}" for d in doc["decisions"])
                chunks.append((text, {**base_meta, "section": "decisions", "_boost": 2.0}))
            if doc.get("action_items"):
                text = preamble + "## Action Items\n" + "\n".join(
                    f"- {ai.get('owner','?')}: {ai.get('item','')} (due {ai.get('due','')})" for ai in doc["action_items"]
                )
                chunks.append((text, {**base_meta, "section": "action_items", "_boost": 1.5}))
    elif doc.get("doc_type") in ("rfc","adr","postmortem","design_doc"):
        title = doc.get("title","Document")
        author = doc.get("author","")
        body = doc.get("body","")
        preamble = f"[{doc['doc_type'].upper()} on {doc.get('date','')}] {title}\nAuthor: {author}\n\n"
        # split by markdown headings
        sections = re.split(r"\n## ", body)
        for sec in sections:
            text = preamble + ("## " + sec if not sec.startswith(("# ","TL;DR")) else sec)
            chunks.append((text[:max_chars*2], {**base_meta, "section": sec.split("\n")[0][:60]}))
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, choices=["priya","rohan"])
    ap.add_argument("--out", default=str(ROOT / "training" / "data"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    persona = load_persona(args.persona)
    persona_dir = ROOT / "corpus" / args.persona
    docs = load_corpus(persona_dir)
    print(f"Loaded {len(docs)} docs from {persona_dir}")

    # SFT pairs
    threads = build_thread_index(docs)
    sft_pairs = make_sft_pairs(threads, persona["email"])
    print(f"Built {len(sft_pairs)} SFT pairs")

    # Convert to chat format
    sysprompt = system_prompt_for(persona)
    chat_examples = [to_chat_format(p, sysprompt) for p in sft_pairs]

    # Train/eval split (95/5)
    random.shuffle(chat_examples)
    n_eval = max(50, len(chat_examples) // 20)
    eval_set = chat_examples[:n_eval]
    train_set = chat_examples[n_eval:]

    sft_train_path = out_dir / f"sft_train_{args.persona}.jsonl"
    sft_eval_path = out_dir / f"sft_eval_{args.persona}.jsonl"
    with sft_train_path.open("w") as f:
        for ex in train_set: f.write(json.dumps(ex) + "\n")
    with sft_eval_path.open("w") as f:
        for ex in eval_set: f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(train_set)} train, {len(eval_set)} eval pairs")

    # RAG docs
    rag_path = out_dir / f"rag_docs_{args.persona}.jsonl"
    n_chunks = 0
    with rag_path.open("w") as f:
        for d in docs:
            for chunk_text, meta in chunk_doc(d):
                f.write(json.dumps({"text": chunk_text, "meta": meta}) + "\n")
                n_chunks += 1
    print(f"Wrote {n_chunks} RAG chunks to {rag_path}")

    # Save the system prompt for inference
    (out_dir / f"system_prompt_{args.persona}.txt").write_text(sysprompt)
    print(f"Wrote system prompt for inference")


if __name__ == "__main__":
    main()
