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
#data = np.fromfile("cs336_data/data/paloma/tokenized_paloma_c4_100_domains_validation.bin", dtype=np.uint16)

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

import urllib.request
from pathlib import Path


def download_single_file(url, output_dir):
    """Download a single WET file from Common Crawl."""
    filename = url.strip().split("/")[-1]
    output_path = Path(output_dir) / filename
    if output_path.exists():
        return output_path  # skip already downloaded
    urllib.request.urlretrieve(url.strip(), output_path)
    return output_path


def download_wet_files(url_file, output_dir, max_workers=4):
    """
    Download WET files listed in a text file.
    url_file: path to .txt with one URL per line, e.g.:
        https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-18/segments/.../wet/CC-MAIN-...-00999.warc.wet.gz
    """
    import concurrent.futures

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with open(url_file) as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Downloading {len(urls)} WET files to {output_dir}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_single_file, url, output_dir): url
            for url in urls
        }
        for future in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(urls),
            desc="Downloading",
        ):
            try:
                path = future.result()
                print(f"Downloaded: {path.name}")
            except Exception as e:
                url = futures[future]
                print(f"Failed: {url} - {e}")

#download_wet_files("cs336_data/wet_urls_8.txt", wet_dir, max_workers=8)



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
t1 = time.time()

# 2 run deduplication.
from deduplication import exact_deduplication  # , min_hash_deduplication_multiline

# exact deduplication
filtered_filepaths = list(filtered_dir.glob("*.wet.gz"))
exact_deduplication(filtered_filepaths, exact_deduplicated_dir)
t2 = time.time()


# 2.5 run fuzzy deduplication
def write_fuzzy_deduplication(filepaths, buckets, parent, similarity_treshold, output_dir):
    from collections import defaultdict
    from pathlib import Path

    def union(a, b):
        # joins two sets at their root
        root_a, root_b = find(a), find(b)
        parent[root_a] = root_b

    def find(x):
        # finds root parent recursively
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def signature_similarity(sig1, sig2):
        matches = sum(a == b for a, b in zip(sig1, sig2))
        return matches / len(sig1)

    for bucket in buckets:
        print(len(bucket))
        for candidates in bucket.values():
            num_bucket_hashes = len(candidates)
            if num_bucket_hashes > 1:
                # print(f"checking full hash similarity for {num_bucket_hashes} documents, among those {hashes[0]}, {hashes[1]}")
                for i in range(num_bucket_hashes - 1):
                    id_i, sig_i = candidates[i]
                    for j in range(i + 1, num_bucket_hashes):
                        id_j, sig_j = candidates[j]
                        if signature_similarity(sig_i, sig_j) > similarity_treshold:
                            union(id_i, id_j)

    clusters = defaultdict(set)  # merge across clusters to single parent file
    for doc_id in parent.keys():
        clusters[find(doc_id)].add(doc_id)
    # print(clusters)
    # Pick earliest file from each cluster. "should" be using random, but this is more reproducible
    deduplicated = [min(v) for k, v in clusters.items()]  # random.choice(list(v)) for k, v...
    surviving_ids = set(deduplicated)
    for file in filepaths:
        # print(file)
        outfile = Path(output_dir) / Path(file).name
        with open(file) as f, open(outfile, "w") as g:
            for line_num, line in enumerate(f):
                if (file, line_num) in surviving_ids:
                    g.write(line)
                """else:
                    print(line[:200])
                    print("---")"""


def bucketize_single_file(file, num_hashes, num_bands, ngrams):
    """
    Variant of min_hash_deduplication that works on files containing a document per line. To avoid ram issues,
    this does not calculate the jaccardian instead using just the full minhash signature.

    """
    import string
    import unicodedata

    import mmh3

    # min hash algorithm with bucketing and lsh
    parent = {}
    buckets = [{} for _ in range(num_bands)]
    translator = str.maketrans("", "", string.punctuation)  # Remove punctation

    with open(file) as f:
        for line_num, line in enumerate(f):
            parent[(file, line_num)] = (file, line_num)
            clean_text = line.translate(translator).lower()
            normalized_text = unicodedata.normalize("NFD", clean_text)
            word_list = normalized_text.split()
            doc_ngrams = set(
                " ".join(a) for a in zip(*[word_list[i:] for i in range(ngrams)])
            )  # builds the ngrams, will fail for documents with num_words < ngrams.
            # doc_ngram_sets[(file, line_num)] = doc_ngrams
            # print(file_ngrams[:3])
            signature = [float("inf")] * num_hashes
            for ngram in doc_ngrams:
                for k in range(num_hashes):
                    h = mmh3.hash(ngram, seed=k)
                    if h < signature[k]:
                        signature[k] = h

            # split signature into bands:
            r = num_hashes // num_bands
            for j in range(num_bands):
                sig_band = hash(tuple(signature[j * r : (j + 1) * r]))
                # store signature
                temp = buckets[j].get(sig_band, [])
                temp.append(((file, line_num), signature))  # adding location and full signature to the bucket.
                buckets[j][sig_band] = temp
        return parent, buckets


# Set up the executor
num_cpus = len(os.sched_getaffinity(0))
num_hashes = 25
num_bands = 5
ngrams = 3
with concurrent.futures.ProcessPoolExecutor(max_workers=num_cpus) as executor:
    exact_deduplicated_filepaths = list(exact_deduplicated_dir.glob("*wet.gz"))

    futures = []
    for filepath in exact_deduplicated_filepaths:
        future = executor.submit(bucketize_single_file, filepath, num_hashes, num_bands, ngrams)
        futures.append(future)

    # Collect results
    all_parent = {}
    all_buckets = [{} for _ in range(num_bands)]  # num_bands
    for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
        file_parent, file_buckets = future.result()
        all_parent.update(file_parent)
        # merge buckets per band
        for i in range(num_bands):
            for k, v in file_buckets[i].items():
                temp = all_buckets[i].get(k, [])
                temp.extend(v)
                all_buckets[i][k] = temp


write_fuzzy_deduplication(
    exact_deduplicated_filepaths, all_buckets, all_parent, similarity_treshold=0.8, output_dir=deduplicated_dir
)

t3 = time.time()


# 3 Run quality score in parallel on a per line basis. add classification to each json line.
from classifiers import classify_quality


def score_single_file(input_filepath, output_filepath):
    with open(input_filepath) as f, open(output_filepath, "a") as g:
        for line in f.readlines():
            label, score = classify_quality(line)
            if label == "paloma":
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

t4 = time.time()
# print(f"before tokenization: {t4 - t0}")


# 4 Upweigh and tokenize final training set
def tokenize_and_add_eos(line):
    num_copies = 1
    tag, text = line.split("\t", 1)
    if tag == "paloma":
        num_copies = 1
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
t5 = time.time()
print(f"Total time: {t5 - t0}")
print(f"Filtering: {t1 - t0}")
print(f"Exact deduplication: {t2 - t1}")
print(f"Fuzzy deduplication: {t3 - t2}")
print(f"Quality classification: {t4 - t3}")
print(f"tokenization: {t5 - t4}")
