"""LoRA fine-tuning of Qwen3-VL-4B-Instruct on CropCal's JSONL, as a plain loop.

Everything that matters for learning is in this one file, in order:
  1. data: JSONL record -> Qwen chat messages (system, [crop, screen, context], answer)
  2. encode: chat template + image patches; labels = -100 everywhere except the answer
  3. model: bf16 base, LoRA adapters on the language model's linear layers only
  4. train: forward -> loss -> backward (grad accumulation) -> clip -> AdamW -> cosine LR
  5. eval: val loss every N steps; adapter checkpoints; metrics.jsonl

Usage (on the Spark, from ~/cropcal/ml):
  python -m train.train_lora --data data/train_v1 --out runs/lora-v1 \
      --data-root-from "/Users/vedanthchamala/Projects/Calander Extension/ml" --data-root-to "$PWD"
  # smoke: add --limit 32 --max-steps 5 --eval-every 5
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import time
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"


# ----------------------------------------------------------------- 1. data

def load_jsonl(path: Path, root_from: str, root_to: str) -> list[dict]:
    recs = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        r["images"] = [p.replace(root_from, root_to) if root_from else p for p in r["images"]]
        recs.append(r)
    return recs


def to_messages(rec: dict) -> list[dict]:
    """Our JSONL is sharegpt-style with '<image>' placeholders; Qwen's processor
    wants typed content blocks. Two images, then the context text."""
    sys_msg, user_msg, asst_msg = rec["messages"]
    text = user_msg["content"].replace("<image>", "").lstrip("\n")
    return [
        {"role": "system", "content": [{"type": "text", "text": sys_msg["content"]}]},
        {"role": "user", "content": [{"type": "image"}, {"type": "image"}, {"type": "text", "text": text}]},
        {"role": "assistant", "content": [{"type": "text", "text": asst_msg["content"]}]},
    ]


# ----------------------------------------------------------------- 2. encode

class CropCalDataset(Dataset):
    def __init__(self, recs: list[dict], processor):
        self.recs = recs
        self.processor = processor

    def __len__(self) -> int:
        return len(self.recs)

    def __getitem__(self, i: int) -> dict:
        rec = self.recs[i]
        images = [Image.open(p).convert("RGB") for p in rec["images"]]
        msgs = to_messages(rec)
        prompt_text = self.processor.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
        full_text = self.processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
        prompt = self.processor(text=[prompt_text], images=images, return_tensors="pt")
        full = self.processor(text=[full_text], images=images, return_tensors="pt")
        n_prompt = prompt["input_ids"].shape[1]
        labels = full["input_ids"].clone()
        labels[:, :n_prompt] = -100  # learn only the answer tokens
        item = {k: v for k, v in full.items()}
        item["labels"] = labels
        item["n_prompt"] = n_prompt
        return item


def collate(items: list[dict], pad_id: int) -> dict:
    """Pad text to the longest sample; image patches are concatenated and the
    model splits them again using image_grid_thw."""
    L = max(it["input_ids"].shape[1] for it in items)
    ids = torch.full((len(items), L), pad_id, dtype=torch.long)
    att = torch.zeros((len(items), L), dtype=torch.long)
    lab = torch.full((len(items), L), -100, dtype=torch.long)
    # per-token modality ids (0 = text, 1 = image) that Qwen3-VL uses for M-RoPE
    mm = torch.zeros((len(items), L), dtype=torch.long)
    for b, it in enumerate(items):
        n = it["input_ids"].shape[1]
        ids[b, :n] = it["input_ids"][0]
        att[b, :n] = it["attention_mask"][0]
        lab[b, :n] = it["labels"][0]
        if "mm_token_type_ids" in it:
            mm[b, :n] = it["mm_token_type_ids"][0]
    batch = {"input_ids": ids, "attention_mask": att, "labels": lab,
             "pixel_values": torch.cat([it["pixel_values"] for it in items], dim=0),
             "image_grid_thw": torch.cat([it["image_grid_thw"] for it in items], dim=0)}
    if any("mm_token_type_ids" in it for it in items):
        batch["mm_token_type_ids"] = mm
    return batch


def make_processor(max_pixels: int, min_pixels: int):
    from transformers import AutoProcessor

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    ip = processor.image_processor
    # Qwen3-VL's image processor keeps the pixel budget in a SizeDict
    # (longest_edge = max pixels, shortest_edge = min pixels); Qwen2.5-VL used
    # min/max_pixels attributes. Our captures are already capped at 1400 px on
    # the long edge, so the default budget (2M px) never downscales them.
    size = getattr(ip, "size", None)
    if size is not None and hasattr(size, "longest_edge"):
        size.longest_edge, size.shortest_edge = max_pixels, min_pixels
    elif isinstance(size, dict):
        ip.size = {"shortest_edge": min_pixels, "longest_edge": max_pixels}
    if hasattr(ip, "max_pixels") and getattr(ip, "max_pixels", None) is not None:
        ip.max_pixels, ip.min_pixels = max_pixels, min_pixels
    return processor


# ----------------------------------------------------------------- 3. model

def make_model(lora_r: int, lora_alpha: int, lora_dropout: float, attn: str):
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText

    model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, dtype=torch.bfloat16, attn_implementation=attn)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    # Adapters on the language model's projections only; the vision tower and
    # the vision->language merger stay frozen for the first run.
    lcfg = LoraConfig(r=lora_r, lora_alpha=lora_alpha, lora_dropout=lora_dropout, bias="none",
                      target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)",
                      task_type="CAUSAL_LM")
    model = get_peft_model(model, lcfg)
    return model


# ----------------------------------------------------------------- 4/5. train + eval

@torch.no_grad()
def evaluate(model, loader, device, max_batches: int) -> float:
    model.eval()
    total, n = 0.0, 0
    for i, batch in enumerate(loader):
        if i >= max_batches:
            break
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.autocast("cuda", dtype=torch.bfloat16):
            out = model(**batch)
        total += out.loss.item()
        n += 1
    model.train()
    return total / max(1, n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/train_v1")
    ap.add_argument("--out", default="runs/lora-v1")
    ap.add_argument("--data-root-from", default="")
    ap.add_argument("--data-root-to", default="")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--max-steps", type=int, default=0, help="overrides epochs when > 0")
    ap.add_argument("--limit", type=int, default=0, help="use only the first N train records (smoke tests)")
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--warmup", type=float, default=0.03)
    ap.add_argument("--weight-decay", type=float, default=0.0)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--max-pixels", type=int, default=2_000_000)
    ap.add_argument("--min-pixels", type=int, default=65_536)
    ap.add_argument("--attn", default="sdpa")
    ap.add_argument("--eval-every", type=int, default=100)
    ap.add_argument("--eval-batches", type=int, default=25)
    ap.add_argument("--save-every", type=int, default=200)
    ap.add_argument("--log-every", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", action="store_true",
                    help="continue from the latest step-N checkpoint in --out (adapter + optimizer + step)")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(vars(args), indent=2))
    device = torch.device("cuda")

    processor = make_processor(args.max_pixels, args.min_pixels)
    pad_id = processor.tokenizer.pad_token_id
    train_recs = load_jsonl(Path(args.data) / "train.jsonl", args.data_root_from, args.data_root_to)
    val_recs = load_jsonl(Path(args.data) / "val.jsonl", args.data_root_from, args.data_root_to)
    if args.limit:
        train_recs = train_recs[: args.limit]
        val_recs = val_recs[: max(4, args.limit // 8)]
    train_ds, val_ds = CropCalDataset(train_recs, processor), CropCalDataset(val_recs, processor)
    coll = lambda items: collate(items, pad_id)  # noqa: E731
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=coll,
                              num_workers=args.workers, persistent_workers=args.workers > 0, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=coll,
                            num_workers=min(2, args.workers))

    model = make_model(args.lora_r, args.lora_alpha, args.lora_dropout, args.attn).to(device)
    model.print_trainable_parameters()
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=args.weight_decay, betas=(0.9, 0.999))

    start_step = 0
    if args.resume:
        # The Spark has rebooted under load twice; make interruptions cheap.
        ckpts = sorted((d for d in out.glob("step-*") if (d / "adapter_model.safetensors").exists()),
                       key=lambda d: int(d.name.split("-")[1]))
        if ckpts:
            ck = ckpts[-1]
            from peft import set_peft_model_state_dict
            from safetensors.torch import load_file
            set_peft_model_state_dict(model, load_file(ck / "adapter_model.safetensors"))
            if (ck / "optimizer.pt").exists():
                opt.load_state_dict(torch.load(ck / "optimizer.pt", map_location=device))
            start_step = int(ck.name.split("-")[1])
            print(f"resumed from {ck} at step {start_step}", flush=True)

    steps_per_epoch = len(train_loader) // args.grad_accum
    total_steps = args.max_steps or max(1, int(steps_per_epoch * args.epochs))
    warmup_steps = max(1, int(total_steps * args.warmup))

    def lr_at(step: int) -> float:
        if step < warmup_steps:
            return args.lr * (step + 1) / warmup_steps
        p = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return args.lr * 0.5 * (1 + math.cos(math.pi * p))

    print(f"train {len(train_ds)} samples, val {len(val_ds)}, {steps_per_epoch} steps/epoch, "
          f"{total_steps} total steps, effective batch {args.batch_size * args.grad_accum}", flush=True)
    metrics = open(out / "metrics.jsonl", "a")
    model.train()
    step, micro, t0, tokens, running = start_step, 0, time.time(), 0, 0.0
    done = step >= total_steps
    skip_micro = (start_step * args.grad_accum) % max(1, len(train_loader))  # resume mid-epoch position
    while not done:
        for i, batch in enumerate(train_loader):
            if skip_micro:
                if i < skip_micro:
                    continue
                skip_micro = 0
            batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
            with torch.autocast("cuda", dtype=torch.bfloat16):
                out_ = model(**batch)
                loss = out_.loss / args.grad_accum
            loss.backward()  # backprop through LoRA params only (base weights are frozen)
            running += loss.item()
            tokens += int(batch["attention_mask"].sum())
            micro += 1
            if micro % args.grad_accum != 0:
                continue
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            for g in opt.param_groups:
                g["lr"] = lr_at(step)
            opt.step()
            opt.zero_grad(set_to_none=True)
            step += 1
            if step % args.log_every == 0 or step == 1:
                el = time.time() - t0
                rec = {"step": step, "loss": running / args.log_every if step % args.log_every == 0 else running,
                       "lr": lr_at(step - 1), "tok_per_s": tokens / el, "elapsed_s": round(el)}
                print(json.dumps(rec), flush=True)
                metrics.write(json.dumps(rec) + "\n"); metrics.flush()
                running = 0.0
            if step % args.eval_every == 0 or step == total_steps:
                vl = evaluate(model, val_loader, device, args.eval_batches)
                rec = {"step": step, "val_loss": vl}
                print(json.dumps(rec), flush=True)
                metrics.write(json.dumps(rec) + "\n"); metrics.flush()
            if step % args.save_every == 0 or step == total_steps:
                ck = out / f"step-{step}"
                model.save_pretrained(ck)
                processor.save_pretrained(ck)
                torch.save(opt.state_dict(), ck / "optimizer.pt")
                print(f"saved {ck}", flush=True)
            if step >= total_steps:
                done = True
                break
    model.save_pretrained(out / "final")
    processor.save_pretrained(out / "final")
    print("done", flush=True)


if __name__ == "__main__":
    main()
