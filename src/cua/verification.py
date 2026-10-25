"""Independent URL/state checks supplement fallible visual inference."""
from urllib.parse import parse_qs, urlsplit


def search_url_matches(url, task):
    if not url.startswith(("https://", "http://")):
        url = "https://" + url
    actual, expected = urlsplit(url), urlsplit(task.url)
    return (actual.scheme == "https" and actual.hostname == expected.hostname
            and actual.path.rstrip("/") == expected.path.rstrip("/")
            and parse_qs(actual.query).get("q") == [task.query])


def verify_step(stage, browser, task):
    if stage == 0:
        return browser.address_focused()
    if stage == 1:
        return browser.address_value() == task.url
    return search_url_matches(browser.address_value(), task)
