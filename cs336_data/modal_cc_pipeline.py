import json
import os
import time
from collections.abc import Iterable
from pathlib import Path

import modal

app = modal.App("cc-wet-pipeline")

OUT_VOL = modal.Volume.from_name("cc-wet-out", create_if_missing=False)
HF_CACHE = modal.Volume.from_name("hf-cache", create_if_missing=False)
MODEL_VOL = modal.Volume.from_name("cc-models", create_if_missing=False)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "g++",
        "make",
        "python3-dev",
    )
    .pip_install(
        # PIN numpy for fasttext compatibility
        "numpy<2",
        "tqdm",
        "transformers",
        "huggingface_hub",
        "mmh3",
        "regex",
        "resiliparse",
        "FastWARC",
        "fasttext",
        "pybind11",
        "scipy",
    )
    .add_local_python_source("classifiers")
    .add_local_python_source("deduplication")
)


# -------------------------
# Helpers
# -------------------------

def chunked(xs: list[str], n: int) -> list[list[str]]:
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def stable_band_key(signature_slice: list[int]) -> int:
    """Deterministic band key across processes/containers."""
    import hashlib

    b = (",".join(map(str, signature_slice))).encode("utf-8")
    h = hashlib.blake2b(b, digest_size=8).digest()
    return int.from_bytes(h, "little", signed=False)


# -------------------------
# TOP-LEVEL worker functions
# (must be picklable for ProcessPoolExecutor)
# -------------------------

def _filter_one(args: tuple[str, str]) -> str:
    """Run create_training_data on one file; delete raw input after."""
    inp_str, out_str = args
    from classifiers import create_training_data

    create_training_data(inp_str, out_str)
    try:
        Path(inp_str).unlink(missing_ok=True)
    except Exception:
        pass
    return out_str


def _bucketize_one(args: tuple[str, int, int, int, int]) -> tuple[dict, list[dict]]:
    """Bucketize one exact-dedup file for fuzzy dedup."""
    file_str, num_hashes, num_bands, ngrams, r = args

    import string
    import unicodedata
    import mmh3

    parent: dict = {}
    buckets: list[dict] = [{} for _ in range(num_bands)]
    translator = str.maketrans("", "", string.punctuation)

    with open(file_str) as f:
        for line_num, line in enumerate(f):
            parent[(file_str, line_num)] = (file_str, line_num)

            clean = unicodedata.normalize("NFD", line.translate(translator).lower())
            words = clean.split()
            if len(words) < ngrams:
                continue

            doc_ngrams = set(" ".join(a) for a in zip(*[words[i:] for i in range(ngrams)]))

            sig = [2**63 - 1] * num_hashes
            for ng in doc_ngrams:
                for k in range(num_hashes):
                    h = mmh3.hash(ng, seed=k, signed=False)
                    if h < sig[k]:
                        sig[k] = h

            for j in range(num_bands):
                band = sig[j * r : (j + 1) * r]
                key = stable_band_key(band)
                buckets[j].setdefault(key, []).append(((file_str, line_num), sig))

    return parent, buckets


def _score_one(args: tuple[str, str]) -> str:
    """Quality filter one file -> tagged output."""
    inp_str, out_str = args
    from classifiers import classify_quality

    with open(inp_str) as f, open(out_str, "a") as g:
        for line in f:
            text = line.strip()
            label, score = classify_quality(text)
            if label == "paloma":
                g.write(label + "\t" + line)
    return out_str


# -------------------------
# Modal functions
# -------------------------

