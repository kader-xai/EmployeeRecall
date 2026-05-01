# Training Runbook

End-to-end: take the synthetic corpus → trained LoRA + RAG index → working demo.

**Where to run**: a Linux GPU box. Recommended: RunPod A100 40GB (~$1.79/hr) or 2× RTX 4090 (~$0.50/hr on Vast.ai). Total cost target: **$15–25**.

**Total wall time**: ~3–6 hours for the full pipeline (mostly training).

---

## 0. Provision the GPU box

### RunPod (recommended, easiest)
1. Create account at runpod.io.
2. Deploy a Pod → "PyTorch 2.4" template → GPU: A100 PCIe 40GB.
3. Container disk: 40GB. Volume: 50GB.
4. Click "Start" → "Connect" → "Web Terminal" or SSH.

### Vast.ai (cheaper)
1. vast.ai → Search → filter for ≥24GB VRAM, CUDA 12.1+, Ubuntu 22.04.
2. Pick instance, click Rent.
3. SSH in.

Either way, you'll be in a Linux shell with `python3`, `nvidia-smi`, and CUDA available.

```bash
nvidia-smi   # confirm GPU visible
python3 --version  # 3.10+ required
```

---

## 1. Get the corpus onto the GPU box

You have three choices.

### Option A — push from your Mac (simple)
On your Mac:
```bash
cd "~/Library/CloudStorage/GoogleDrive-.../My Drive/Projects/ProjectRecall"
tar czf /tmp/ProjectRecall.tar.gz \
    personas cast accounts projects corpus \
    training scripts methodology README.md
# Transfer (replace HOST/PORT with your pod's SSH details)
scp -P PORT /tmp/ProjectRecall.tar.gz root@HOST:/workspace/
```
On the pod:
```bash
cd /workspace && tar xzf ProjectRecall.tar.gz
cd ProjectRecall
```

### Option B — push to a private GitHub repo, clone on pod
On your Mac: `git init && git add . && git commit -m init && git remote add origin <repo> && git push`.
On pod: `git clone <repo>`.

### Option C — re-generate on the pod
On the pod:
```bash
git clone <wherever-you-put-personas-and-scripts>
cd ProjectRecall
python3 scripts/generate_bulk_corpus.py
python3 scripts/generate_bulk_corpus_v2.py
```
(Deterministic — same output as your Mac.)

---

## 2. Install dependencies

```bash
cd /workspace/ProjectRecall
pip install -U pip wheel
pip install -r training/requirements.txt
# Smoke test
python3 -c "import torch, transformers, peft, trl, faiss, sentence_transformers; \
  print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
```

If unsloth fails to install (it can be picky about CUDA/torch versions), fallback:
```bash
pip install unsloth-zoo
# or fall back to pure HF — comment out unsloth in train_lora.py
# and use FastLanguageModel.from_pretrained → AutoModelForCausalLM.from_pretrained
```

---

## 3. Prepare training data

```bash
cd /workspace/ProjectRecall
python3 training/prep_training_data.py --persona priya
python3 training/prep_training_data.py --persona rohan
```

You should see something like:
```
Loaded 7000+ docs from corpus/priya
Built 2500+ SFT pairs
Wrote 2400+ train, 100+ eval pairs
Wrote 30000+ RAG chunks to ...rag_docs_priya.jsonl
```

Sanity check:
```bash
ls -la training/data/
# expect: sft_train_priya.jsonl, sft_eval_priya.jsonl, rag_docs_priya.jsonl, system_prompt_priya.txt
# (and matching for rohan)
```

---

## 4. Build the RAG index

```bash
python3 training/build_rag_index.py --persona priya
python3 training/build_rag_index.py --persona rohan
```

First run downloads the BGE embedder (~440MB). Embedding ~30k chunks takes 3–8 min on A100, ~15 min on CPU.

Outputs:
- `training/data/rag_index_{persona}.faiss`
- `training/data/rag_meta_{persona}.jsonl`

---

## 5. Train the LoRA

```bash
python3 training/train_lora.py --persona priya --epochs 3
```

Expected timing on A100 40GB:
- Load + LoRA wrap: 1–2 min
- Training (2.5k pairs × 3 epochs): **45 min – 1.5 hr**
- Save adapter: 30 sec

You'll see logging like:
```
{'loss': 1.42, 'learning_rate': 0.000196, 'epoch': 0.04}
{'loss': 1.18, 'learning_rate': 0.00019, 'epoch': 0.08}
...
```

Loss should drop from ~1.5 to ~0.6–0.9 by epoch 3.

Then for Rohan:
```bash
python3 training/train_lora.py --persona rohan --epochs 3
```

Outputs:
- `training/checkpoints/priya/` — LoRA adapter (small, ~150MB)
- `training/checkpoints/rohan/`

