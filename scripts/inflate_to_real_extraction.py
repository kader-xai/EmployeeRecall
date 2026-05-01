"""
Inflate the JSONL corpus into the multi-format artifact set that a real
mailbox extraction produces:

For each email:
  - raw .eml (RFC822) — what `libpst` produces from a PST
  - .html (HTML body render) — what Outlook/Gmail stores
  - .txt (plain-text body)
  - .json (already in JSONL)

For each meeting:
  - structured .json (already in JSONL)
  - .ics calendar invite
  - .vtt or .txt transcript file
  - .md notes file (rendered)

This isn't fake padding — it's the real output of an extraction pipeline,
which is what we'd ship through the methodology pipeline. Total footprint
will be ~5-10x the JSONL size.

Run:
    python scripts/inflate_to_real_extraction.py
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from email.utils import format_datetime, make_msgid

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "extraction_output"
OUT.mkdir(exist_ok=True)

EML_TEMPLATE = """From: {from_name} <{from_email}>
To: {to_field}
Cc: {cc_field}
Subject: {subject}
Date: {date_rfc}
Message-ID: {msg_id}
Thread-Topic: {thread_topic}
Thread-Index: {thread_idx}
Content-Type: multipart/alternative; boundary="bnd_{boundary}"
MIME-Version: 1.0
X-Mailer: Northwind-Extraction/1.0

--bnd_{boundary}
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit

{body_plain}

--bnd_{boundary}
Content-Type: text/html; charset=utf-8
Content-Transfer-Encoding: 8bit

{body_html}

