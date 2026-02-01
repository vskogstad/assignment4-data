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
            for line in f.readlines():
                key = hash(line)
                if counts[key] == 1:
                    g.writelines(line)


def min_hash_deduplication(
    filepaths, num_hashes, num_bands, ngrams, jaccard_threshold, output_dir, multiline_files=False
):
    # implementation of union find algo for clustering:
    if multiline_files:
        parent = {line: line for file in filepaths for line in file}
    else:
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
    available_files = filepaths

    for file in available_files:
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
    deduplicated = [min(v) for k, v in clusters.items()]  # "should" be random, but this is more reproducible

    for file in deduplicated:
        # print(file)
        outfile = Path(output_dir) / Path(file).name
        with open(file) as f, open(outfile, "w") as g:
            g.write(f.read())

    return


def min_hash_deduplication_multiline(filepaths, num_hashes, num_bands, ngrams, similarity_treshold, output_dir):
    """
    Variant of min_hash_deduplication that works on files containing a document per line. To avoid ram issues,
    this does not calculate the jaccardian instead using just the full minhash signature.

    """

    # implementation of union find algo for clustering:
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

    # min hash algorithm with bucketing and lsh
    random.seed(45)
    parent = {}
    buckets = [{} for _ in range(num_bands)]
    translator = str.maketrans("", "", string.punctuation)  # Remove punctation

    for file in filepaths:
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
                signature = [float('inf')] * num_hashes
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

    return
