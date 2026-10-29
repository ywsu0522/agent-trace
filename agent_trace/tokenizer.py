"""Split lowercase text into ASCII alphanumeric tokens."""

import re


def tokenize(text):
    return re.findall(r'[a-z0-9]+', text.lower())
