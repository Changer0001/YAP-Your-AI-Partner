from transformers import AutoTokenizer
from pathlib import Path

# Create output directory
out_dir = Path(__file__).parent / "tokenizer_assets"
out_dir.mkdir(parents=True, exist_ok=True)

# Download and save tokenizer
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
tokenizer.save_pretrained(out_dir)

print(f"Tokenizer saved to: {out_dir}")
