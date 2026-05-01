# Train in Google Colab

The corpus already lives in your Google Drive — Colab can mount it directly. No file uploads needed.

## Setup (5 minutes)

1. **Open Colab** → https://colab.research.google.com
2. **File → Upload notebook** → upload `training/Persona_Continuity_Colab.ipynb` from your Drive
   *(or in Colab's file browser, navigate to `MyDrive/Projects/ProjectRecall/training/` and double-click)*
3. **Runtime → Change runtime type → Hardware: GPU**
   - **Pro/Pro+ (recommended):** select **A100** — defaults are tuned for 40GB (7B, MAX_SEQ=4096, batch=4)
   - **Pro:** **L4** also works; drop `MAX_SEQ` to 2048 in cell 3
   - **Free tier:** select **T4** and flip `MODEL_SIZE = '3b'`, `MAX_SEQ = 2048` in cell 3
4. **Runtime → Run all**
5. When the Drive mount cell prompts, click **"Connect to Google Drive"** and approve.

## Per-tier expectations

| Tier | GPU | Model | Time per persona | Notes |
|---|---|---|---|---|
| Pro / Pro+ | A100 40GB | Qwen2.5-7B (4-bit) | 25–40 min | **Default config.** MAX_SEQ=4096, batch=4, grad-accum=4 |
| Pro | L4 24GB | Qwen2.5-7B (4-bit) | 90–120 min | Drop `MAX_SEQ` to 2048, `BATCH_SIZE` to 2 |
| Free | T4 16GB | Qwen2.5-3B (4-bit) | 60–90 min | Set `MODEL_SIZE='3b'`, `MAX_SEQ=2048`, `BATCH_SIZE=2` |
| Free (slow) | T4 16GB | Qwen2.5-7B (4-bit) | 4–6 hr | Tight; `MAX_SEQ=1024`, `BATCH_SIZE=1`, `GRAD_ACCUM=16` |

## What the notebook does

1. Mounts your Google Drive (where the corpus already is)
2. Auto-detects `PROJECT_ROOT` (looks for `MyDrive/Projects/ProjectRecall`, falls back to a recursive glob)
3. Installs deps (~5 min one-time)
4. Runs `prep_training_data.py` for the chosen persona
5. Builds the RAG FAISS index
6. Trains the LoRA — checkpoints saved every 200 steps **back to Drive**, so a session disconnect doesn't lose work
7. Runs an inference smoke-test on the demo question
8. Lets you ask interactive questions
9. Runs the formal eval

## To train both personas

The notebook does one persona per run (model loading is the bottleneck). For the other:
1. Runtime → Restart runtime
2. Change `PERSONA = 'rohan'` in cell 3
3. Run all again

Both checkpoints end up in `training/checkpoints/{persona}/` on your Drive.

## Surviving session timeouts

- Free tier disconnects after ~12 hours of inactivity, sometimes sooner.
- Checkpoints save to Drive every 200 steps. If you reconnect, `trainer.train(resume_from_checkpoint=True)` would pick up — modify the train cell if you hit this.
- For T4 free training: keep the tab focused, use a tab-keep-alive extension, or upgrade to Pro for $10/mo (worth it for this).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `OutOfMemoryError` on T4 | Drop `MAX_SEQ` to 1024, `BATCH_SIZE` to 1, increase `GRAD_ACCUM` to 16 |
| `unsloth` install fails | Restart runtime, re-run install cell. Sometimes pip caches break. |
| "Drive mount needs auth" loops | Open the URL it prints in the *same browser* that owns the Drive |
| Drive path not found | Open the file browser (folder icon left sidebar), navigate to your project, right-click → Copy path, paste into `PROJECT_ROOT` |
| Eval cell can't find checkpoint | Make sure cell 7 finished saving — check `training/checkpoints/{persona}/adapter_config.json` exists |

## After training — keep the LoRA, drop the runtime

The LoRA adapters are small (~50–150 MB depending on model). They're already on your Drive after training. You can:
- Re-run inference cells anytime in a fresh Colab session (re-mount Drive, re-install deps, skip the train cell)
- Download the adapter folders and run locally if you have a GPU
- Convert to GGUF for Ollama / MLX for Mac inference (see main `RUNBOOK.md` section 9)

## Cost summary

- **Free Colab**: $0, with the caveats above
- **Colab Pro**: $9.99/mo, gets you faster GPUs and longer sessions — one month covers training both personas comfortably
- **Colab Pro+**: $49.99/mo — overkill for this project unless you're iterating
