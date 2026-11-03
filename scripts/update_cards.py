"""Refresh public profile cards without publishing upstream error images."""

import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ENDPOINT = "https://github-stats-extended.vercel.app"
SVG = "{http://www.w3.org/2000/svg}"
MAX_BYTES = 256 * 1024
CARDS = {
    "stats.svg": (
        "/api",
        {"show_icons": "true", "hide_rank": "true", "include_all_commits": "false"},
        {"commits", "prs", "issues"},
    ),
    "top-langs.svg": (
        "/api/top-langs",
        {"layout": "compact", "langs_count": "6"},
        {"lang-name"},
    ),
}


def validate_svg(data, expected_ids):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Empty or oversized card")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unexpected XML declarations")
    root = ET.fromstring(data)
    if root.tag != SVG + "svg":
        raise ValueError("Response is not an SVG")
    ids = {element.get("data-testid") for element in root.iter()}
    if not expected_ids.issubset(ids):
        raise ValueError("Expected card data is missing")
    text = " ".join(root.itertext()).lower()
    if any(message in text for message in (
        "something went wrong", "resource not accessible", "rate limit exceeded",
    )):
        raise ValueError("Upstream returned an error card")
    for element in root.iter():
        if element.tag in {SVG + "script", SVG + "foreignObject"}:
            raise ValueError("Unexpected active SVG content")
        for name, value in element.attrib.items():
            if name.lower().startswith("on") or (
                name.rsplit("}", 1)[-1] == "href" and not value.startswith("#")
            ):
                raise ValueError("Unexpected external or active SVG content")


def fetch_svg(url, expected_ids):
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "alyldas-profile-cards"})
            with urlopen(request, timeout=20) as response:
                data = response.read(MAX_BYTES + 1)
            validate_svg(data, expected_ids)
            return data
        except (HTTPError, URLError, TimeoutError, ValueError, ET.ParseError):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def update_cards(username, directory):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", username):
        raise ValueError("Invalid GitHub username")
    common = {
        "username": username, "hide_border": "true", "bg_color": "111820",
        "title_color": "C6F36B", "icon_color": "C6F36B",
        "text_color": "B8C6D2", "border_radius": "12",
    }
    # Validate the entire batch before touching the last good snapshots.
    snapshots = {}
    for filename, (path, options, expected_ids) in CARDS.items():
        url = ENDPOINT + path + "?" + urlencode(common | options)
        snapshots[filename] = fetch_svg(url, expected_ids)
    directory.mkdir(parents=True, exist_ok=True)
    for filename, data in snapshots.items():
        temporary = directory / (filename + ".next")
        temporary.write_bytes(data)
        temporary.replace(directory / filename)
    print("Updated public activity and language cards")


if __name__ == "__main__":
    update_cards(
        os.environ.get("GITHUB_REPOSITORY_OWNER", "alyldas"),
        Path(__file__).resolve().parents[1] / "profile",
    )