@app.function(
    image=image,
    cpu=16.0,
    memory=65536,       # 64 GiB
    ephemeral_disk=524288,  # MiB (~512 GiB)
    timeout=24 * 60 * 60,
    retries=2,
    volumes={
        "/out": OUT_VOL,
        "/root/.cache/huggingface": HF_CACHE,
        "/models": MODEL_VOL,
    },
    secrets=[modal.Secret.from_name("hf-token")]
)
def process_chunk(chunk_id: int, urls: list[str]):
    """
    One chunk job:
      download -> filter -> exact dedup -> fuzzy dedup -> quality -> tokenize shard
    """
    t0 = time.time()

    # IMPORTANT: set fork + env var before importing classifiers
    import multiprocessing as mp
    mp.set_start_method("fork", force=True)

    os.environ["CLASSIFIER_DIR"] = "/models/classifiers"
    
    import concurrent.futures
    import urllib.request
    import numpy as np
    from tqdm import tqdm
    from transformers import AutoTokenizer

    # import AFTER env var
    from deduplication import exact_line_deduplication

    base = Path("/tmp/work") / f"chunk_{chunk_id:03d}"
    wet_dir = base / "wet"
    filtered_dir = base / "filtered"
    exact_dir = base / "exact"
    dedup_dir = base / "dedup"
    tagged_dir = base / "tagged"
    for d in [wet_dir, filtered_dir, exact_dir, dedup_dir, tagged_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1) Download (threaded)
    def download_one(url: str) -> Path:
        fn = url.split("/")[-1]
        outp = wet_dir / fn
        if not outp.exists():
            urllib.request.urlretrieve(url, outp)
        return outp

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        wet_paths = list(
            tqdm(ex.map(download_one, urls), total=len(urls), desc=f"chunk {chunk_id} download")
        )

    # 2) Filter (process pool) — USE TOP-LEVEL WORKER
    ncpu = os.cpu_count() or 8
    filter_jobs = [(str(p), str(filtered_dir / p.name)) for p in wet_paths]

    with concurrent.futures.ProcessPoolExecutor(max_workers=ncpu) as ex:
        filtered_paths = list(
            tqdm(ex.map(_filter_one, filter_jobs), total=len(filter_jobs), desc=f"chunk {chunk_id} filter")
        )
    filtered_paths = [Path(p) for p in filtered_paths]

    # 3) Exact line dedup within chunk
    exact_line_deduplication(filtered_paths, exact_dir)
    exact_paths = list(exact_dir.glob("*.wet.gz"))

    # 4) Fuzzy dedup within chunk (stable band keys)
    num_hashes = 25
    num_bands = 5
    ngrams = 3
    r = num_hashes // num_bands

    bucket_jobs = [(str(p), num_hashes, num_bands, ngrams, r) for p in exact_paths]

    with concurrent.futures.ProcessPoolExecutor(max_workers=ncpu) as ex:
        futures = [ex.submit(_bucketize_one, job) for job in bucket_jobs]

        all_parent = {}
        all_buckets = [{} for _ in range(num_bands)]
        for fut in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc=f"chunk {chunk_id} bucketize",
        ):
            file_parent, file_buckets = fut.result()
            all_parent.update(file_parent)
            for bi in range(num_bands):
                for k, v in file_buckets[bi].items():
                    all_buckets[bi].setdefault(k, []).extend(v)

    from collections import defaultdict

    def find(x):
        while all_parent[x] != x:
            all_parent[x] = all_parent[all_parent[x]]
            x = all_parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        all_parent[ra] = rb

    def sig_sim(a, b):
        matches = sum(x == y for x, y in zip(a, b))
        return matches / len(a)

    sim_thresh = 0.8
    for band in all_buckets:
        for candidates in band.values():
            if len(candidates) <= 1:
                continue
            for i in range(len(candidates) - 1):
                id_i, sig_i = candidates[i]
                for j in range(i + 1, len(candidates)):
                    id_j, sig_j = candidates[j]
                    if sig_sim(sig_i, sig_j) > sim_thresh:
                        union(id_i, id_j)

    clusters = defaultdict(set)
    for doc_id in list(all_parent.keys()):
        clusters[find(doc_id)].add(doc_id)
    survivors = {min(v) for v in clusters.values()}

    for fp in exact_paths:
        outp = dedup_dir / fp.name
        with open(fp) as f, open(outp, "w") as g:
            for ln, line in enumerate(f):
                if (str(fp), ln) in survivors:
                    g.write(line)

    dedup_paths = list(dedup_dir.glob("*.wet.gz"))

    # 5) Quality filter -> tagged — USE TOP-LEVEL WORKER
    score_jobs = [(str(p), str(tagged_dir / p.name)) for p in dedup_paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=ncpu) as ex:
        tagged_paths = list(
            tqdm(ex.map(_score_one, score_jobs), total=len(score_jobs), desc=f"chunk {chunk_id} quality")
        )
    tagged_paths = [Path(p) for p in tagged_paths]

    # 6) Tokenize -> shard
    tokenizer = AutoTokenizer.from_pretrained("gpt2")

    shard_path = Path("/out/shards") / f"train_chunk_{chunk_id:03d}.bin"
    shard_path.parent.mkdir(parents=True, exist_ok=True)

    def iter_tagged_lines(paths: list[Path]) -> Iterable[str]:
        for p in paths:
            with open(p) as f:
                for line in f:
                    yield line

    def tokenize_line(line: str) -> list[int]:
        tag, doc = line.split("\t", 1)
        payload = json.loads(doc)
        text = payload if isinstance(payload, str) else payload.get("text", "")
        ids = tokenizer.encode(text) + [tokenizer.eos_token_id]
        return ids

    total_tokens = 0
    with open(shard_path, "ab") as out_f:
        for line in tqdm(iter_tagged_lines(tagged_paths), desc=f"chunk {chunk_id} tokenize"):
            ids = tokenize_line(line)
            total_tokens += len(ids)
            np.asarray(ids, dtype=np.uint16).tofile(out_f)

    metrics = {
        "chunk_id": chunk_id,
        "n_urls": len(urls),
        "n_filtered_files": len(filtered_paths),
        "n_exact_files": len(exact_paths),
        "n_dedup_files": len(dedup_paths),
        "n_tagged_files": len(tagged_paths),
        "total_tokens": total_tokens,
        "seconds": time.time() - t0,
    }
    mpath = Path("/out/metrics") / f"chunk_{chunk_id:03d}.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(metrics, indent=2))

    OUT_VOL.commit()
    return metrics


@app.function(
    image=image,
    cpu=4.0,
    memory=8192,
    timeout=6 * 60 * 60,
    volumes={"/out": OUT_VOL},
)
def merge_shards():
    shards_dir = Path("/out/shards")
    final_dir = Path("/out/final")
    final_dir.mkdir(parents=True, exist_ok=True)

    shard_paths = sorted(shards_dir.glob("train_chunk_*.bin"))
    out_path = final_dir / "train.bin"

    with open(out_path, "wb") as w:
        for p in shard_paths:
            with open(p, "rb") as r:
                while True:
                    buf = r.read(1024 * 1024)
                    if not buf:
                        break
                    w.write(buf)

    OUT_VOL.commit()
    return {"n_shards": len(shard_paths), "out": str(out_path)}


@app.local_entrypoint()
def main(
    url_file: str,
    chunk_size: int = 200,
    wave: int = 3,
):
    urls = [ln.strip() for ln in Path(url_file).read_text().splitlines() if ln.strip()]
    chunks = chunked(urls, chunk_size)

    for start in range(0, len(chunks), wave):
        ids = list(range(start, min(start + wave, len(chunks))))
        wave_chunks = chunks[start : start + wave]
        list(process_chunk.map(ids, wave_chunks))

    print("All chunk jobs finished. Merging shards...")
    print(merge_shards.remote())
