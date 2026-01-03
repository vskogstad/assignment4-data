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


def min_hash_deduplication(filepaths, num_hashes, num_bands, ngrams, output_dir):

    return