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
    signatures = {}
    for file in filepaths:
        with open(file) as f:
            text = f.read()
            translator = str.maketrans("", "", string.punctuation) # Remove punctation
            clean_text = text.translate(translator).lower()
            normalized_text = unicodedata.normalize("NFD", clean_text)
            word_list = normalized_text.split()
            doc_ngrams = [" ".join(a) for a in zip(*[word_list[i:] for i in range(ngrams)])] # builds the ngrams, will fail for documents with num_words < ngrams.
            #print(file_ngrams[:3])
            signature = []
            for k in range(num_hashes):
                signature.append(min([mmh3.hash(ngram, seed=k) for ngram in doc_ngrams])) # using mmh3 to get a distinct hash function for each k.
            sig = hash(tuple(signature))
        # store signature
        temp = signatures.get(sig, [])
        #print("before:", temp)
        temp.append(file)
        #print("after", temp)
        signatures[sig] = temp
    
    for value in signatures.values():
        if len(value) > 1:
            #print("-----More than one option", value)
            file = random.choice(value)
        else:
            file = value[0]
        outfile = Path(output_dir) / Path(file).name
        with open(file) as f, open(outfile, "w") as g: # not clean, but should work.
            deduplicated_lines = []
            for line in f.readlines():
                deduplicated_lines.append(line)
            g.writelines(deduplicated_lines)

    
    return
