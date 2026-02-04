
from transformers import AutoTokenizer
import numpy as np

tokenizer = AutoTokenizer.from_pretrained("gpt2")

data2 = np.fromfile("data/train96.bin", dtype=np.uint16)
print(tokenizer.decode(data2[:100]))
print("\n\n\n\n\nValidation data")

data = np.fromfile("data/tokenized_paloma_c4_100_domains_validation.bin", dtype=np.uint16)

print(tokenizer.decode(data[:100]))