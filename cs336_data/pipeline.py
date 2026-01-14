import numpy as np
import json

data = np.fromfile("cs336_data/data/tokenized/tokenized_paloma_c4_100_domains_validation.bin", dtype=np.uint16)

from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("gpt2")
print(tokenizer.decode(data[0:2500]))

import concurrent.futures
import os
import pathlib

from classifiers import create_training_data
from tqdm import tqdm


def process_single_wet_file(input_path: str, output_path: str):
    create_training_data(input_path, output_path)
    return output_path


# Set up the executor
num_cpus = len(os.sched_getaffinity(0))
executor = concurrent.futures.ProcessPoolExecutor(max_workers=num_cpus)
wet_filepaths = pathlib.Path.glob("cs336_data/data/wet_files")
output_directory_path = "cs336_data/data/filtered"
futures = []
for wet_filepath in wet_filepaths:
    # For each warc.wet.gz filepath, submit a job to the executor and get a future back
    wet_filename = str(pathlib.Path(wet_filepath).name)
    future = executor.submit(process_single_wet_file, wet_filepath, os.path.join(output_directory_path, wet_filename))
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

import sys

sys.exit()
from deduplication import exact_deduplication
# only exact deduplication for now to keep number of folders down a bit.
output_directory = "cs336_data/data/deduplicated"
filtered_filepaths = pathlib.Path.glob("cs336_data/data/filtered")
exact_deduplication(filtered_filepaths, output_directory)



# 3 Run quality score in parallel on a per line basis. add classification to each json line.

from classifiers import classify_quality

def score(input):
    with open(filepath, "a") as f:
        for line in filepath

        for _ in range(quality_upweight):
            f.write(text)


futures = []
for filtered_filepath in filtered_filepaths:
    # For each filtered filepath, submit a job to the executor and get a future back
    filtered_filename = str(pathlib.Path(filtered_filepath).name)
    future = executor.submit(process_single_wet_file, filtered_filepath, os.path.join(output_directory_path, filtered_filename))
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

# 4 Upweigh and tokenize final training set

num_repeats = 3
output_file = "data/paloma/tokenized_training.bin"
with open(output_file, "w") as t:
    for filtered_filepath in pathlib.Path.glob("cs336_data/data/tagged"):
        json_file = json.loads(filtered_filepath)
        for data_type, line in json_file:
            if data_type == "Paloma":
                for _ in range(num_repeats):
                    t.writelines(tokenizer.encode(line + "<|endoftext|>"))
            t.writelines(tokenizer.encode(line + "<|endoftext|>"))
