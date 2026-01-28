import concurrent.futures
import multiprocessing
import os
import shutil
import time
from pathlib import Path

import numpy as np
from classifiers import create_training_data
from tqdm import tqdm
from transformers import AutoTokenizer

t0 = time.time()
data = np.fromfile("cs336_data/data/paloma/tokenized_paloma_c4_100_domains_validation.bin", dtype=np.uint16)

tokenizer = AutoTokenizer.from_pretrained("gpt2")

# Set up all folder paths
wet_dir = Path.cwd() / Path("cs336_data/data/wet_files")
filtered_dir = Path.cwd() / Path("cs336_data/data/filtered")
exact_deduplicated_dir = Path.cwd() / Path("cs336_data/data/exact_deduplicated")
deduplicated_dir = Path.cwd() / Path("cs336_data/data/deduplicated")
tagged_dir = Path.cwd() / Path("cs336_data/data/tagged")
tokenized_dir = Path.cwd() / Path("cs336_data/data/tokenized")

# Clear directories at pipeline start
for dir in [filtered_dir, exact_deduplicated_dir, deduplicated_dir, tagged_dir, tokenized_dir]:
    if dir.exists():
        shutil.rmtree(dir)
    dir.mkdir(parents=True, exist_ok=True)


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
from deduplication import exact_deduplication, min_hash_deduplication_multiline

# exact deduplication
filtered_filepaths = list(filtered_dir.glob("*.wet.gz"))
exact_deduplication(filtered_filepaths, exact_deduplicated_dir)

# fuzzy deduplication
exact_deduplicated_filepaths = list(exact_deduplicated_dir.glob("*.wet.gz"))
min_hash_deduplication_multiline(
    filepaths=exact_deduplicated_filepaths,
    num_hashes=50,
    num_bands=5,
    ngrams=3,
    similarity_treshold=0.8,
    output_dir=deduplicated_dir,
)


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


training_data = tokenized_dir / "train3.bin"
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
# all_ids = [token_id for sublist in results for token_id in sublist]
print(f"Tokenized and encoded {tagged_dir} into some tokens")
"""ids_array = np.array(all_ids, dtype=np.uint16)
ids_array.tofile(training_data)"""

data2 = np.fromfile(training_data, dtype=np.uint16)
print(len(data2), "number of tokens")
print(tokenizer.decode(data2[:100]))
t2 = time.time()
print(f"during tokenization: {t2 - t1}")
