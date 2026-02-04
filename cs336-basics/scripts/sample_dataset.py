
from transformers import AutoTokenizer
import numpy as np

tokenizer = AutoTokenizer.from_pretrained("gpt2")
print("Training data:")
data2 = np.fromfile("data/train96.bin", dtype=np.uint16)
print(tokenizer.decode(data2[:1000]))
print("\n______________________________________________________________________________________________\n\n\n\nValidation data:")

data = np.fromfile("data/tokenized_paloma_c4_100_domains_validation.bin", dtype=np.uint16)

print(tokenizer.decode(data[:1000]))