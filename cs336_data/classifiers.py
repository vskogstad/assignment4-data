import json
import random
import time
from pathlib import Path

import fasttext
import nltk
import regex as re
from fastwarc.stream_io import *
from fastwarc.warc import ArchiveIterator, WarcRecordType, has_block_digest
from resiliparse.extract.html2text import extract_plain_text
from resiliparse.parse.encoding import detect_encoding

# Load once at module level
LANG_MODEL = fasttext.load_model("cs336_data/classifiers/lid.176.ftz")
NSFW_MODEL = fasttext.load_model("cs336_data/classifiers/jigsaw_fasttext_bigrams_nsfw_final.bin")
TOXIC_MODEL = fasttext.load_model("cs336_data/classifiers/jigsaw_fasttext_bigrams_hatespeech_final.bin")
QUALITY_MODEL = fasttext.load_model("cs336_data/classifiers/paloma.bin")


def ensure_nltk_data():
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)


ensure_nltk_data()  # can't store this within folder structure, need to ensure it is downloaded if not found.


def extract_text(html_bytes):
    """Extracts text from bytestream"""
    try:
        text = html_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        # print("Decoding Error:", e)
        enc = detect_encoding(html_bytes)
        try:
            text = html_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            # print("Trying to replace and force utf-8")
            text = html_bytes.decode("utf-8", errors="replace")  # Last resort: force UTF-8 with replacement characters
    a = extract_plain_text(text)
    # print(f" {a =} ")
    return a


def identify_language(text):
    # Identifies language using a pretrained fasttext classifier.
    # TODO: Use .bin for bigger runs
    model = LANG_MODEL
    text = " ".join(
        [sentence for sentence in text.split("\n")]
    )  # THIS IS A HACK. Will give the classifier multiline text that it's not trained on.
    language, score = model.predict(text)

    return language[0].split("__label__")[1], float(score[0])


def classify_nsfw(text):
    # Identifies nsfw language using a pretrained fasttext classifier.
    # TODO: Use .bin for bigger runs
    model = NSFW_MODEL
    text = " ".join(
        [sentence for sentence in text.split("\n")]
    )  # THIS IS A HACK. Will give the classifier multiline text that it's not trained on.

    language, score = model.predict(text)
    return language[0].split("__label__")[1], float(score[0])


def classify_toxic_speech(text):
    # Identifies language using a pretrained fasttext classifier.
    # TODO: Use .bin for bigger runs
    model = TOXIC_MODEL
    text = " ".join(
        [sentence for sentence in text.split("\n")]
    )  # THIS IS A HACK. Will give the classifier multiline text that it's not trained on.

    """text_offensive ="You should kill yourself. I will buy you rope."
    language, score = model.predict(text_offensive)
    print(f"Classification and certainty for {text_offensive =}:\n {language = }, {score = }")"""

    language, score = model.predict(text)

    return language[0].split("__label__")[1], float(score[0])


def classify_quality(text, model_path=None):
    # Identifies quality (similarity to page linked from wikipedia) using a pretrained fasttext classifier.
    if not model_path:
        model = QUALITY_MODEL
    else:
        model = fasttext.load_model(model_path)
    text = " ".join(
        [sentence for sentence in text.split("\n")]
    )  # This is fine. Will give the classifier multiline text joined together. Same as what it's trained on.

    language, score = model.predict(text)

    return language[0].split("__label__")[1], float(score[0])


def gopher_quality_filter(text, include_alphabetic=True):
    words = text.split()  # nltk.word_tokenize(text)

    # Contain less than 50 or more than 100_000
    num_words = len(words)
    if num_words > 100_000 or num_words < 50:
        return False, "Num_words"

    # Mean word length below 3 or above 10
    word_length = 0
    for word in words:
        word_length += len(word)
    avg_word_length = word_length / num_words
    if avg_word_length > 10 or avg_word_length < 3:
        return False, "Word_length"

    # more than 30 % of lines ending with ellipsis
    line_text = text.split("\n")
    total_lines = len(line_text)
    ellipsis_lines = 0

    for line in line_text:
        if line[-3:] == "...":
            ellipsis_lines += 1
    if ellipsis_lines / total_lines > 0.3:
        return False, "Ellipses"

    # contain less than 80 % of words with at least one alphabetic character
    if include_alphabetic:
        num_alphabetic_words = 0
        for word in words:
            if any(c.isalpha() for c in word):
                num_alphabetic_words += 1

        if num_alphabetic_words / num_words < 0.8:
            return False, "Alphabetic"

    return True, ""


def c4_filter(text, blocked_content=False, remove_pdfs=False):
    if remove_pdfs:
        if text.startswith("%PDF"):
            return False, "PDF"

    if blocked_content:
        if "page not found" in text[:50].lower():
            return False, "Page not found"

        if "error" in text[:50].lower():
            return False, "Error"

        if "Cloudflare Ray ID" in text[-2000:]:
            return False, "Cloudfare"

    if len(text) > 600000 or len(text) < 200:
        return False, "Num_words"

    line_text = text.split("\n")
    trimmed = []
    for line in line_text:
        if not line or line[-1] not in ['"', ".", "!", "?"]:
            continue
        words = line.split()
        if len(words) < 5:
            continue
        trimmed.append(line)
    return True, "\n".join(trimmed)


