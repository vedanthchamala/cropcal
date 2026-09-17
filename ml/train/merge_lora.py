"""Merge a LoRA adapter into the base model and save a plain HF checkpoint
(for vLLM serving or llama.cpp GGUF conversion).

Usage: python -m train.merge_lora --adapter runs/lora-v1/final --out runs/lora-v1/merged
"""
from __future__ import annotations

import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoProcessor

from train.train_lora import MODEL_ID


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    base = AutoModelForImageTextToText.from_pretrained(MODEL_ID, dtype=torch.bfloat16)
    model = PeftModel.from_pretrained(base, args.adapter).merge_and_unload()
    model.save_pretrained(args.out, safe_serialization=True)
    AutoProcessor.from_pretrained(args.adapter).save_pretrained(args.out)
    print("merged ->", args.out)


if __name__ == "__main__":
    main()
