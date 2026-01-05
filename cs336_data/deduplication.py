import random
import string
import unicodedata
from collections import defaultdict
from pathlib import Path

import mmh3


def exact_deduplication(filepaths, output_directory):
    # count unique lines
    counts = {}
    for file in filepaths:
        with open(file) as f:
            for line in f.readlines():
                key = hash(line)
                counts[key] = counts.get(key, 0) + 1

    # create new files with only unique lines
    for file in filepaths:
        outfile = Path(output_directory) / Path(file).name
        with open(file) as f, open(outfile, "w") as g:
            deduplicated_lines = []
            for line in f.readlines():
                key = hash(line)
                if counts[key] == 1:
                    deduplicated_lines.append(line)
            g.writelines(deduplicated_lines)


def min_hash_deduplication(filepaths, num_hashes, num_bands, ngrams, jaccard_threshold, output_dir):
    # implementation of union find for clustering:
    parent = {file: file for file in filepaths}

    def union(a, b):
        # joins two sets at their root
        root_a, root_b = find(a), find(b)
        parent[root_a] = root_b

    def find(x):
        # finds root parent recursively
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    # min hash algorithm with bucketing and lsh
    doc_ngram_sets = {}
    buckets = [{} for _ in range(num_bands)]
    for file in filepaths:
        with open(file) as f:
            text = f.read()
            translator = str.maketrans("", "", string.punctuation)  # Remove punctation
            clean_text = text.translate(translator).lower()
            normalized_text = unicodedata.normalize("NFD", clean_text)
            word_list = normalized_text.split()
            doc_ngrams = set(
                " ".join(a) for a in zip(*[word_list[i:] for i in range(ngrams)])
            )  # builds the ngrams, will fail for documents with num_words < ngrams.
            doc_ngram_sets[file] = doc_ngrams
            # print(file_ngrams[:3])
            signature = []
            for k in range(num_hashes):
                signature.append(
                    min([mmh3.hash(ngram, seed=k) for ngram in doc_ngrams])
                )  # using mmh3 to get a distinct hash function for each k.

            # split signature into bands:
            r = num_hashes // num_bands
            for j in range(num_bands):
                sig_band = hash(tuple(signature[j * r : (j + 1) * r]))
                # store signature
                temp = buckets[j].get(sig_band, [])
                temp.append(file)
                buckets[j][sig_band] = temp

    for bucket in buckets:
        for docs in bucket.values():
            num_docs = len(docs)
            if num_docs > 1:
                # print(f"checking jaccard similarity for {num_docs} documents, among those {docs[0]}, {docs[1]}")
                for i in range(num_docs - 1):
                    d1_ngrams = doc_ngram_sets[docs[i]]
                    for j in range(i + 1, num_docs):
                        if parent[docs[i]] == docs[j] or parent[docs[j]] == docs[i]:
                            continue
                            print("could avoid computing this again")

                        d2_ngrams = doc_ngram_sets[docs[j]]
                        # Do jaccards similarity:
                        jaccard = len(d1_ngrams & d2_ngrams) / len(d1_ngrams | d2_ngrams)
                        if jaccard > jaccard_threshold:
                            # print(f"jaccard similarity above threshold for {docs[i]}, {docs[j]}")
                            union(docs[i], docs[j])

    clusters = defaultdict(set)  # merge across clusters to single parent file
    for file in filepaths:
        clusters[find(file)].add(file)
    # print(clusters)
    # Pick one random choice from each cluster
    deduplicated = [random.choice(list(v)) for k, v in clusters.items()]

    for file in deduplicated:
        # print(file)
        outfile = Path(output_dir) / Path(file).name
        with open(file) as f, open(outfile, "w") as g:  # not clean, but should work.
            deduplicated_lines = []
            for line in f.readlines():
                deduplicated_lines.append(line)
            g.writelines(deduplicated_lines)

    return
