from pathlib import Path

import random
import fasttext
import regex as re
from fastwarc.stream_io import *
from fastwarc.warc import ArchiveIterator, WarcRecordType, has_block_digest
from resiliparse.extract.html2text import extract_plain_text
from resiliparse.parse.encoding import detect_encoding
import nltk

def ensure_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', quiet=True)

ensure_nltk_data()

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
            text = html_bytes.decode("utf-8", errors="replace") # Last resort: force UTF-8 with replacement characters
    a = extract_plain_text(text)
    # print(f" {a =} ")
    return a


def identify_language(text):
    # Identifies language using a pretrained fasttext classifier.
    # TODO: Use .bin for bigger runs
    pretrained_classifier = "cs336_data/classifiers/lid.176.ftz"
    model = fasttext.load_model(pretrained_classifier)
    text = " ".join(
        [sentence for sentence in text.split("\n")]
    )  # THIS IS A HACK. Will give the classifier multiline text that it's not trained on.
    language, score = model.predict(text)

    return language[0].split("__label__")[1], float(score[0])

def classify_nsfw(text):
    # Identifies nsfw language using a pretrained fasttext classifier.
    # TODO: Use .bin for bigger runs
    pretrained_classifier = "cs336_data/classifiers/jigsaw_fasttext_bigrams_nsfw_final.bin"
    model = fasttext.load_model(pretrained_classifier)
    text = " ".join(
        [sentence for sentence in text.split("\n")]
    )  # THIS IS A HACK. Will give the classifier multiline text that it's not trained on.
    
    language, score = model.predict(text)
    return language[0].split("__label__")[1], float(score[0])


def classify_toxic_speech(text):
    # Identifies language using a pretrained fasttext classifier.
    # TODO: Use .bin for bigger runs
    pretrained_classifier = "cs336_data/classifiers/jigsaw_fasttext_bigrams_hatespeech_final.bin"
    model = fasttext.load_model(pretrained_classifier)
    text = " ".join(
        [sentence for sentence in text.split("\n")]
    )  # THIS IS A HACK. Will give the classifier multiline text that it's not trained on.

    """text_offensive ="You should kill yourself. I will buy you rope."
    language, score = model.predict(text_offensive)
    print(f"Classification and certainty for {text_offensive =}:\n {language = }, {score = }")"""

    language, score = model.predict(text)

    return language[0].split("__label__")[1], float(score[0])

def gopher_quality_filter(text):
    words = nltk.word_tokenize(text)

    # Contain less than 50 or more than 100_000
    num_words = len(words)
    if num_words > 100_000 or num_words < 50:
        return False
    
    # Mean word length below 3 or above 10
    word_length = 0
    for word in words:
        word_length += len(word)
    avg_word_length = word_length / num_words
    if avg_word_length > 10 or avg_word_length < 3:
        return False
    
    # more than 30 % of lines ending with ellipsis
    line_text = text.split("\n")
    total_lines = len(line_text)
    ellipsis_lines = 0

    for line in line_text:
        if line[-3:] == "...":
            ellipsis_lines += 1
    if ellipsis_lines/total_lines > 0.3:
        return False

    # contain less than 80 % of words with at least one alphabetic character
    num_alphabetic_words = 0
    for word in words:
        if word.isalpha() or (word.isalnum() and not word.isdigit()):
            num_alphabetic_words += 1
    
    if num_alphabetic_words / num_words < 0.8:
        return False

    return True


if __name__ == "__main__":
    random.seed(45)
    stream = GZipStream(FileStream("cs336_data/data/CC_example.warc.gz", "rb"))
    i = 0
    for record in ArchiveIterator(stream, func_filter=has_block_digest):
        # print(record.record_id)
        # print(record.content_length)
        if random.randint(0,100) <= 5:
            #print(record.record_id)
            # print(record.content_length)
            bytes = record.reader.read()
            text = extract_text(bytes)
            if identify_language(text)[0] == "en":
                #print(text)
                print(i, gopher_quality_filter(text))#classify_toxic_speech(text), classify_nsfw(text))
                i += 1
                if i == 20:
                    break
