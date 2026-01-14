import json
with open('data/paloma/paloma_c4_100_domains_val.jsonl') as f, open("paloma.txt", "w") as g:
        docs = [json.loads(line) for line in f]
        for item in docs:
            g.write("__label__paloma " + " ".join(item["text"].split("\n")) + "\n")
            