def write_to_fasttext_training_data(
    filepath_out, label_out, filepath_in_warc="cs336_data/data/CC_example.warc.gz", num_records=-1
):
    def min_content_filter(record, min_bytes=200):
        return has_block_digest(record) and record.content_length > min_bytes

    # TODO: check that file exits

    stream = GZipStream(FileStream(filepath_in_warc, "rb"))
    i = 0
    reasons = {
        "Too large": 0,
        "Not english": 0,
        "Num_words": 0,
        "Word_length": 0,
        "Ellipses": 0,
        "Alphabetic": 0,
        "PDF": 0,
        "Page not found": 0,
        "Error": 0,
        "Cloudfare": 0,
        "nsfw": 0,
        "toxic": 0,
    }
    with open(file=filepath_out, mode="w", encoding="utf-8") as f:
        for record in ArchiveIterator(stream, func_filter=min_content_filter):
            if record.content_length > 5_000_000:
                continue
            bytes = record.reader.read()
            text = bytes.decode("utf-8")  # extract_text(bytes)
            # Going through the pipeline step by step
            if identify_language(text)[0] == "en":
                passing, text = c4_filter(text, True, True)
                if not passing:
                    reasons[text] += 1
                    continue
            else:
                print("Not English")
                continue

            passed_gopher, reason = gopher_quality_filter(text, include_alphabetic=True)
            if not passed_gopher:
                reasons[reason] += 1
                continue
            if not classify_nsfw(text)[0] == "non-nsfw":
                reasons["nsfw"] += 1
                continue
            if not classify_toxic_speech(text)[0] == "non-toxic":
                reasons["toxic"] += 1
                continue
            text = label_out + " " + " ".join(text.split("\n")) + "\n"
            f.write(text)
            # print(record.record_id)
            i += 1
            if i == num_records:  # if not specified , we will iterate over entire warc-file
                break
    print(reasons)


def create_training_data(
    filepath_in="cs336_data/data/CC_example.warc.gz", filepath_out="cs336_data/data/training_data.json", num_records=-1, warc=False
):
    def min_content_filter(record, min_bytes=1000):
        return has_block_digest(record) and record.content_length > min_bytes

    # TODO: check that file exits

    stream = GZipStream(FileStream(filepath_in, "rb"))
    i = 0
    filtered = {
        "Too large": 0,
        "Not english": 0,
        "Num_words": 0,
        "Word_length": 0,
        "Ellipses": 0,
        "Alphabetic": 0,
        "PDF": 0,
        "Page not found": 0,
        "Error": 0,
        "Cloudfare": 0,
        "nsfw": 0,
        "toxic": 0,
    }
    with open(file=filepath_out, mode="w", encoding="utf-8") as f:
        for record in ArchiveIterator(stream, func_filter=min_content_filter):
            if record.content_length > 5_000_000:
                filtered["Too large"] += 1
                continue

            bytes = record.reader.read()
            if warc:
                text = extract_text(bytes)
            else:  # wet files, can decode directly
                text = bytes.decode("utf-8")
            # Going through the pipeline step by step
            if identify_language(text)[0] == "en":
                passing, text = c4_filter(text, True, True)
                if not passing:
                    filtered[text] += 1
                    continue
            else:
                filtered["Not english"] += 1
                continue

            passed_gopher, reason = gopher_quality_filter(text, include_alphabetic=True)
            if not passed_gopher:
                filtered[reason] += 1
                continue
            if not classify_nsfw(text)[0] == "non-nsfw":
                filtered["nsfw"] += 1
                continue
            if not classify_toxic_speech(text)[0] == "non-toxic":
                filtered["toxic"] += 1
                continue
            # source, confidence = classify_quality(text)
            # if source == "cc":

            # text = label_out + str(confidence) + " " + " ".join(text.split("\n")) + "\n"
            f.write(json.dumps(text) + "\n")
            # print(record.record_id)
            i += 1
            if i == num_records:  # if not specified , we will iterate over entire warc-file
                break
    print(i, filtered)


def train_fasttext_quality_filter(
    training_file,
    validation_file,
    output_file,
):
    # model = fasttext.train_supervised(input=training_file, epoch=10, lr=1)  # 2 GB file
    model = fasttext.train_supervised(
        input=training_file,
        epoch=10,
        lr=1,
        dim=100,
        wordNgrams=2,
        bucket=2_000_000,
        minCount=5,
    )
    model.quantize(input=training_file, retrain=True)
    print(model.test(validation_file))
    model.save_model(output_file)


if __name__ == "__main__":
    """train_fasttext_quality_filter(
        "cs336_data/data/paloma_shuffled.txt", "cs336_data/data/paloma_val.txt", "cs336_data/classifiers/paloma.bin"
    )"""
    # write_to_fasttext_training_data("cs336_data/data/training_positive4.txt", "__label__wiki","cs336_data/data/sampled_positive_urls.warc.warc.gz")
    # write_to_fasttext_training_data("cs336_data/data/training_negative2.txt", "__label__cc", "cs336_data/data/CC_example.warc.gz")
    t0 = time.time()
    create_training_data(
        "cs336_data/data/CC-MAIN-20250417135010-20250417165010-00065.warc.wet.gz",
        "cs336_data/data/training2.json",
    )
    print(time.time() - t0)
    import sys

    sys.exit()
    random.seed(45)
    stream = GZipStream(FileStream("cs336_data/data/CC_example.warc.gz", "rb"))
    i = 0
    for record in ArchiveIterator(stream, func_filter=has_block_digest):
        # print(record.record_id)
        # print(record.content_length)
        if random.randint(0, 100) <= 5:
            # print(record.record_id)
            # print(record.content_length)
            bytes = record.reader.read()
            text = extract_text(bytes)
            if identify_language(text)[0] == "en":
                # print(text)
                print(i, gopher_quality_filter(text))  # classify_toxic_speech(text), classify_nsfw(text))
                i += 1
                if i == 5:
                    break
                    break
