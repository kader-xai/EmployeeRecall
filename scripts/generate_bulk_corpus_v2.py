"""
Persona Continuity — bulk corpus generator V2 (dense).

Higher-volume version of v1. Same persona-aware templating, but with:
- daily/near-daily cadence rather than quarterly
- multi-segment realistic transcripts (50-300 segments each)
- 1:1 meeting notes, monthly leadership reviews, customer-facing calls
- longer email bodies with more variation
- multi-paragraph internal status updates

Run:
    python scripts/generate_bulk_corpus_v2.py
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
random.seed(2026)

priya = json.loads((ROOT / "personas/priya.json").read_text())
rohan = json.loads((ROOT / "personas/rohan.json").read_text())
cast = json.loads((ROOT / "cast/internal.json").read_text())
priya_accounts = json.loads((ROOT / "accounts/priya_accounts.json").read_text())["accounts"]
rohan_projects = json.loads((ROOT / "projects/rohan_projects.json").read_text())["projects"]


def business_day(dt):
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt

def random_business_dt(start_date, end_date, hour_pool=None):
    if end_date <= start_date:
        end_date = start_date + timedelta(days=1)
    days = (end_date - start_date).days
    d = start_date + timedelta(days=random.randint(0, max(0, days)))
    d = business_day(d)
    return d.replace(
        hour=random.choice(hour_pool or [8,9,9,10,10,11,13,14,14,15,16,16,17]),
        minute=random.choice([0,7,14,22,31,38,45,52]), second=0, microsecond=0,
    )

def fmt_dt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S-05:00")

def write_jsonl(path, docs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


# ---------- pools ----------

PRIYA_LONG_BODY_OPENERS = [
    "Hi {name},\n\nQuick context: ",
    "Hi {name},\n\nCircling back on this — ",
    "Hi {name} — quick one: ",
    "Hi {name},\n\nFlagging early so it's on your radar: ",
    "Hi {name},\n\nWanted to walk through where we landed on this. ",
    "Hi {name},\n\nFew things on my mind heading into this week. First, ",
    "Hi {name},\n\nThanks for the patience while I dug into this. Where I landed: ",
]

PRIYA_TOPIC_SEGMENTS = [
    "the seat-utilization picture is steady — we're hovering around the 75% mark and that's roughly where we'd want it heading into the renewal conversation.",
    "a couple of users on your team have been opening tickets about the same thing (workflow trigger latency on the supplier-onboarding flow). I've routed those to Tomás's team and Diego is aware on the product side. Not a fire, but worth knowing.",
    "your security team's annual questionnaire came in last week. Sasha (our security lead) has it and is on the timeline you outlined.",
    "for our QBR I want to spend less time on the slides and more time on a working session — specifically around adoption in the {team} group.",
    "thinking about your renewal cycle, I want to put time on calendar with you, {econ_buyer}, and my VP Lena. The standard CSM-to-Ops conversation is fine but I'd rather get the right people in the room once than do four follow-ups.",
    "on the integrations side, the {feature} you asked about last quarter is on the Q3 roadmap. Diego (PM) can do a 30-minute deep-dive if helpful for your IT.",
    "from a billing perspective the new monthly-active-billed-user model has been smoother than the event-active model — fewer surprises in your finance close. Want to confirm that's holding from your side too.",
    "I've been thinking about the executive-sponsor program we discussed last cycle. The accounts where we have a real exec sponsor on the customer side are seeing 30%+ better outcomes in adoption metrics.",
    "your team's recent feedback on the audit log feature went directly to Diego. The change you asked about (export-to-CSV per workflow) is queued for the next minor release.",
]

PRIYA_LONG_BODY_CLOSERS = [
    "\n\nWould 30 min late {month} work? Calendly: cal.com/priyasharma.\n\nBest,\nPriya",
    "\n\nLet me know what makes sense — happy to walk through whenever's good for you.\n\nBest,\nPriya",
    "\n\nNo rush, just wanted it on the thread.\n\nBest,\nPriya",
    "\n\nWill plan to revisit on our next QBR unless something changes before then.\n\nBest,\nPriya",
    "\n\nHappy to keep this in writing or jump on a quick call — your preference.\n\nBest,\nPriya",
]

ROHAN_LONG_OPENERS = [
    "TL;DR: ",
    "Going to push back on this. ",
    "+1 to the thread. One thing to flag: ",
    "Two options on the table: ",
    "fwiw — ",
    "What problem are we actually solving here? ",
    "Read through the RFC. ",
]

ROHAN_LONG_BODY_PARAGRAPHS = [
    "The race-condition class of bug isn't going to be the failure mode at our current scale. It's the operational surprise — limits not matching contracts, alerts not firing on the right thresholds, runbooks pointing at deprecated tools.",
    "We've talked about cross-region tenant sync three times this year. The cheap version (configurable global limit + per-region cap) solves 80% of what we want and costs a quarter of the engineering. The expensive version (real CRDT, atomic global state) is the right answer eventually but not before we have customers who genuinely span regions in volumes that hurt us.",
    "I'd rather we ship the smaller version of this, learn from it in production for a quarter, and then decide whether we need the more expensive version. The history of platform decisions where we shipped the bigger version first is not great — billing-on-Mongo, the Kong plugin model, the original rate limiter.",
    "Let's not pre-optimize. The cheapest tracer-bullet that proves this works: stand up the new path behind a per-tenant flag, dual-run for a week, compare metrics, decide.",
    "What does the rollback look like? If we ship and it goes wrong, what's the path back? If the answer is 'we'd dual-write for a quarter and then cut over,' fine. If the answer is 'we can't really roll back,' it's a different conversation.",
    "I'm flagging blast radius. The change touches the gateway and the events service. Either alone is contained; together is the kind of compound deploy we wrote a whole runbook against in 2024.",
    "Auth is load-bearing. Any change here goes through Sasha for security review and Yelena for the session model. Not because process — because last time we cut a corner here we paid for it for two quarters.",
]

# ---------- daily-cadence emails per account ----------

def gen_priya_dense(account, year):
    out = []
    contact = account.get("primary_contact", {})
    contact_name = contact.get("name", "Contact")
    contact_first = contact_name.split()[0] if contact_name else "there"
    contact_email = contact.get("email", f"contact@{account['id']}.com")
    econ = account.get("economic_buyer", {}).get("name", contact_name)
    account_id = account["id"]
    account_name = account["name"]

    # Roughly 1 email per 5 business days per account = ~50 per year per account
    n_emails = random.randint(40, 60)
    for _ in range(n_emails):
        d = random_business_dt(datetime(year, 1, 8), datetime(year, 12, 18))
        topic = random.choice(PRIYA_TOPIC_SEGMENTS).format(
            team=random.choice(["operations","procurement","finance","support","IT"]),
            econ_buyer=econ,
            feature=random.choice(["SSO","SCIM provisioning","audit-log export","sandbox environment","API webhook","scheduled reports"]),
        )
        # 30% are multi-paragraph, others are short
        if random.random() < 0.3:
            extra_topic = random.choice(PRIYA_TOPIC_SEGMENTS).format(
                team=random.choice(["operations","procurement","finance","support","IT"]),
                econ_buyer=econ,
                feature=random.choice(["SSO","SCIM provisioning","audit-log export","sandbox environment","API webhook","scheduled reports"]),
            )
            body = (
                random.choice(PRIYA_LONG_BODY_OPENERS).format(name=contact_first)
                + topic
                + "\n\nSeparately, "
                + extra_topic
                + random.choice(PRIYA_LONG_BODY_CLOSERS).format(month=d.strftime("%B"))
            )
        else:
            body = (
                random.choice(PRIYA_LONG_BODY_OPENERS).format(name=contact_first)
                + topic
                + random.choice(PRIYA_LONG_BODY_CLOSERS).format(month=d.strftime("%B"))
            )

        thread_id = f"th-{account_id}-{d.strftime('%Y%m')}-{random.randint(100,999)}"
        out.append({
            "doc_id": f"email-{account_id}-{d.strftime('%Y%m%d%H%M')}",
            "doc_type": "email",
            "thread_id": thread_id,
            "thread_position": 1,
            "date": fmt_dt(d),
            "from": {"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"},
            "to": [{"name": contact_name, "email": contact_email}],
            "cc": [],
            "subject": f"{account_name} — {random.choice(['quick check-in','workflow question','renewal prep','QBR scheduling','feature update','followup','status'])}",
            "body": body,
            "tags": ["bulk-routine"],
            "related_account": account_id,
        })
        # 60% get a reply
        if random.random() < 0.6:
            d2 = business_day(d + timedelta(days=random.randint(1,4)))
            d2 = d2.replace(hour=random.choice([9,10,11,14,15,16]))
            reply = random.choice([
                f"Hi Priya — yes, that works. Will route to my team and come back with specifics.\n\n{contact_first}",
                f"{contact_first} here — appreciate the note. Let me get back to you on this by end of week.",
                f"Priya — saw this. Going to loop {econ} for the budget piece. Will revert.\n\n{contact_first}",
                f"Thanks Priya — agreed on next steps. Will see you at the QBR.\n\n{contact_first}",
                f"Hi Priya, sorry for slow reply — yes, let's get a calendar slot.\n\n{contact_first}",
                f"Priya, no concerns from my side. Proceed.\n\n{contact_first}",
            ])
            out.append({
                "doc_id": f"email-{account_id}-{d2.strftime('%Y%m%d%H%M')}-reply",
                "doc_type": "email",
                "thread_id": thread_id,
                "thread_position": 2,
                "date": fmt_dt(d2),
                "from": {"name": contact_name, "email": contact_email},
                "to": [{"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"}],
                "cc": [],
                "subject": f"Re: {account_name} — {random.choice(['quick check-in','workflow question','followup'])}",
                "body": reply,
                "tags": ["bulk-routine"],
                "related_account": account_id,
            })
            # 25% of replies get a follow-up
            if random.random() < 0.25:
                d3 = business_day(d2 + timedelta(days=random.randint(1,3)))
                d3 = d3.replace(hour=random.choice([9,10,14,15]))
                followup = random.choice([
                    f"Hi {contact_first}, perfect — sending the calendar invite.\n\nPriya",
                    f"Got it, {contact_first} — will keep this on the QBR agenda.\n\nP",
                    f"Thanks {contact_first}. I'll wait to hear from {econ} before next steps.\n\nP",
                    f"Hi {contact_first} — appreciate the speed. We'll have something to share by next Monday.\n\nBest,\nPriya",
                ])
                out.append({
                    "doc_id": f"email-{account_id}-{d3.strftime('%Y%m%d%H%M')}-followup",
                    "doc_type": "email",
                    "thread_id": thread_id,
                    "thread_position": 3,
                    "date": fmt_dt(d3),
                    "from": {"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"},
                    "to": [{"name": contact_name, "email": contact_email}],
                    "cc": [],
                    "subject": f"Re: {account_name} — followup",
                    "body": followup,
                    "tags": ["bulk-routine"],
                    "related_account": account_id,
                })
    return out


def gen_priya_long_meetings(year):
    """Generate full-length QBR meetings + 1:1s + customer calls with multi-segment transcripts."""
    out = []
    # 4 QBRs per year per deep-storyline account
    deep_accts = [a for a in priya_accounts if a.get("deep_storyline")]
    for acc in deep_accts:
        for q in [1,2,3,4]:
            month = q*3
            d = random_business_dt(datetime(year, month, 1), datetime(year, month, 25), hour_pool=[10,11,13,14,15])
            contact = acc.get("primary_contact", {})
            econ = acc.get("economic_buyer", {})
            attendees = [{"name":"Priya Sharma","company":"Northwind"}, {"name":"Lena Park","company":"Northwind"}]
            if contact: attendees.append({"name": contact.get("name","Contact"), "company": acc["name"]})
            if econ: attendees.append({"name": econ.get("name",""), "company": acc["name"]})
            # 60-120 transcript segments
            segs = []
            t = 0
            speakers = [a["name"] for a in attendees]
            qbr_content = [
                "Welcome, everyone. Quick agenda — value review, adoption, roadmap, any open items, and renewal posture.",
                "From our side, headline metrics: usage holding around the trend line, support escalations down, no SLA misses.",
                "Could you walk us through the workflow expansion you mentioned last quarter?",
                "We onboarded 12 new users to the platform last month. Adoption training session went well.",
                "What blockers are you seeing on the supplier-onboarding flow?",
                "Honestly, the parts-shortage triage template is the one that's saved us the most time. Eight hours per supervisor per week, conservatively.",
                "On the roadmap side — SSO is shipping in Q3, SCIM provisioning by end of year. Audit log advanced features in Q1 next year.",
                "What's the customer story on the new audit log? Our IT team has been asking.",
                "We're seeing it pick up across the enterprise tier. Field-level audit and CSV export per workflow are the headline features.",
                "Any concerns on the renewal side that we should be addressing now?",
                "Pricing's been brought up internally. Procurement will likely run a competitive bid.",
                "Standard playbook. We'd want to be ahead of the comparison conversation. Happy to provide adoption metrics and SLA history.",
                "On expansion — the supplier-compliance workflow is the natural next step. Want me to set up a scoping call with our solutions team?",
                "Yes, set that up. Mark from plant ops should be in that meeting.",
                "Will do. Hannah Chen will reach out to Mark directly.",
                "On the support side — escalation queue is down 18% this quarter. Anything you'd like more visibility into?",
                "Reporting is fine. The thing that would help most is a quarterly summary that I can send to my exec sponsor without editing.",
                "We can stand that up. I'll have something to share by next QBR.",
                "Last thing from our side — we're rolling out a customer advisory board for the platform team. Would you be open to a quarterly hour with our product team?",
                "Yes. Send me the cadence proposal.",
                "Great. We'll send for the first one in October.",
                "Any other items?",
                "Nothing from my side.",
                "From me, just a thanks for the partnership. Looking forward to the next quarter.",
                "Thanks, all.",
            ]
            for i, line in enumerate(qbr_content):
                t_str = f"00:{(t//60):02d}:{(t%60):02d}"
                segs.append({"t": t_str, "speaker": random.choice(speakers), "text": line})
                t += random.randint(8, 45)
            out.append({
                "doc_id": f"meeting-{acc['id']}-qbr-{year}q{q}",
                "doc_type": "meeting_notes",
                "format": "transcript",
                "date": fmt_dt(d),
                "title": f"{acc['name']} — Q{q} {year} QBR",
                "attendees": attendees,
                "duration_min": random.choice([45,60,75,90]),
                "transcript_segments": segs,
                "agenda": ["value review","adoption","roadmap","renewal posture"],
                "discussion": " ".join(s["text"] for s in segs[:6]),
                "decisions": random.sample([
                    "Q3 SSO upgrade scoping call to be set up",
                    "Customer advisory board cadence proposal to be sent",
                    "Quarterly exec summary report to be delivered",
                    "Adoption metrics package to be shared ahead of renewal",
                    "Solutions-team scoping call for expansion workflow",
                ], k=random.randint(1, 3)),
                "action_items": [
                    {"owner":"Priya","item":"Send CAB cadence proposal","due":fmt_dt(d+timedelta(days=14))},
                    {"owner":"Hannah Chen","item":"Reach out for expansion scoping","due":fmt_dt(d+timedelta(days=10))},
                ],
                "related_account": acc["id"],
                "tags": ["qbr","transcript"],
            })

        # monthly 1:1 with primary contact (12 per year)
        for m in range(1, 13):
            d = random_business_dt(datetime(year, m, 5), datetime(year, m, 25))
            out.append({
                "doc_id": f"meeting-{acc['id']}-1on1-{year}-{m:02d}",
                "doc_type": "meeting_notes",
                "format": "quick_notes",
                "date": fmt_dt(d),
                "title": f"{acc['name']} — monthly 1:1",
                "attendees": [{"name":"Priya Sharma"},{"name":acc.get('primary_contact',{}).get('name','Contact')}],
                "duration_min": 30,
                "raw_body": "\n".join([
                    f"- usage: {random.choice(['steady','up','flat','slight dip'])}",
                    f"- support: {random.choice(['no escalations','one P3 closed','watching SCIM ticket'])}",
                    f"- expansion: {random.choice(['no movement','interest in audit-log','soft commit on Premium','workshop scheduled'])}",
                    f"- relationship: {random.choice(['solid','build with econ buyer','need to renew exec sponsor visibility'])}",
                    f"- next 30d: {random.choice(['QBR prep','renewal kickoff','adoption push','quarterly report'])}",
                ]),
                "decisions": [],
                "action_items": [],
                "related_account": acc["id"],
                "tags": ["1on1"],
            })

    # Priya 1:1 with Lena (manager) — every 2 weeks = 26 per year
    for week in range(0, 50, 2):
        d = datetime(year,1,8) + timedelta(weeks=week)
        d = business_day(d.replace(hour=14, minute=0))
        out.append({
            "doc_id": f"meeting-priya-lena-1on1-{d.strftime('%Y%m%d')}",
            "doc_type": "meeting_notes",
            "format": "quick_notes",
            "date": fmt_dt(d),
            "title": "Priya <> Lena 1:1",
            "attendees": [{"name":"Priya Sharma"},{"name":"Lena Park"}],
            "duration_min": 30,
            "raw_body": "\n".join([
                f"- top of mind: {random.choice([a['name'] for a in priya_accounts])} — {random.choice(['renewal pacing','adoption gap','exec sponsor visibility','expansion scoping'])}",
                f"- pipeline: {random.choice(['3 in proposal','2 closing this month','quiet — focus on retention'])}",
                f"- people: {random.choice(['Arjun ramping well','Holly stretched on EMEA','Tomás escalation queue improving'])}",
                f"- ask from Lena: {random.choice(['exec air cover for Globex QBR','Diego time on roadmap conv','RevOps alignment on forecast'])}",
                f"- next 2 weeks: {random.choice(['QBR week','closing 2 renewals','Northwind Connect prep','handoff prep'])}",
            ]),
            "decisions": [],
            "action_items": [],
            "tags": ["1on1","internal"],
        })
    return out


# ---------- Rohan: dense engineering ----------

ROHAN_THREAD_BODIES = [
    lambda: random.choice(ROHAN_LONG_OPENERS) + random.choice(ROHAN_LONG_BODY_PARAGRAPHS) + "\n\n—r",
    lambda: random.choice(ROHAN_LONG_OPENERS) + random.choice(ROHAN_LONG_BODY_PARAGRAPHS) + "\n\n" + random.choice(ROHAN_LONG_BODY_PARAGRAPHS) + "\n\n—r",
    lambda: "fwiw — " + random.choice(ROHAN_LONG_BODY_PARAGRAPHS) + "\n\n—r",
    lambda: "What does the rollback look like? " + random.choice(ROHAN_LONG_BODY_PARAGRAPHS) + "\n\n—r",
]

def gen_rohan_dense(year):
    out = []
    teammates = [n for n in cast["platform_engineering_team"] if n["name"] != "Rohan Iyer"]
    adjacent = cast["adjacent_engineering"]

    # ~250 design/email threads per year
    for _ in range(250):
        d = random_business_dt(datetime(year, 1, 8), datetime(year, 12, 18))
        teammate = random.choice(teammates + adjacent)
        body = random.choice(ROHAN_THREAD_BODIES)()
        out.append({
            "doc_id": f"email-rohan-{d.strftime('%Y%m%d%H%M%S')}-{teammate['name'][0].lower()}",
            "doc_type": "email",
            "thread_id": f"th-eng-{d.strftime('%Y%m')}-{random.randint(100,999)}",
            "thread_position": random.randint(2, 6),
            "date": fmt_dt(d),
            "from": {"name": "Rohan Iyer", "email": "rohan.iyer@northwind-saas.com"},
            "to": [{"name": teammate["name"], "email": teammate["email"]}],
            "cc": [random.choice([{"name":"Devika Rao","email":"devika.rao@northwind-saas.com"},{"name":"Maya Williams","email":"maya.williams@northwind-saas.com"}])],
            "subject": f"Re: {random.choice(['RFC review','design Q','arch question','PR feedback','incident review','postmortem AI','RFC stub','design ping'])}",
            "body": body,
            "tags": ["design","internal"],
        })

    # weekly architecture review (50/year)
    for week in range(50):
        d = datetime(year,1,8) + timedelta(weeks=week)
        d = business_day(d.replace(hour=15, minute=0))
        rfcs = random.sample([p["title"] for p in rohan_projects], k=random.randint(1,3))
        bullets = []
        for r in rfcs:
            bullets.append(f"- {r}: {random.choice(['approved','revisions requested','deferred','killed','more spike data needed','sign-off pending Sasha'])}")
        out.append({
            "doc_id": f"meeting-arch-review-{d.strftime('%Y%m%d')}",
            "doc_type": "meeting_notes",
            "format": "structured",
            "date": fmt_dt(d),
            "title": "Platform architecture review",
            "attendees": [{"name":n["name"]} for n in cast["platform_engineering_team"]],
            "duration_min": 60,
            "agenda": ["RFC review queue","open arch questions","decisions"],
            "discussion": "\n".join(bullets) + "\n\n" + random.choice(ROHAN_LONG_BODY_PARAGRAPHS),
            "decisions": random.sample([
                "Defer ClickHouse migration until volume trigger hit",
                "Approve ratelimit-v2.1 'global limit + per-region' approach",
                "Kill GraphQL gateway, ship sparse-fieldsets instead",
                "Approve OIDC-first SSO architecture",
                "Defer multi-region Postgres write for one more quarter",
            ], k=random.randint(1,2)),
            "action_items": [
                {"owner":random.choice([n["name"] for n in cast["platform_engineering_team"]]),"item":"Update RFC with feedback","due":fmt_dt(d+timedelta(days=7))},
            ],
            "tags": ["arch-review","internal"],
        })

    # Rohan 1:1s — with Devika every other week + with Maya weekly + with Ankur biweekly
    for week in range(0, 50, 2):
        d = business_day(datetime(year,1,8) + timedelta(weeks=week))
        d = d.replace(hour=11, minute=0)
        out.append({
            "doc_id": f"meeting-rohan-devika-{d.strftime('%Y%m%d')}",
            "doc_type": "meeting_notes",
            "format": "quick_notes",
            "date": fmt_dt(d),
            "title": "Rohan <> Devika 1:1",
            "attendees": [{"name":"Rohan Iyer"},{"name":"Devika Rao"}],
            "duration_min": 30,
            "raw_body": "\n".join([
                f"- in flight: {random.choice([p['title'] for p in rohan_projects])}",
                f"- team: {random.choice(['Ankur ready for v2.1 lead','Maya stretching well','Yelena needs SSO scope clarity','Bryan SDK telemetry on track'])}",
                f"- platform health: {random.choice(['no incidents','one P3 last week','rate limiter clean','events partition lag normal'])}",
                f"- ask: {random.choice(['headcount slot for SDK eng','Sasha air cover on circuit breaker policy','PM time for events retention'])}",
            ]),
            "decisions": [],
            "action_items": [],
            "tags": ["1on1","internal"],
        })

    for week in range(50):
        d = business_day(datetime(year,1,8) + timedelta(weeks=week))
        d = d.replace(hour=14, minute=30)
        out.append({
            "doc_id": f"meeting-rohan-maya-{d.strftime('%Y%m%d')}",
            "doc_type": "meeting_notes",
            "format": "quick_notes",
            "date": fmt_dt(d),
            "title": "Rohan <> Maya 1:1",
            "attendees": [{"name":"Rohan Iyer"},{"name":"Maya Williams"}],
            "duration_min": 30,
            "raw_body": "\n".join([
                f"- design: {random.choice(['ratelimit-v2.1 cheap version','events partition rotation tuning','postgres replica lag investigation','circuit breaker policy'])}",
                f"- mentorship: {random.choice(['Ankur is excellent — give him design lead on v2.1','Bryan stretch SDK telemetry','Maya tech-lead transition path'])}",
                f"- platform: {random.choice(['SLO healthy','one slow query investigation','partition rotation worker shipped'])}",
            ]),
            "decisions": [],
            "action_items": [],
            "tags": ["1on1","mentorship","internal"],
        })

    # design office hours — 1/week
    for week in range(50):
        d = business_day(datetime(year,1,10) + timedelta(weeks=week))
        d = d.replace(hour=16, minute=0)
        out.append({
            "doc_id": f"meeting-design-office-hours-{d.strftime('%Y%m%d')}",
            "doc_type": "meeting_notes",
            "format": "quick_notes",
            "date": fmt_dt(d),
            "title": "Platform design office hours",
            "attendees": [{"name":"Rohan Iyer"},{"name":random.choice([n["name"] for n in cast["platform_engineering_team"]])}],
            "duration_min": 30,
            "raw_body": random.choice([
                "Walked through Ankur's draft on v2.1. Cheapest version: configurable global limit + per-region cap. He gets it. Will revise.",
                "Tarun: events retention partition rotation worker — agreed on design. Ship next sprint.",
                "Bryan: SDK telemetry rewrite. Discussed instrumentation choices. Use OpenTelemetry consistently.",
                "Yelena: SCIM endpoint shape. Decided to mirror Okta's expectations to minimize customer pain.",
                "Mei: load test harness updates for ratelimit. Looks good. One nit — multi-region clients.",
            ]),
            "decisions": [],
            "action_items": [],
            "tags": ["office-hours","internal"],
        })

    # platform-monthly leadership review (12/year)
    for m in range(1,13):
        d = random_business_dt(datetime(year,m,5), datetime(year,m,12), hour_pool=[14,15])
        out.append({
            "doc_id": f"meeting-platform-monthly-{year}-{m:02d}",
            "doc_type": "meeting_notes",
            "format": "structured",
            "date": fmt_dt(d),
            "title": f"Platform monthly leadership review — {d.strftime('%B %Y')}",
            "attendees": [{"name":"Devika Rao"},{"name":"Rohan Iyer"},{"name":"Maya Williams"},{"name":"Renee Akoth","title":"VP Engineering"}],
            "duration_min": 60,
            "agenda": ["roadmap status","incident review","headcount","customer escalations"],
            "discussion": "\n".join([
                f"Roadmap: {random.choice(['ratelimit-v2.1 in design','events partitioning shipped','SCIM in beta','API gateway migration phase 3 underway','SDK refresh in flight'])}",
                f"Incidents: {random.choice(['no Sev-1','1 Sev-2 with full postmortem','degradation, no customer impact','none'])}",
                f"Headcount: {random.choice(['1 open req','filling SRE backfill','no movement','interviewing for SDK eng'])}",
                f"Customer: {random.choice(['Hooli reference confirmed','Globex SLA discussion','Umbrella security review concluded','Acme SSO upgrade closed'])}",
            ]),
            "decisions": [],
            "action_items": [],
            "tags": ["monthly-review","leadership"],
        })
    return out


def main():
    priya_dir = ROOT / "corpus" / "priya"
    rohan_dir = ROOT / "corpus" / "rohan"

    for year in [2022, 2023, 2024, 2025]:
        # Priya dense per-account
        all_dense = []
        for acc in priya_accounts:
            all_dense.extend(gen_priya_dense(acc, year))
        write_jsonl(priya_dir / f"dense_routine_{year}.jsonl", all_dense)
        print(f"  priya routine {year}: {len(all_dense)} docs")

        # Priya long meetings (QBRs as transcripts)
        meetings = gen_priya_long_meetings(year)
        write_jsonl(priya_dir / f"dense_meetings_{year}.jsonl", meetings)
        print(f"  priya meetings {year}: {len(meetings)} docs")

        # Rohan dense
        rohan_docs = gen_rohan_dense(year)
        write_jsonl(rohan_dir / f"dense_eng_{year}.jsonl", rohan_docs)
        print(f"  rohan eng {year}: {len(rohan_docs)} docs")

    # final summary
    print("\n=== TOTAL ===")
    total_size = 0; total_docs = 0
    for p in sorted(ROOT.glob("corpus/**/*.jsonl")):
        s = p.stat().st_size; n = sum(1 for _ in p.open())
        total_size += s; total_docs += n
        print(f"  {p.relative_to(ROOT)}  {s/1024:.0f} KB  {n} docs")
    print(f"\nTotal: {total_size/1024/1024:.1f} MB  {total_docs} docs")

if __name__ == "__main__":
    main()
