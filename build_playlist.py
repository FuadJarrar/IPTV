#!/usr/bin/env python3
import json
import re
import urllib.request
from pathlib import Path

SOURCE_M3U = "https://iptv-org.github.io/iptv/index.country.m3u"
ROYA_API = "https://ticket.roya-tv.com/api/v5/fastchannel/1"
OUTPUT = Path("index.country.m3u")

UA = "Mozilla/5.0"

def fetch_text(url, referer=None):
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def find_secured_url(obj):
    if isinstance(obj, dict):
        v = obj.get("secured_url")
        if isinstance(v, str) and v.startswith("http"):
            return v
        for value in obj.values():
            found = find_secured_url(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_secured_url(value)
            if found:
                return found
    return None

def parse_entries(text):
    lines = text.splitlines()
    header = lines[0] if lines and lines[0].startswith("#EXTM3U") else "#EXTM3U"
    entries, current = [], []
    for line in lines[1:]:
        if line.startswith("#EXTINF:"):
            if current:
                entries.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        entries.append(current)
    return header, entries

group_re = re.compile(r'group-title="([^"]*)"')

def entry_key(entry):
    extinf = entry[0]
    m = group_re.search(extinf)
    group = (m.group(1) if m else "Other").strip()
    name = extinf.split(",", 1)[1].strip() if "," in extinf else extinf
    return group.casefold(), name.casefold()

source = fetch_text(SOURCE_M3U)
header, entries = parse_entries(source)

# Prevent duplicate custom Roya entry if the upstream list changes later.
entries = [e for e in entries if "Roya TV (Roya Page)" not in e[0]]

roya_json = json.loads(fetch_text(ROYA_API, referer="https://roya.tv/"))
roya_url = find_secured_url(roya_json)
if not roya_url:
    raise RuntimeError("Roya API did not return a secured_url")

roya_entry = [
    '#EXTINF:-1 tvg-id="RoyaTV.jo" tvg-name="Roya TV" group-title="Jordan",Roya TV (Roya Page)',
    '#EXTVLCOPT:http-referrer=https://roya.tv/',
    '#EXTVLCOPT:http-user-agent=Mozilla/5.0',
    roya_url,
]
entries.append(roya_entry)
entries.sort(key=entry_key)

out = [header]
for entry in entries:
    out.extend(entry)

OUTPUT.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Wrote {OUTPUT} with {len(entries)} channels")
