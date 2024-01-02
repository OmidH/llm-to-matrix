import re
from urllib.parse import urlparse

def prepare_msg(tmplt, msg):
    if not tmplt.strip():
        return msg
    new_str = tmplt.replace("{message}", msg)
    return new_str


def validate_url(url):
    if not urlparse(url).scheme:
        url = 'https://' + url

    parsed_url = urlparse(url)

    # ChatGPT generated
    regex = re.compile(
        r'^(?:http)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, url) is not None and bool(parsed_url.netloc), url
