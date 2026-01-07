#!/usr/bin/env python3
"""
Improved Paloma setup with proper document separation.

Options for handling document boundaries:
1. Add EOS token (<|endoftext|>) between documents (GPT-2 standard)
2. Add double newlines between documents
3. Save raw text with clear separators for classifier training
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from tqdm import tqdm

def install_deps():
    import subprocess
    subprocess.run([
        sys.executable, "-m", "pip", "install", 
        "datasets", "transformers", "numpy", "tqdm",
        "--break-system-packages", "-q"
    ])

print("Installing dependencies...")
install_deps()

from datasets import load_dataset
from transformers import AutoTokenizer


def tokenize_with_eos_separator(dataset, tokenizer, output_bin: Path):
    """
    Tokenize with EOS token between documents.
    This is the standard approach for GPT-2 style training.
    
    The EOS token (token ID 50256 for GPT-2) signals document boundaries,
    allowing the model to learn to "reset" between documents.
    """
    all_tokens = []
    eos_token_id = tokenizer.eos_token_id  # 50256 for GPT-2
    
    print(f"Using EOS token: '{tokenizer.eos_token}' (id={eos_token_id})")
    
    for example in tqdm(dataset, desc="Tokenizing with EOS separation"):
        text = example.get('text', '')
        if text:
            tokens = tokenizer.encode(text, add_special_tokens=False)
            all_tokens.extend(tokens)
            all_tokens.append(eos_token_id)  # Add EOS after each document
    
    tokens_array = np.array(all_tokens, dtype=np.uint16)
    tokens_array.tofile(output_bin)
    
    return tokens_array


def save_raw_text_with_separators(dataset, output_txt: Path, output_jsonl: Path):
    """
    Save raw text in two formats:
    1. Plain text with clear document separators (for inspection)
    2. JSONL with one document per line (for classifier training)
    """
    SEPARATOR = "\n\n" + "="*80 + "\n" + "=== NEW DOCUMENT ===" + "\n" + "="*80 + "\n\n"
    
    with open(output_txt, 'w', encoding='utf-8') as f_txt, \
         open(output_jsonl, 'w', encoding='utf-8') as f_jsonl:
        
        for i, example in enumerate(tqdm(dataset, desc="Saving raw text")):
            text = example.get('text', '')
            
            # Get metadata if available
            metadata = {k: v for k, v in example.items() if k != 'text'}
            
            # Write to plain text file with separator
            if i > 0:
                f_txt.write(SEPARATOR)
            f_txt.write(text)
            
            # Write to JSONL (one doc per line, perfect for classifier training)
            doc = {'text': text, 'doc_id': i, **metadata}
            f_jsonl.write(json.dumps(doc, ensure_ascii=False) + '\n')
    
    print(f"Saved {i+1} documents")


def create_token_to_doc_mapping(dataset, tokenizer, output_path: Path):
    """
    Create a mapping file that records document boundaries in token space.
    This allows you to recover which document each token belongs to.
    
    Format: List of (start_token_idx, end_token_idx, doc_id) tuples
    """
    boundaries = []
    current_pos = 0
    eos_token_id = tokenizer.eos_token_id
    
    for doc_id, example in enumerate(tqdm(dataset, desc="Computing boundaries")):
        text = example.get('text', '')
        if text:
            tokens = tokenizer.encode(text, add_special_tokens=False)
            num_tokens = len(tokens) + 1  # +1 for EOS
            
            boundaries.append({
                'doc_id': doc_id,
                'start_token': current_pos,
                'end_token': current_pos + num_tokens - 1,  # -1 because end is inclusive
                'num_tokens': num_tokens
            })
            current_pos += num_tokens
    
    with open(output_path, 'w') as f:
        json.dump(boundaries, f)
    
    print(f"Saved document boundaries for {len(boundaries)} documents")
    return boundaries


def verify_separation(bin_path: Path, tokenizer, num_samples: int = 3):
    """Verify that document separation is working correctly."""
    data = np.fromfile(bin_path, dtype=np.uint16)
    eos_token_id = tokenizer.eos_token_id
    
    # Find EOS positions
    eos_positions = np.where(data == eos_token_id)[0]
    
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}")
    print(f"Total tokens: {len(data):,}")
    print(f"EOS tokens found: {len(eos_positions):,}")
    print(f"Number of documents: {len(eos_positions)}")
    
    # Show a few document boundaries
    print(f"\nShowing {num_samples} document boundaries:")
    print("-"*60)
    
    for i in range(min(num_samples, len(eos_positions) - 1)):
        # Get tokens around the EOS
        eos_pos = eos_positions[i]
        start = max(0, eos_pos - 20)
        end = min(len(data), eos_pos + 21)
        
        snippet = data[start:end]
        text = tokenizer.decode(snippet)
        
        # Mark the EOS position
        before_eos = tokenizer.decode(data[start:eos_pos])
        eos_token = tokenizer.decode([data[eos_pos]])
        after_eos = tokenizer.decode(data[eos_pos+1:end])
        
        print(f"\nDocument boundary {i+1} (token position {eos_pos}):")
        print(f"  ...{before_eos[-50:] if len(before_eos) > 50 else before_eos}")
        print(f"  [EOS: '{eos_token}']")
        print(f"  {after_eos[:50] if len(after_eos) > 50 else after_eos}...")
    
    print("-"*60)


def main():
    output_dir = Path("./data/paloma")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*60)
    print("Downloading Paloma C4 100 domains validation set...")
    print("="*60)
    
    try:
        dataset = load_dataset(
            "allenai/paloma",
            name="c4_100_domains",
            split="val",
            trust_remote_code=True
        )
    except Exception as e:
        print(f"\nError: {e}")
        print("\nPlease accept the license at:")
        print("https://huggingface.co/datasets/allenai/paloma")
        print("\nThen login: huggingface-cli login")
        return
    
    print(f"\nDownloaded {len(dataset)} documents")
    
    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    
    # 1. Save raw text for classifier training
    print("\n" + "="*60)
    print("Step 1: Saving raw text files (for classifier training)")
    print("="*60)
    
    save_raw_text_with_separators(
        dataset,
        output_dir / "paloma_c4_100_domains_val.txt",
        output_dir / "paloma_c4_100_domains_val.jsonl"
    )
    
    # 2. Tokenize with EOS separation
    print("\n" + "="*60)
    print("Step 2: Tokenizing with EOS document separators")
    print("="*60)
    
    bin_path = output_dir / "tokenized_paloma_c4_100_domains_validation.bin"
    tokens = tokenize_with_eos_separator(dataset, tokenizer, bin_path)
    
    print(f"\nSaved: {bin_path}")
    print(f"Total tokens: {len(tokens):,}")
    print(f"File size: {bin_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    # 3. Create document boundary mapping
    print("\n" + "="*60)
    print("Step 3: Creating document boundary mapping")
    print("="*60)
    
    create_token_to_doc_mapping(
        dataset, 
        tokenizer, 
        output_dir / "document_boundaries.json"
    )
    
    # 4. Verify
    print("\n" + "="*60)
    print("Step 4: Verification")
    print("="*60)
    
    verify_separation(bin_path, tokenizer)
    
    # Summary
    print("\n" + "="*60)
    print("OUTPUT FILES")
    print("="*60)
    print(f"""
Files created in {output_dir}:

1. tokenized_paloma_c4_100_domains_validation.bin
   - Tokenized data with EOS tokens between documents
   - Load with: np.fromfile(path, dtype=np.uint16)

2. paloma_c4_100_domains_val.jsonl
   - One JSON document per line (for classifier training)
   - Each line: {{"text": "...", "doc_id": N, ...}}

3. paloma_c4_100_domains_val.txt
   - Human-readable with clear separators
   - For manual inspection

4. document_boundaries.json
   - Maps token positions to document IDs
   - Useful for analysis

To load the tokenized data:
    data = np.fromfile('{bin_path}', dtype=np.uint16)
    
To find document boundaries:
    eos_positions = np.where(data == 50256)[0]
    
To load JSONL for classifier training:
    with open('paloma_c4_100_domains_val.jsonl') as f:
        docs = [json.loads(line) for line in f]
""")


if __name__ == "__main__":
    main()