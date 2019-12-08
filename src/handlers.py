OK_RESPONSE = {"statusCode": 200}
FORDIDDEN_RESPONSE = {"statusCode": 403}


def extract_and_sort_hashtags(text, default):
    tags = sorted(set(part[1:] for part in text.split() if part.startswith("#")))

    if len(tags) == 0:
        tags = default

    return " ".join(tags)
