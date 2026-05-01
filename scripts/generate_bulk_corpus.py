"""
Persona Continuity — bulk corpus generator.

Produces routine emails + meeting notes around the hand-written deep storylines,
using the personas + accounts + projects manifests. Output is JSONL files in
corpus/{priya,rohan}/bulk_*.jsonl

This generator is deterministic given the seed (so re-runs are reproducible).
It uses templates + persona-aware phrasing rather than calling an external LLM,
so it produces volume cheaply. Quality is intentionally lower than the
hand-written storylines — the goal is realistic ambient corpus, not narrative.

Run:
    python scripts/generate_bulk_corpus.py
"""
import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
random.seed(42)

# ---------- load manifests ----------
priya = json.loads((ROOT / "personas/priya.json").read_text())
rohan = json.loads((ROOT / "personas/rohan.json").read_text())
cast = json.loads((ROOT / "cast/internal.json").read_text())
priya_accounts = json.loads((ROOT / "accounts/priya_accounts.json").read_text())["accounts"]
rohan_projects = json.loads((ROOT / "projects/rohan_projects.json").read_text())["projects"]

# ---------- helpers ----------

def daterange(start, end, step_days=1):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=step_days)

def business_day(dt):
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt

def random_business_dt(start_date, end_date):
    days = (end_date - start_date).days
    d = start_date + timedelta(days=random.randint(0, max(0, days)))
    d = business_day(d)
    return d.replace(
        hour=random.choice([8, 9, 9, 10, 10, 11, 13, 14, 14, 15, 16, 16, 17]),
        minute=random.choice([0, 7, 14, 22, 31, 38, 45, 52]),
        second=0,
        microsecond=0,
    )

def fmt_dt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S-05:00")