### Watching VRAM
```bash
watch -n 2 nvidia-smi
```
Should sit around 18–24 GB used on A100 with our settings. If you OOM:
- Drop `--batch-size 4 --grad-accum 4` to `--batch-size 2 --grad-accum 8`
- Or reduce `MAX_SEQ` from 4096 to 2048 in `train_lora.py`

---

## 6. Test inference (the demo)

```bash
python3 training/inference.py --persona priya \
  --question "What happened with Acme Corp?"
```

You should see an answer in Priya's voice with `[Source N]` citations and a sources list at the bottom showing which docs were retrieved.

Try the demo questions:
```bash
python3 training/inference.py --persona priya --interactive
> What happened with Acme Corp?
> Why did we credit Acme $4,200?
> Who is Mike Reyes?
> What was the soft commit on Premium?
```

For Rohan:
```bash
python3 training/inference.py --persona rohan --interactive
> Why are we using Postgres for events instead of Mongo?
> What was the May 2024 incident?
> Why did we kill the GraphQL gateway?
```

---

## 7. Run the eval

```bash
python3 training/eval.py --persona priya
python3 training/eval.py --persona rohan
```

Outputs:
- `training/eval_results_{persona}.json` — raw
- `training/eval_results_{persona}.md` — readable, drop into the video

Target metrics (synthetic data, well-trained):
- **History keyword score**: 0.65–0.85 (each question's must-mention keywords are in the answer)
- **Citations**: 4–8 per answer, mostly from the retrieved set
- **Style cosine** (vs held-out true reply): 0.55–0.75

---

## 8. Pull the checkpoints back

```bash
# On the pod
tar czf /tmp/checkpoints.tar.gz training/checkpoints training/data/rag_index_*.faiss training/data/rag_meta_*.jsonl training/eval_results_*

# On your Mac
scp -P PORT root@HOST:/tmp/checkpoints.tar.gz ~/Downloads/
```

LoRA adapters are tiny (~150MB each); the RAG indices are larger (~150MB) but still manageable.

---

## 9. Production deployment notes

For the video / a real demo, you can serve locally on a Mac with Apple Silicon:

```bash
# Convert merged model to MLX format (Apple Silicon optimized)
pip install mlx-lm
# After training with --save-merged on the GPU box, transfer the merged model
# Then on Mac:
mlx_lm.convert --hf-path ./training/checkpoints/priya_merged --mlx-path ./mlx-priya
mlx_lm.server --model ./mlx-priya --port 8080
```

Or with Ollama (also on Mac):
```bash
# Convert merged model to GGUF on the GPU box (or any Linux machine)
pip install llama-cpp-python
python3 -m llama_cpp.tools.convert ./training/checkpoints/priya_merged \
  --outfile priya.gguf --outtype q4_k_m

# Push to Ollama
echo 'FROM ./priya.gguf' > Modelfile
ollama create kalicoach-priya -f Modelfile
ollama run kalicoach-priya
```

You'd still need to wire up RAG separately (e.g. a small FastAPI shim that calls FAISS and proxies to Ollama).

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `OOM` during training | Lower batch size, or use `--load-in-4bit` more aggressively, or drop max_seq to 2048 |
| `unsloth` install fails | Use HF-only path: replace `FastLanguageModel.from_pretrained` with `AutoModelForCausalLM.from_pretrained` + `prepare_model_for_kbit_training` |
| RAG retrieval finds wrong docs | Increase `--top-k`, or tune chunk size in `prep_training_data.py` |
| Model doesn't cite sources | Lower `temperature` to 0.2, or strengthen the citation instruction in `inference.py:build_prompt` |
| Style match low | Train longer (5 epochs); ensure SFT pairs are filtered correctly to persona-authored only |
| Hallucinations | Check that retrieved sources actually contain the answer; if not, that's a RAG problem, not a LoRA problem |

---

## 11. Cost summary

| Step | Time | Cost (A100 @ $1.79/hr) |
|---|---|---|
| Provisioning | 5 min | $0.15 |
| Data prep | 2 min | $0.05 |
| RAG index build (×2) | 15 min | $0.45 |
| Training Priya | 90 min | $2.70 |
| Training Rohan | 90 min | $2.70 |
| Inference + eval | 30 min | $0.90 |
| Pull-back + cleanup | 10 min | $0.30 |
| **Total** | **~4 hours** | **~$7.25** |

Add buffer for first-time mistakes: budget $15–20.

---

## 12. What you have at the end

- Two trained LoRA adapters (Priya + Rohan)
- Two RAG indexes
- Eval reports showing performance
- A working `inference.py` for the demo
- Everything reproducible from the synthetic corpus
