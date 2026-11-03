#!/usr/bin/env python3
"""Save Crossref metadata checks; metadata does not verify research claims or indexing."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def lookup(item):
    key, title, doi = item
    record = {
        "key": key,
        "manuscript_title": title,
        "doi": doi,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        url = "https://api.crossref.org/works/" + quote(doi, safe="")
        request = Request(url, headers={"User-Agent": "CC-CEP-research-metadata-audit/0.1"})
        with urlopen(request, timeout=30) as response:
            data = json.load(response)["message"]
        record.update(
            status="metadata_found",
            title=data.get("title"),
            publisher=data.get("publisher"),
            year=data.get("published"),
            url=data.get("URL"),
            type=data.get("type"),
        )
    except Exception as exc:
        record.update(status="unverified", error=str(exc))
    return record


if __name__ == "__main__":
    source = (ROOT / "cas-refs.bib").read_text(encoding="utf-8-sig")
    items = []
    for key, body in re.findall(r"@\w+\{([^,]+),(.*?)(?=\n@|\Z)", source, re.S):
        doi = re.search(r"doi\s*=\s*\{([^}]+)\}", body)
        title = re.search(r"title\s*=\s*\{(.*?)\},\s*\n", body, re.S)
        if doi:
            items.append((key, title.group(1) if title else "", doi.group(1)))
    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(lookup, items))
    (ROOT / "docs" / "reference-audit.json").write_text(json.dumps(records, indent=2) + "\n")
    print(
        f"{sum(r['status'] == 'metadata_found' for r in records)}/{len(records)} metadata records found"
    )
