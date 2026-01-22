import multiprocessing
import time

import numpy as np

t0 = time.time()
data = np.fromfile("cs336_data/data/tokenized/tokenized_paloma_c4_100_domains_validation.bin", dtype=np.uint16)

from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("gpt2")
# print(tokenizer.decode(data[0:2500]))
"""data2 = np.fromfile("cs336_data/data/tokenized/train.bin", dtype=np.uint16)
print(tokenizer.decode(data2[:4400]))
import sys

sys.exit()"""
import concurrent.futures
import os
from pathlib import Path

from classifiers import create_training_data
from tqdm import tqdm

# Set up all folder paths
wet_dir = Path.cwd() / Path("cs336_data/data/wet_files")
filtered_dir = Path.cwd() / Path("cs336_data/data/filtered")
deduplicated_dir = Path.cwd() / Path("cs336_data/data/deduplicated")
tagged_dir = Path.cwd() / Path("cs336_data/data/tagged")
tokenized_dir = Path.cwd() / Path("cs336_data/data/tokenized")


def process_single_wet_file(input_path: str, output_path: str):
    create_training_data(input_path, output_path)
    return output_path


# Set up the executor
num_cpus = len(os.sched_getaffinity(0))
with concurrent.futures.ProcessPoolExecutor(max_workers=num_cpus) as executor:
    # print(wet_dir)
    wet_filepaths = list(wet_dir.glob("*.wet.gz"))
    # print(wet_filepaths)

    futures = []
    for wet_filepath in wet_filepaths:
        # For each warc.wet.gz filepath, submit a job to the executor and get a future back
        wet_filename = str(Path(wet_filepath).name)
        future = executor.submit(process_single_wet_file, wet_filepath, filtered_dir / wet_filename)
        # Store the futures
        futures.append(future)
    # Iterate over the completed futures as they finish, using a progress bar
    # to keep track of progress.
    for future in tqdm(
        concurrent.futures.as_completed(futures),
        total=len(wet_filepaths),
    ):
        output_file = future.result()
        print(f"Output file written: {output_file}")


# 2 run deduplication. Exact first then fuzzy.
from deduplication import exact_deduplication

# only exact deduplication for now to keep number of folders down a bit.
filtered_filepaths = list(filtered_dir.glob("*.wet.gz"))
exact_deduplication(filtered_filepaths, deduplicated_dir)


# 3 Run quality score in parallel on a per line basis. add classification to each json line.
from classifiers import classify_quality


def score_single_file(input_filepath, output_filepath):
    with open(input_filepath) as f, open(output_filepath, "a") as g:
        for line in f.readlines():
            label, score = classify_quality(line)
            g.write(label + "\t" + line)
    return output_filepath


# Set up the executor
num_cpus = len(os.sched_getaffinity(0))
with concurrent.futures.ProcessPoolExecutor(max_workers=num_cpus) as executor:
    deduplicated_filepaths = list(deduplicated_dir.glob("*wet.gz"))

    futures = []
    for filepath in deduplicated_filepaths:
        # For each filtered filepath, submit a job to the executor and get a future b00ack
        deduplicated_filename = str(Path(filepath).name)
        future = executor.submit(score_single_file, filepath, tagged_dir / deduplicated_filename)
        # Store the futures
        futures.append(future)
    # Iterate over the completed futures as they finish, using a progress bar
    # to keep track of progress.
    for future in tqdm(
        concurrent.futures.as_completed(futures),
        total=len(filtered_filepaths),
    ):
        output_file = future.result()
        print(f"Output file written: {output_file}")

t1 = time.time()
print(f"before tokenization: {t1 - t0}")


# 4 Upweigh and tokenize final training set
def tokenize_and_add_eos(line):
    num_copies = 1
    tag, text = line.split("\t", 1)
    if tag == "paloma":
        num_copies = 2
    result = tokenizer.encode(text) + [tokenizer.eos_token_id]
    return result * num_copies


"""
results = []
num_repeats = 2
training_data = tokenized_dir / "train.bin"
tagged_filepaths = list(tagged_dir.glob("*wet.gz"))


for filepath in tagged_filepaths:
    with open(filepath) as f:
        json_file = f.readlines()
    for line in json_file:
        tag, text = line.split("\t", 1)
        num_copies = 1
        if tag == "paloma":
            num_copies = num_repeats
        result = tokenize_and_add_eos(text) * num_copies
        results.append(result)
        # Flatten the list of ids and convert to numpy array
all_ids = [token_id for sublist in results for token_id in sublist]
print(f"Tokenized and encoded {wet_filepath} into {len(all_ids)} tokens")
ids_array = np.array(all_ids, dtype=np.uint16)
ids_array.tofile(training_data)"""
num_repeats = 2
training_data = tokenized_dir / "train2.bin"
tagged_filepaths = list(tagged_dir.glob("*wet.gz"))


tokenizer = AutoTokenizer.from_pretrained("gpt2")

pool = multiprocessing.Pool(multiprocessing.cpu_count())
results = []
chunksize = 100
for filepath in tagged_filepaths:
    with open(filepath) as f, open(training_data, "ab") as train:
        lines = f.readlines()
        for result in tqdm(
            pool.imap(tokenize_and_add_eos, lines, chunksize=chunksize), total=len(lines), desc="Tokenizing lines"
        ):
            ids_array = np.array(result, dtype=np.uint16)
            ids_array.tofile(train)
pool.close()
pool.join()
# Flatten the list of ids and convert to numpy array
#all_ids = [token_id for sublist in results for token_id in sublist]
print(f"Tokenized and encoded {tagged_dir} into some tokens")
"""ids_array = np.array(all_ids, dtype=np.uint16)
ids_array.tofile(training_data)"""

data2 = np.fromfile("cs336_data/data/tokenized/train.bin", dtype=np.uint16)
print(tokenizer.decode(data2[:1400]))
t2 = time.time()
print(f"during tokenization: {t2 - t1}")
