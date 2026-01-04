import string
import unicodedata
import random
import mmh3
from pathlib import Path


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
    # count unique lines
    doc_ngram_sets = {}
    buckets = [{} for _ in range(num_bands)]
    for file in filepaths:
        with open(file) as f:
            text = f.read()
            translator = str.maketrans("", "", string.punctuation) # Remove punctation
            clean_text = text.translate(translator).lower()
            normalized_text = unicodedata.normalize("NFD", clean_text)
            word_list = normalized_text.split()
            doc_ngrams = set(" ".join(a) for a in zip(*[word_list[i:] for i in range(ngrams)])) # builds the ngrams, will fail for documents with num_words < ngrams.
            doc_ngram_sets[file] = doc_ngrams
            #print(file_ngrams[:3])
            signature = []
            for k in range(num_hashes):
                signature.append(min([mmh3.hash(ngram, seed=k) for ngram in doc_ngrams])) # using mmh3 to get a distinct hash function for each k.
            
            # split signature into bands:
            r = num_hashes//num_bands
            for j in range(num_bands):
                sig_band = hash(tuple(signature[j*r:(j+1)*r])) 
                # store signature
                temp = buckets[j].get(sig_band, [])
                temp.append(file)
                buckets[j][sig_band] = temp
    
    clusters = []
    for bucket in buckets:
        for value in bucket.values():
            num_docs = len(value)
            if num_docs > 1:
                print(f"checking jaccard similarity for {num_docs} documents, among those {value[0]}, {value[1]}")
                for p1 in range(num_docs-1):
                    d1_ngrams = doc_ngram_sets[value[p1]]
                    for p2 in range(p1+1, num_docs):
                        if {value[p1], value[p2]} in clusters:
                            continue
                            print("could avoid computing this again")
                        d2_ngrams = doc_ngram_sets[value[p2]]
                        # Do jaccards similarity:
                        j = len(d1_ngrams & d2_ngrams) / len(d1_ngrams | d2_ngrams)
                        if j > jaccard_threshold:
                            print(f"jaccard similarity above threshold for {value[p1]}, {value[p2]}")
                            clusters.append({value[p1], value[p2]})

    print(clusters)
    merged_clusters = clusters
    # manipulate to get all clusters from matches in different buckets.
    """merged_clusters = [set() for _ in clusters]
    merges = 1
    while(merges > 1):
        merges = 0
        for cluster in clusters:
            for i in range(len(merged_clusters)):
                if len(cluster & merged_clusters[i]) > 0 or merged_clusters[i] == set():
                    merged_clusters[i] = merged_clusters[i] | cluster
                    merges = 1
                    break
                else:
                    merged_clusters[i] = cluster"""

    # remove one random choice from each cluster
    # 
    # merge across clusters into duplicates set  
    print(type(merged_clusters))
    unlucky = random.choice(list(merged_clusters[0]))  
    print("unlucky", unlucky)       
    print("<<<<<<<<<<<", merged_clusters)
    merged_clusters[0].remove(unlucky)
    duplicates = merged_clusters[0]


    for file in filepaths:
        print(file)
        if file in duplicates:
            continue
            #print("-----More than one option", value)
            #file = random.choice(list(value))
        outfile = Path(output_dir) / Path(file).name
        with open(file) as f, open(outfile, "w") as g: # not clean, but should work.
            deduplicated_lines = []
            for line in f.readlines():
                deduplicated_lines.append(line)
            g.writelines(deduplicated_lines)

    
    return