def write_jsonl(path, docs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

# ---------- Priya: routine email templates ----------

PRIYA_QUARTERLY_CHECKIN_TEMPLATES = [
    "Hi {contact_first},\n\nQuick quarterly check-in. From our side things have been steady — usage holding {usage_summary}, no support escalations on file. A few items worth flagging:\n\n• {item_1}\n• {item_2}\n\nWould 30 min late {month} work to do a proper review? Calendly: cal.com/priyasharma.\n\nBest,\nPriya",
    "Hi {contact_first},\n\nCircling back on our usual quarterly cadence. Wanted to flag two things: {item_1} and {item_2}. Otherwise the account is healthy from our side.\n\nLet me know if a working call makes sense. No rush.\n\nBest,\nPriya",
    "Hi {contact_first},\n\nQuick context: it's been about a quarter since our last sync and I want to keep us on cadence. Headline from our side — {usage_summary}. One ask: {item_1}.\n\nHappy to walk through whenever works.\n\nBest,\nPriya",
]

PRIYA_QBR_AGENDA_ITEMS = [
    "expand a workflow into the {team} team",
    "review the upcoming renewal terms language",
    "discuss the SSO upgrade we talked about last cycle",
    "walk through the new audit-log feature shipping next month",
    "align on adoption goals for next quarter",
    "review the integrations roadmap and your asks",
]

USAGE_SUMMARIES = [
    "around the usual range",
    "up about 12% over last quarter",
    "flat with last quarter",
    "slightly below trend, mostly seasonality",
    "trending up — your team has been active in workflow design",
]

PRIYA_INTERNAL_FLAG_TEMPLATES = [
    "Hey Lena —\n\nQuick FYI on {account_name}. {flag_summary}. Not urgent but worth knowing about heading into our next 1:1.\n\n— P",
    "Hey Lena — {flag_summary} on {account_name}. Will keep you posted.\n\n— P",
    "Lena — flagging on {account_name}: {flag_summary}. Will handle, want it on your radar.\n\n— P",
]

INTERNAL_FLAGS = [
    "primary contact has been slower than usual to respond",
    "saw a small dip in active users, going to dig in",
    "their security team is starting an annual review — Sasha looped",
    "rumor of a procurement consolidation on their side",
    "champion is potentially moving teams, watching",
    "they brought up a competitor name in our last call, no concern yet",
]

PRIYA_ACK_TEMPLATES = [
    "{name} — got it, will pick this up by EOD.\n\nP",
    "Thanks {name}, on it.\n\nP",
    "Hi {name}, no problem. I'll route to the right person and get back to you.\n\nBest,\nPriya",
    "{name} — confirming receipt. Will revert tomorrow.\n\nP",
]

def gen_priya_routine(account, year=2024):
    """Generate a quarter's worth of routine emails for one account."""
    out = []
    contact_first = (account.get("primary_contact", {}).get("name", "there").split() + ["there"])[0]
    contact_email = account.get("primary_contact", {}).get("email", f"contact@{account['id']}.com")
    account_id = account["id"]
    account_name = account["name"]

    # 4 quarterly check-ins per year
    quarters = [(year, m) for m in (3, 6, 9, 12)]
    for (y, m) in quarters:
        d = random_business_dt(datetime(y, m, 5), datetime(y, m, 25))
        thread_id = f"th-{account_id}-checkin-{y}q{m//3}"
        body = random.choice(PRIYA_QUARTERLY_CHECKIN_TEMPLATES).format(
            contact_first=contact_first,
            usage_summary=random.choice(USAGE_SUMMARIES),
            item_1=random.choice(PRIYA_QBR_AGENDA_ITEMS).format(team=random.choice(["ops", "finance", "product", "support"])),
            item_2=random.choice(PRIYA_QBR_AGENDA_ITEMS).format(team=random.choice(["ops", "finance", "product", "support"])),
            month=d.strftime("%B"),
        )
        out.append({
            "doc_id": f"email-{account_id}-checkin-{y}q{m//3}",
            "doc_type": "email",
            "thread_id": thread_id,
            "thread_position": 1,
            "date": fmt_dt(d),
            "from": {"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"},
            "to": [{"name": account.get("primary_contact", {}).get("name", "Contact"), "email": contact_email}],
            "cc": [],
            "subject": f"{account_name} — quick {d.strftime('%B')} check-in",
            "body": body,
            "tags": ["routine", "quarterly-checkin"],
            "related_account": account_id,
        })
        # plausible reply
        d2 = d + timedelta(days=random.randint(1, 4), hours=random.randint(1, 6))
        d2 = business_day(d2.replace(hour=10, minute=random.choice([12, 27, 41])))
        reply_text = random.choice([
            f"Hi Priya — yes, end of {d.strftime('%B')} works. Will grab a Calendly slot today.\n\nThanks,\n{contact_first}",
            f"Thanks Priya. {random.choice(['Looking at calendars now.', 'Sending a few times that work.', 'Will get back to you this week.'])}\n\n{contact_first}",
            f"{contact_first} here — appreciate the note. Yes to a call. Will reply with options.",
        ])
        out.append({
            "doc_id": f"email-{account_id}-checkin-{y}q{m//3}-reply",
            "doc_type": "email",
            "thread_id": thread_id,
            "thread_position": 2,
            "date": fmt_dt(d2),
            "from": {"name": account.get("primary_contact", {}).get("name", "Contact"), "email": contact_email},
            "to": [{"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"}],
            "cc": [],
            "subject": f"Re: {account_name} — quick {d.strftime('%B')} check-in",
            "body": reply_text,
            "tags": ["routine"],
            "related_account": account_id,
        })

    # internal flags 1-2 per year per account
    for _ in range(random.randint(1, 2)):
        d = random_business_dt(datetime(year, 1, 15), datetime(year, 12, 15))
        flag = random.choice(INTERNAL_FLAGS)
        out.append({
            "doc_id": f"email-{account_id}-internal-{d.strftime('%Y%m%d')}",
            "doc_type": "email",
            "thread_id": f"th-{account_id}-internal-{d.strftime('%Y%m')}",
            "thread_position": 1,
            "date": fmt_dt(d),
            "from": {"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"},
            "to": [{"name": "Lena Park", "email": "lena.park@northwind-saas.com"}],
            "cc": [],
            "subject": f"FYI — {account_name}",
            "body": random.choice(PRIYA_INTERNAL_FLAG_TEMPLATES).format(account_name=account_name, flag_summary=flag),
            "tags": ["internal", "fyi"],
            "related_account": account_id,
        })

    # 1-3 acknowledgment-style replies per year
    for _ in range(random.randint(1, 3)):
        d = random_business_dt(datetime(year, 2, 1), datetime(year, 11, 30))
        out.append({
            "doc_id": f"email-{account_id}-ack-{d.strftime('%Y%m%d%H%M')}",
            "doc_type": "email",
            "thread_id": f"th-{account_id}-misc-{d.strftime('%Y%m')}",
            "thread_position": 2,
            "date": fmt_dt(d),
            "from": {"name": "Priya Sharma", "email": "priya.sharma@northwind-saas.com"},
            "to": [{"name": account.get("primary_contact", {}).get("name", "Contact"), "email": contact_email}],
            "cc": [],
            "subject": f"Re: {account_name} — {random.choice(['quick question', 'about the integration', 'follow-up', 'access for new user', 'reporting question'])}",
            "body": random.choice(PRIYA_ACK_TEMPLATES).format(name=contact_first),
            "tags": ["routine"],
            "related_account": account_id,
        })
    return out

# ---------- Priya: weekly CSM sync meeting notes ----------

WEEKLY_DISCUSSION_LINES = [
    "Priya: {acc} renewal closing this month, on track.",
    "Priya: {acc} adoption stable.",
    "Priya: {acc} contact going on parental leave, transition contact named.",
    "Priya: {acc} expansion conversation queued for next QBR.",
    "Holly: {acc} EMEA DPA renegotiated.",
    "Holly: {acc} usage flat, watching.",
    "Marcus: pipeline update — three opportunities at proposal stage.",
    "Lena: reminder to log soft-commits in SFDC by Friday.",
    "Tomás: support escalation queue down 18% this week.",
    "Priya: {acc} added to expansion-watch — Premium upgrade interest.",
    "Holly: {acc} renewal paper sent, awaiting countersign.",
    "Diego (guest): integrations roadmap updated, pop-health workflow in scope for Q1.",
    "Lena: Q4 advocacy targets — need 2 more references signed.",
    "Priya: {acc} QBR scheduled, agenda drafted.",
]

def gen_priya_weekly_syncs(year=2024):
    out = []
    start = datetime(year, 1, 8)
    for week in range(50):
        d = start + timedelta(weeks=week)
        d = d.replace(hour=10, minute=0)
        d = business_day(d)
        lines = []
        for _ in range(random.randint(5, 9)):
            acc = random.choice(priya_accounts)
            lines.append(random.choice(WEEKLY_DISCUSSION_LINES).format(acc=acc["name"]))
        decisions = random.sample([
            "Soft-commits to be logged in SFDC by Friday",
            "Q4 advocacy push: target 2 more reference customers",
            "QBR cadence reset — quarterly minimum for tier-1 accounts",
            "Renewal forecast review moved to mid-month",
        ], k=random.randint(1, 2))
        out.append({
            "doc_id": f"meeting-cs-weekly-{d.strftime('%Y%m%d')}",
            "doc_type": "meeting_notes",
            "format": "structured",
            "date": fmt_dt(d),
            "title": "CSM weekly sync",
            "attendees": [
                {"name": "Lena Park"}, {"name": "Priya Sharma"}, {"name": "Holly Tran"},
                {"name": "Marcus Reilly"}, {"name": "Tomás Reyes"},
            ],
            "duration_min": 60,
            "agenda": ["account watchlist", "renewals closing", "pipeline", "advocacy"],
            "discussion": "\n".join(lines),
            "decisions": decisions,
            "action_items": [],
            "related_account": None,
            "tags": ["weekly-sync"],
        })
    return out

# ---------- Rohan: routine engineering content ----------

ROHAN_REVIEW_OPENERS = [
    "lgtm with one nit",
    "blocking — let's chat",
    "+1, ship it",
    "fwiw — alternative approach in thread, but I'm fine either way",
    "nope, let's revisit",
    "see thread comment",
    "approve once tests added",
]

ROHAN_DESIGN_OPENERS = [
    "Two options: (a) {a}, (b) {b}. Leaning (a).",
    "What problem are we actually solving here?",
    "TL;DR: I don't think we should do this. Long version below.",
    "What does the rollback look like?",
    "Let's not pre-optimize. Cheapest version that proves it works:",
    "I'd push back on this because we'll regret it in six months.",
]

ROHAN_TECH_REPLIES = [
    "Confirmed reproducible, opening a fix branch.",
    "Going to wait until Monday — Friday merge rule.",
    "Discussed with Maya. Agree, will revise the RFC.",
    "Not blocking but flagging: blast radius is bigger than the diff suggests.",
    "Yes. Same approach as we used in the Postgres migration.",
    "Disagree on the framing. The bug is the test, not the code. Will explain in review.",
    "Tracer-bullet first. Don't try to land the whole thing in one PR.",
    "Per ADR-0017, this stays in Postgres. Reopen in 12-18 months.",
]

ROHAN_PR_REVIEW_TEMPLATES = [
    "{opener}\n\n- nit: rename {var} to be clearer about ownership\n- consider: extract the retry logic to the SDK helper\n- {closing}",
    "{opener}\n\nblocking on the migration ordering — {detail}\n\notherwise looks fine.",
    "{opener}\n\nfwiw — {detail}\n\nlgtm assuming the test is added.",
]

def gen_rohan_routine(year=2024):
    out = []
    # weekly platform standup notes
    start = datetime(year, 1, 8)
    for week in range(50):
        d = start + timedelta(weeks=week)
        d = business_day(d.replace(hour=10, minute=30))
        bullets = random.sample([
            "rate-limiter v2 rollout — 50% complete, no incidents",
            "events service partition rotation worker shipped",
            "SCIM provisioning RFC under review",
            "API gateway migration phase 2 in flight",
            "auth token rotation cadence updated",
            "load test harness for ratelimit added",
            "Postgres replica lag investigation closed",
            "incident review followup AIs all closed except cross-region",
            "on-call rotation: next week Maya primary, Tarun secondary",
            "RFC backlog: 3 in review, 1 needs revision",
        ], k=random.randint(4, 7))
        out.append({
            "doc_id": f"meeting-platform-standup-{d.strftime('%Y%m%d')}",
            "doc_type": "meeting_notes",
            "format": "structured",
            "date": fmt_dt(d),
            "title": "Platform team weekly standup",
            "attendees": [{"name": n["name"]} for n in cast["platform_engineering_team"]],
            "duration_min": 30,
            "agenda": ["status round-robin", "blockers", "on-call handoff"],
            "discussion": "\n".join(f"- {b}" for b in bullets),
            "decisions": [],
            "action_items": [],
            "related_account": None,
            "tags": ["weekly-sync", "platform"],
        })

    # PR review style emails (synthetic)
    for _ in range(random.randint(40, 60)):
        d = random_business_dt(datetime(year, 1, 15), datetime(year, 12, 15))
        teammate = random.choice(cast["platform_engineering_team"])
        if teammate["name"] == "Rohan Iyer":
            continue
        body = random.choice(ROHAN_PR_REVIEW_TEMPLATES).format(
            opener=random.choice(ROHAN_REVIEW_OPENERS),
            var=random.choice(["clientCtx", "retryCount", "cfg", "session", "limit"]),
            detail=random.choice([
                "the migration must run before the deploy or we lose writes",
                "this changes the contract — need a deprecation note first",
                "the test isn't actually exercising the concurrency path",
                "happy path looks good, sad path has no coverage",
            ]),
            closing=random.choice(["nice cleanup", "ship after nits", "one more pass and lgtm"]),
        )
        out.append({
            "doc_id": f"email-pr-review-{d.strftime('%Y%m%d%H%M%S')}-{teammate['name'][0].lower()}",
            "doc_type": "email",
            "thread_id": f"th-pr-{d.strftime('%Y%m%d')}-{random.randint(100,999)}",
            "thread_position": 2,
            "date": fmt_dt(d),
            "from": {"name": "Rohan Iyer", "email": "rohan.iyer@northwind-saas.com"},
            "to": [{"name": teammate["name"], "email": teammate["email"]}],
            "cc": [],
            "subject": f"Re: PR #{random.randint(400, 1200)} — {random.choice(['ratelimit fix', 'metrics tag', 'partition rotation', 'sdk retry', 'auth refactor'])}",
            "body": body,
            "tags": ["pr-review"],
            "related_account": None,
        })

    # design replies / threads
    for _ in range(random.randint(30, 50)):
        d = random_business_dt(datetime(year, 1, 15), datetime(year, 12, 15))
        teammate = random.choice([n for n in cast["platform_engineering_team"] if n["name"] != "Rohan Iyer"])
        opener = random.choice(ROHAN_DESIGN_OPENERS).format(
            a=random.choice(["ship a behind-flag prototype", "extend the existing endpoint", "carry the v1 path for a quarter"]),
            b=random.choice(["build the v2 surface from scratch", "introduce a new service", "force a migration"]),
        )
        body = f"{opener}\n\n{random.choice(ROHAN_TECH_REPLIES)}\n\n—r"
        out.append({
            "doc_id": f"email-design-reply-{d.strftime('%Y%m%d%H%M%S')}-{teammate['name'][0].lower()}",
            "doc_type": "email",
            "thread_id": f"th-design-{d.strftime('%Y%m')}-{random.randint(10,99)}",
            "thread_position": random.randint(2, 5),
            "date": fmt_dt(d),
            "from": {"name": "Rohan Iyer", "email": "rohan.iyer@northwind-saas.com"},
            "to": [{"name": teammate["name"], "email": teammate["email"]}],
            "cc": [],
            "subject": f"Re: {random.choice(['design question', 'RFC feedback', 'thread continued', 'arch question'])}",
            "body": body,
            "tags": ["design", "internal"],
            "related_account": None,
        })

    return out

# ---------- main ----------

def main():
    priya_dir = ROOT / "corpus" / "priya"
    rohan_dir = ROOT / "corpus" / "rohan"

    for year in [2023, 2024, 2025]:
        # Priya routines for each account
        all_routine = []
        for acc in priya_accounts:
            all_routine.extend(gen_priya_routine(acc, year=year))
        write_jsonl(priya_dir / f"bulk_routine_{year}.jsonl", all_routine)

        # Priya weekly syncs
        write_jsonl(priya_dir / f"bulk_weekly_syncs_{year}.jsonl", gen_priya_weekly_syncs(year=year))

        # Rohan routines
        write_jsonl(rohan_dir / f"bulk_routine_{year}.jsonl", gen_rohan_routine(year=year))

    # summary
    print("Generated:")
    for p in sorted(ROOT.glob("corpus/**/*.jsonl")):
        size_kb = p.stat().st_size / 1024
        n = sum(1 for _ in p.open())
        print(f"  {p.relative_to(ROOT)}  {size_kb:.0f} KB  {n} docs")

if __name__ == "__main__":
    main()
