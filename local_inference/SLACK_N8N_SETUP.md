# Slack + n8n demo recipe

Get from a freshly trained persona to **`/ask-priya What happened with Acme?`** working in Slack in about 30 minutes.

---

## End-to-end picture

```
Slack user
  │
  │  /ask-priya What happened with Acme?
  ▼
Slack workspace
  │
  │  POST  https://<tunnel>.trycloudflare.com/webhook/slack-persona
  ▼
Cloudflare quick tunnel  ───────►  n8n on your Mac (port 5678)
                                       │
                          ┌────────────┴────────────┐
                          │ workflow:               │
                          │  1. webhook receives    │
                          │  2. parse payload       │
                          │  3. ack Slack in <3 s   │
                          │  4. POST api.py         │
                          │  5. format reply        │
                          │  6. POST response_url   │
                          └────────────┬────────────┘
                                       │
                                       ▼
                              api.py on your Mac (port 8000)
                                       │
                          FAISS retrieve top-8 chunks
                                       │
                                       ▼
                              Ollama on your Mac (port 11434)
                                       │
                          LoRA-merged Qwen-7B generates
                                       │
                                       ▼
                              JSON {answer, sources}
                                       │
                                       ▼
                              n8n formats Slack message
                                       │
                                       ▼
                              Reply appears in channel
```

---

## What you need

- **Trained persona** — at minimum `priya-q4_k_m.gguf` and the FAISS index (`rag_index_priya.faiss`, `rag_meta_priya.jsonl`). See [training/COLAB.md](../training/COLAB.md).
- **A Slack workspace where you're an admin** — a free workspace you create yourself avoids any "needs admin approval" issues.
- **Mac with**: Ollama, Python 3.11+, Node 20+ (for npm-installed n8n), `cloudflared`, `gh` (optional).

Open four terminal tabs. You'll need them all running during the demo.

---

## Tab 1 — Ollama + persona model

```bash
brew install ollama
ollama serve &                # or open Ollama.app

cd local_inference
cp ../training/priya-q4_k_m.gguf .

# Replace the SYSTEM placeholder with the real persona prompt
sed -i '' "s|SYSTEM .*|SYSTEM \"\"\"$(cat ../training/data/system_prompt_priya.txt)\"\"\"|" Modelfile.priya

ollama create priya -f Modelfile.priya
ollama run priya 'hi' < /dev/null   # pre-warm so the first Slack call is fast
```

Verify:

```bash
ollama list                         # priya should appear
```

---

## Tab 2 — Persona API (FastAPI on port 8000)

```bash
cd local_inference
pip install -r requirements.txt
python api.py
```

Expected last line:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Verify from any other terminal:

```bash
curl http://127.0.0.1:8000/personas
# {"priya":{"chunks":17663}}

curl -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"persona":"priya","question":"What happened with Acme?"}' | head -c 200
```

If the second curl returns JSON with an `answer` field, the API is good.

---

## Tab 3 — n8n (port 5678)

Install once:

```bash
npm install -g n8n            # needs Node 20 or 22 (n8n hates Node 25+)
```

Run:

```bash
n8n start
```

First launch runs database migrations for ~30 s. Wait for:

```
Editor is now accessible via:
http://localhost:5678
```

In the browser:

1. Open <http://localhost:5678>.
2. Create the owner account on first launch (any email/password — local only).
3. **Workflows** → **+ Add workflow** → **⋮** menu top-right → **Import from File**.
4. Pick `local_inference/n8n_workflow.json`.

You should see six connected nodes:

```
Webhook (Slack Slash Command) → Parse Slack Payload ┐
                                                    ├─ Ack Slack       (instant ack to Slack)
                                                    └─ Call Persona API → Format Reply → Post to Slack
```

### Edit the API URL

Click the **Call Persona API** node. Change the URL from `http://host.docker.internal:8000/ask` to:

```
http://127.0.0.1:8000/ask
```

(`127.0.0.1`, not `localhost` — see Troubleshooting.)

Save (Cmd-S). **Toggle Active** in the top right — the slider must turn green.

Click the **Slack Slash Command** node. The right panel shows a **Production URL** like `http://localhost:5678/webhook/slack-persona`. That's the path Slack will hit through the tunnel.

---

## Tab 4 — Cloudflared tunnel

Slack needs HTTPS to reach your Mac.

```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:5678
```

Last lines of output:

```
Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):
https://<random-words>.trycloudflare.com
```

**Copy that URL.** The Slack request URL will be:

```
https://<random-words>.trycloudflare.com/webhook/slack-persona
```

Verify the tunnel reaches n8n:

```bash
curl -X POST https://<random-words>.trycloudflare.com/webhook/slack-persona \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'command=/ask-priya&text=hi&response_url=https://example.com'
```

You should get back JSON with `_Asking priya about: *hi* ..._`. If you do, every layer below Slack is wired.

> Quick tunnels generate a new URL on every restart. For a stable URL, set up a named Cloudflare tunnel.

---

## Slack app setup

