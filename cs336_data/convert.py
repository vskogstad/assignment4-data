from fastwarc.warc import ArchiveIterator, WarcRecordType, has_block_digest
from resiliparse.parse.encoding import detect_encoding
from resiliparse.extract.html2text import extract_plain_text
#for later:


from fastwarc.stream_io import *




from pathlib import Path

def extract_text(html_bytes):
    """Extracts text from bytestream"""
    try:
        text = html_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        print("Decoding Error:", e)
        enc = detect_encoding(html_bytes)
        print(enc)
        text = html_bytes.decode(enc)
    a =extract_plain_text(text)
    print(f" {a =} ")
    return a


if __name__ == "__main__":
    stream = GZipStream(FileStream("/home/vegard/projects/stanford/assignment4-data/cs336_data/data/CC_example.warc.gz", "rb"))
    max = 3
    for record in ArchiveIterator(stream, func_filter=has_block_digest):
        print(record.record_id)
        print(record.content_length)
        bytes = record.reader.read()
        extract_text(bytes)
        max -= 1
        if max == 0:
            break