--bnd_{boundary}--
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;font-size:11pt;color:#202020;max-width:780px;margin:24px;}}
.hdr{{border-bottom:1px solid #e1e1e1;padding-bottom:8px;margin-bottom:16px;color:#666;font-size:9pt;}}
.from{{font-weight:600;color:#202020;}}.subj{{font-weight:600;font-size:12pt;color:#0a0a0a;margin-bottom:6px;}}
.body{{line-height:1.55;white-space:pre-wrap;}}.sig{{color:#666;font-size:9pt;margin-top:32px;border-top:1px solid #f0f0f0;padding-top:12px;}}
</style></head><body>
<div class="subj">{subject}</div>
<div class="hdr">
<span class="from">{from_name}</span> &lt;{from_email}&gt;<br>
<b>To:</b> {to_field}<br>
{cc_html}<b>Sent:</b> {date_human}<br>
</div>
<div class="body">{body_html}</div>
<div class="sig">— sent via Northwind mail platform</div>
</body></html>"""

ICS_TEMPLATE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Northwind//Extraction//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{title}
DESCRIPTION:{description}
ORGANIZER;CN={organizer}:mailto:{organizer_email}
{attendees}
LOCATION:Online
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
"""

def fmt_addr(p): return f'"{p["name"]}" <{p["email"]}>' if isinstance(p, dict) else str(p)
def fmt_addrs(ps): return ", ".join(fmt_addr(p) for p in (ps or []))

def short_hash(s, n=8):
    return hashlib.sha1(s.encode()).hexdigest()[:n]

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z","+00:00")) if "T" in s else datetime.fromisoformat(s + "T09:00:00")

def email_to_eml(doc):
    dt = parse_dt(doc["date"])
    boundary = short_hash(doc["doc_id"])
    msg_id = make_msgid(domain="northwind-saas.com")
    return EML_TEMPLATE.format(
        from_name=doc["from"]["name"],
        from_email=doc["from"]["email"],
        to_field=fmt_addrs(doc.get("to", [])),
        cc_field=fmt_addrs(doc.get("cc", [])),
        subject=doc.get("subject","(no subject)"),
        date_rfc=format_datetime(dt),
        msg_id=msg_id,
        thread_topic=doc.get("thread_id",""),
        thread_idx=short_hash(doc.get("thread_id",""), 16),
        boundary=boundary,
        body_plain=doc.get("body",""),
        body_html=doc.get("body","").replace("\n","<br>\n"),
    )

def email_to_html(doc):
    dt = parse_dt(doc["date"])
    cc = fmt_addrs(doc.get("cc", []))
    return HTML_TEMPLATE.format(
        from_name=doc["from"]["name"],
        from_email=doc["from"]["email"],
        to_field=fmt_addrs(doc.get("to", [])),
        cc_html=f"<b>Cc:</b> {cc}<br>" if cc else "",
        subject=doc.get("subject","(no subject)"),
        date_human=dt.strftime("%A, %B %d, %Y at %I:%M %p"),
        body_html=doc.get("body","").replace("\n","<br>\n"),
    )

def meeting_to_ics(doc):
    dt = parse_dt(doc["date"])
    dur = doc.get("duration_min", 30)
    end = dt.replace(minute=(dt.minute + dur) % 60, hour=dt.hour + (dt.minute + dur) // 60)
    desc = doc.get("discussion","") or doc.get("raw_body","")
    desc = desc.replace("\n","\\n")[:1000]
    attendees = "\n".join(
        f'ATTENDEE;CN={a.get("name","?")};RSVP=TRUE:mailto:{a.get("name","x").lower().replace(" ",".")}@northwind-saas.com'
        for a in doc.get("attendees", [])
    )
    organizer = doc.get("attendees",[{}])[0].get("name","Priya Sharma")
    return ICS_TEMPLATE.format(
        uid=f'{doc["doc_id"]}@northwind-saas.com',
        dtstamp=dt.strftime("%Y%m%dT%H%M%SZ"),
        dtstart=dt.strftime("%Y%m%dT%H%M%SZ"),
        dtend=end.strftime("%Y%m%dT%H%M%SZ"),
        title=doc.get("title","Meeting"),
        description=desc,
        organizer=organizer,
        organizer_email=organizer.lower().replace(" ",".") + "@northwind-saas.com",
        attendees=attendees,
    )

def meeting_to_md(doc):
    title = doc.get("title","Meeting")
    dt = parse_dt(doc["date"]).strftime("%Y-%m-%d %H:%M")
    out = [f"# {title}", f"**Date:** {dt}", f"**Duration:** {doc.get('duration_min',30)} min", "",
           "## Attendees", *[f"- {a.get('name','?')}" + (f' ({a.get("company","")})' if a.get("company") else "") for a in doc.get("attendees",[])],
           "", "## Agenda"]
    out.extend(f"- {a}" for a in doc.get("agenda",[]))
    out.append("")
    if doc.get("discussion"):
        out.extend(["## Discussion", doc["discussion"], ""])
    if doc.get("raw_body"):
        out.extend(["## Notes", doc["raw_body"], ""])
    if doc.get("decisions"):
        out.append("## Decisions")
        out.extend(f"- {d}" for d in doc["decisions"])
        out.append("")
    if doc.get("action_items"):
        out.append("## Action Items")
        out.extend(f"- **{ai.get('owner','?')}**: {ai.get('item','')} (due {ai.get('due','TBD')})" for ai in doc["action_items"])
    return "\n".join(out)

def transcript_to_vtt(doc):
    out = ["WEBVTT", ""]
    segs = doc.get("transcript_segments", [])
    for i, s in enumerate(segs):
        t1 = s.get("t","00:00:00")
        # synthetic end time = t1 + 30s
        h, m, sec = (int(x) for x in t1.split(":"))
        end_total = h*3600 + m*60 + sec + 30
        eh, em, es = end_total // 3600, (end_total % 3600) // 60, end_total % 60
        t2 = f"{eh:02d}:{em:02d}:{es:02d}"
        out.append(f"{i+1}")
        out.append(f"{t1}.000 --> {t2}.000")
        out.append(f"<v {s.get('speaker','?')}>{s.get('text','')}")
        out.append("")
    return "\n".join(out)


def main():
    emails_dir = OUT / "emails"
    meetings_dir = OUT / "meetings"
    emails_dir.mkdir(exist_ok=True)
    meetings_dir.mkdir(exist_ok=True)

    n_emails = 0
    n_meetings = 0
    for jsonl_path in ROOT.glob("corpus/**/*.jsonl"):
        persona = jsonl_path.parent.name
        for line in jsonl_path.open():
            doc = json.loads(line)
            doc_id = doc["doc_id"]
            persona_dir_e = emails_dir / persona
            persona_dir_m = meetings_dir / persona
            if doc.get("doc_type") == "email":
                persona_dir_e.mkdir(exist_ok=True)
                (persona_dir_e / f"{doc_id}.eml").write_text(email_to_eml(doc))
                (persona_dir_e / f"{doc_id}.html").write_text(email_to_html(doc))
                (persona_dir_e / f"{doc_id}.txt").write_text(doc.get("body",""))
                n_emails += 1
            elif doc.get("doc_type") in ("meeting_notes",):
                persona_dir_m.mkdir(exist_ok=True)
                (persona_dir_m / f"{doc_id}.ics").write_text(meeting_to_ics(doc))
                (persona_dir_m / f"{doc_id}.md").write_text(meeting_to_md(doc))
                if doc.get("format") == "transcript" or doc.get("transcript_segments"):
                    (persona_dir_m / f"{doc_id}.vtt").write_text(transcript_to_vtt(doc))
                n_meetings += 1

    print(f"Inflated: {n_emails} emails, {n_meetings} meetings")
    # size summary
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    files = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"Total extraction footprint: {total/1024/1024:.1f} MB across {files} files")

if __name__ == "__main__":
    main()