At <https://api.slack.com/apps>:

### 1. Create the app

- **Create New App** → **From scratch**.
- Name: `Employee Recall`.
- Pick your workspace.

### 2. Add slash commands

Left sidebar → **Slash Commands** → **Create New Command**:

| Field | Value |
|---|---|
| Command | `/ask-priya` |
| Request URL | `https://<your-tunnel>.trycloudflare.com/webhook/slack-persona` |
| Short Description | Ask Priya |
| Usage Hint | What happened with Acme? |

Save. Repeat for `/ask-rohan` (same Request URL — the workflow routes by command name).

### 3. Add the bot scope

Left sidebar → **OAuth & Permissions** → **Bot Token Scopes** → **Add an OAuth Scope** → add `chat:write`. (`commands` was added automatically with the slash commands.)

### 4. Install

Same page, scroll to the top → **Install to Workspace** → **Allow**.

You don't need to copy or store any token — the Slack `response_url` in each slash command request is one-time and lets us reply without auth.

---

## Test it in Slack

In any channel of your workspace:

```
/ask-priya What happened with Acme Corp?
```

Within 1 second:

> _Asking priya about: **What happened with Acme Corp?** ..._

Within ~10–15 seconds:

> **priya:** Thanks for the patience while I dug into this. The seat-count on Acme's Q1 invoice came in 31 seats over (388 vs 357), about $14k. Mike Reyes (CFO) pushed on this in a working session on March 4 [Source 1]…
>
> **Sources:**
> • `meeting-acme-001` (2025-03-04) — score 0.74
> • `email-acme-003` (2025-03-03) — score 0.71

If you see this — you're done.

---

## Demo question script

Run these in order to build tension:

```
/ask-priya What happened with Acme Corp?
/ask-priya Why did we credit Acme $4,200 in Q1 2025?
/ask-priya Who is Mike Reyes and how should I handle him?
/ask-priya Why did Rekall churn?

/ask-rohan Why are we using Postgres for events instead of MongoDB?
/ask-rohan What was the May 2024 incident?
/ask-rohan Why did we kill the GraphQL gateway?
```

Closing demo (cross-persona, same event):

```
/ask-priya What was the May 2025 Hooli incident from the customer side?
/ask-rohan What was the May 2025 Hooli incident? Walk me through the root cause.
```

Same event, two grounded perspectives. That's the moment the audience gets it.

---

## Security

The cloudflared tunnel publishes your Mac to the public internet. **Anyone with the URL can hit your API.**

Minimum mitigations:

- **API key on `/ask`.** Read `os.environ['API_KEY']` in `api.py`, require an `X-API-Key` header, add the matching header in n8n's HTTP Request node.
- **Stop the tunnel when not demoing.** `Ctrl-C` in tab 4 kills public access immediately.
- **Don't put real PII in the corpus.** This setup is for demos with synthetic data.

For anything beyond a personal demo, deploy `api.py` on a private VPS with proper auth, TLS, rate limiting, and logging.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Slack: `dispatch_failed` / `operation_timeout` | n8n didn't ack within 3 s | Workflow not Active. Toggle it. Make sure `Parse Slack Payload` branches to **both** `Ack Slack` and `Call Persona API` in parallel. |
| `404` on the webhook | Using the test URL or workflow inactive | Use the **production** URL (`/webhook/...`), not the test URL (`/webhook-test/...`). And the workflow toggle must be green. |
| n8n: `ECONNREFUSED ::1:8000` | IPv6 resolution; api.py binds IPv4 | In the HTTP node URL, use `http://127.0.0.1:8000/ask` (not `localhost`). |
| n8n: `ECONNREFUSED 127.0.0.1:8000` | api.py not running | Restart tab 2 |
| Tunnel returns Cloudflare 1033 page | `cloudflared` died | Restart tab 4. The URL changes — update Slack and n8n. |
| First Slack call takes ~30 s | Ollama loading the model | Pre-warm: `ollama run priya 'hi' < /dev/null` before the demo |
| Tunnel URL changes on restart | Quick tunnels are ephemeral | Use a **named** Cloudflare tunnel for a stable hostname |
| n8n won't start, complains about Node version | Node 25+ incompatible | `nvm use 22 && npm install -g n8n` |
| Slack "/ask-priya is not recognised" | Slash commands not registered or app not installed | Recheck app config; reinstall |
| Generic-sounding answers, no voice | Modelfile `SYSTEM` block still placeholder | Replace with contents of `training/data/system_prompt_priya.txt`, then `ollama create priya -f Modelfile.priya` again |

---

## What's running where (cheat sheet)

| Tab | Process | Port | Public? |
|---|---|---|---|
| 1 | Ollama | 11434 | local only |
| 2 | api.py (FastAPI) | 8000 | local only |
| 3 | n8n | 5678 | local only |
| 4 | cloudflared | — | **public via tunnel** → forwards to 5678 |

Stop the demo: `Ctrl-C` in tab 4 first (kills public access), then in tabs 1–3 in any order.
