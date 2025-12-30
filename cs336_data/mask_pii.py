
import regex as re


def mask_emails(text):
    email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    split_text = re.split(email_regex, text)
    num_masks = len(split_text) - 1
    return ("|||EMAIL_ADDRESS|||".join(split_text), num_masks)


def mask_phone_numbers(text):
    phone_regex = re.compile(r"(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}")
    split_text = re.split(phone_regex, text)
    num_masks = len(split_text) - 1
    return ("|||PHONE_NUMBER|||".join(split_text), num_masks)


def mask_ips(text):
    ip_regex = re.compile(r"[0-9]+.[0-9]+.[0-9]+.[0-9]+")
    split_text = re.split(ip_regex, text)
    num_masks = len(split_text) - 1
    return ("|||IP_ADDRESS|||".join(split_text), num_masks)

