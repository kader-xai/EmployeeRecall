"""
LoRA fine-tune of Qwen2.5-7B-Instruct (or Llama-3.1-8B-Instruct) on the
persona-style chat pairs produced by prep_training_data.py.

Uses unsloth for 2x speed + half VRAM. Runs on a single A100 40GB or
2x RTX 4090. ~6-8 hours for ~10k pairs at 3 epochs.

Outputs:
  training/checkpoints/{persona}/  (LoRA adapter weights)
  training/checkpoints/{persona}_merged/  (merged model, optional)

Run:
    python training/train_lora.py --persona priya
    python training/train_lora.py --persona rohan
"""
import argparse
import json
from pathlib import Path

# unsloth import must come BEFORE transformers
from unsloth import FastLanguageModel
import torch
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig

ROOT = Path(__file__).resolve().parent.parent

BASE_MODEL = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"  # bnb-4bit speeds load
MAX_SEQ = 4096


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, choices=["priya","rohan"])
    ap.add_argument("--data-dir", default=str(ROOT / "training" / "data"))
    ap.add_argument("--out-dir", default=str(ROOT / "training" / "checkpoints"))
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--save-merged", action="store_true",
                    help="Also save a merged (LoRA + base) model. Big.")
    args = ap.parse_args()

    train_path = Path(args.data_dir) / f"sft_train_{args.persona}.jsonl"
    eval_path = Path(args.data_dir) / f"sft_eval_{args.persona}.jsonl"
    out_dir = Path(args.out_dir) / args.persona
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading base model: {BASE_MODEL}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ,
        dtype=None,
        load_in_4bit=True,
    )

    print("Wrapping with LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Dataset — apply chat template
    def format_example(ex):
        text = tokenizer.apply_chat_template(
            ex["messages"], tokenize=False, add_generation_prompt=False
        )
        return {"text": text}

    print(f"Loading datasets from {train_path}")
    train_ds = load_dataset("json", data_files=str(train_path), split="train")
    eval_ds = load_dataset("json", data_files=str(eval_path), split="train")
    train_ds = train_ds.map(format_example, remove_columns=train_ds.column_names)
    eval_ds = eval_ds.map(format_example, remove_columns=eval_ds.column_names)
    print(f"  {len(train_ds)} train, {len(eval_ds)} eval")

    config = SFTConfig(
        output_dir=str(out_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=3,
        max_seq_length=MAX_SEQ,
        dataset_text_field="text",
        packing=False,
        report_to="none",  # set to "wandb" if you want tracking
        seed=42,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=config,
    )

    print("Starting training...")
    trainer.train()

    print(f"Saving LoRA adapter to {out_dir}")
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    if args.save_merged:
        merged_dir = Path(args.out_dir) / f"{args.persona}_merged"
        print(f"Saving merged model to {merged_dir}")
        model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")

    print("Done.")


if __name__ == "__main__":
    main()
