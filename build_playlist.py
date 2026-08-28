#!/usr/bin/env python3
import csv
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE_M3U = "https://iptv-org.github.io/iptv/index.country.m3u"
CHANNELS_CSV = "https://raw.githubusercontent.com/iptv-org/database/master/data/channels.csv"
BLOCKLIST_CSV = "https://raw.githubusercontent.com/iptv-org/database/master/data/blocklist.csv"
ROYA_API = "https://ticket.roya-tv.com/api/v5/fastchannel/1"
ROYA_LOGO = "https://en.roya.tv/images/logo.png"
OUTPUT = Path("index.country.m3u")
ARAB_OUTPUT = Path("arab-countries.m3u")
PLACEHOLDER_BASE = "https://example.invalid/iptv-no-stream"

UA = "Mozilla/5.0"

ARAB_COUNTRIES = {
    "DZ": "Algeria",
    "BH": "Bahrain",
    "KM": "Comoros",
    "DJ": "Djibouti",
    "EG": "Egypt",
    "IQ": "Iraq",
    "JO": "Jordan",
    "KW": "Kuwait",
    "LB": "Lebanon",
    "LY": "Libya",
    "MR": "Mauritania",
    "MA": "Morocco",
    "OM": "Oman",
    "PS": "Palestine",
    "QA": "Qatar",
    "SA": "Saudi Arabia",
    "SO": "Somalia",
    "SD": "Sudan",
    "SY": "Syria",
    "TN": "Tunisia",
    "AE": "United Arab Emirates",
    "YE": "Yemen",
}

group_re = re.compile(r'group-title="([^"]*)"')
tvg_id_re = re.compile(r'tvg-id="([^"]*)"')


def fetch_text(url, referer=None):
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def find_secured_url(obj):
    if isinstance(obj, dict):
        value = obj.get("secured_url")
        if isinstance(value, str) and value.startswith("http"):
            return value
        for child in obj.values():
            found = find_secured_url(child)
            if found:
                return found
    elif isinstance(obj, list):
        for child in obj:
            found = find_secured_url(child)
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


def entry_key(entry):
    extinf = entry[0]
    match = group_re.search(extinf)
    group = (match.group(1) if match else "Other").strip()
    name = extinf.split(",", 1)[1].strip() if "," in extinf else extinf
    return group.casefold(), name.casefold()


def channel_id(entry):
    match = tvg_id_re.search(entry[0])
    return match.group(1).split("@", 1)[0] if match else ""


def stream_url(entry):
    for line in reversed(entry[1:]):
        if line and not line.startswith("#"):
            return line
    return ""


def stream_score(entry):
    name = entry[0].split(",", 1)[-1]
    resolution = max((int(value) for value in re.findall(r"(\d{3,4})[pi]", name)), default=0)
    url = stream_url(entry)
    return (
        "[Not 24/7]" not in name,
        resolution,
        url.startswith("https://"),
        name.casefold(),
    )


def xml_attr(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def set_extinf_attr(extinf, name, value):
    pattern = re.compile(rf'{re.escape(name)}="[^"]*"')
    replacement = f'{name}="{xml_attr(value)}"'
    if pattern.search(extinf):
        return pattern.sub(replacement, extinf, count=1)
    comma = extinf.find(",")
    if comma == -1:
        return extinf + " " + replacement
    return extinf[:comma] + " " + replacement + extinf[comma:]


def set_display_name(extinf, name):
    return extinf.split(",", 1)[0] + "," + name


def unavailable_entry(row, country, reason=None):
    status = "blocked" if reason else "unavailable"
    suffix = f" [Blocked: {reason}]" if reason else " [Unavailable]"
    extinf = (
        '#EXTINF:-1 '
        f'tvg-id="{xml_attr(row["id"])}" '
        f'tvg-name="{xml_attr(row["name"])}" '
        f'group-title="{xml_attr(country)}" '
        f'availability="{status}",'
        f'{row["name"]}{suffix}'
    )
    placeholder = PLACEHOLDER_BASE + "/" + urllib.parse.quote(row["id"], safe="")
    return ["".join(extinf), placeholder]


def build_arab_playlist(header, source_entries, roya_entry, channels_text, blocklist_text):
    by_channel = {}
    for entry in source_entries:
        cid = channel_id(entry)
        if cid and re.match(r"^[a-z][a-z0-9+.-]*://", stream_url(entry), re.I):
            by_channel.setdefault(cid, []).append(entry)

    blocked = {
        row["channel"]: row.get("reason", "blocked")
        for row in csv.DictReader(io.StringIO(blocklist_text))
    }
    catalog = [
        row
        for row in csv.DictReader(io.StringIO(channels_text))
        if row.get("country") in ARAB_COUNTRIES and not row.get("closed")
    ]
    catalog.sort(
        key=lambda row: (
            ARAB_COUNTRIES[row["country"]].casefold(),
            row["name"].casefold(),
            row["id"].casefold(),
        )
    )

    result = []
    counts = {"available": 0, "unavailable": 0, "blocked": 0}
    for row in catalog:
        country = ARAB_COUNTRIES[row["country"]]
        if row["id"] == "RoyaTV.jo":
            chosen = list(roya_entry)
        elif row["id"] in by_channel:
            chosen = list(max(by_channel[row["id"]], key=stream_score))
        else:
            reason = blocked.get(row["id"])
            result.append(unavailable_entry(row, country, reason))
            counts["blocked" if reason else "unavailable"] += 1
            continue

        extinf = chosen[0]
        extinf = set_extinf_attr(extinf, "group-title", country)
        extinf = set_extinf_attr(extinf, "tvg-name", row["name"])
        extinf = set_extinf_attr(extinf, "availability", "available")
        if row["id"] == "RoyaTV.jo":
            extinf = set_display_name(extinf, "Roya TV (Roya Page)")
        chosen[0] = extinf
        result.append(chosen)
        counts["available"] += 1

    out = [header]
    for entry in result:
        out.extend(entry)
    return "\n".join(out) + "\n", counts


def main():
    source = fetch_text(SOURCE_M3U)
    header, entries = parse_entries(source)

    entries = [entry for entry in entries if "Roya TV (Roya Page)" not in entry[0]]
    roya_json = json.loads(fetch_text(ROYA_API, referer="https://roya.tv/"))
    roya_url = find_secured_url(roya_json)
    if not roya_url:
        raise RuntimeError("Roya API did not return a secured_url")

    roya_entry = [
        f'#EXTINF:-1 tvg-id="RoyaTV.jo" tvg-name="Roya TV" tvg-logo="{ROYA_LOGO}" group-title="Jordan" availability="available",Roya TV (Roya Page)',
        '#EXTVLCOPT:http-referrer=https://roya.tv/',
        '#EXTVLCOPT:http-user-agent=Mozilla/5.0',
        roya_url,
    ]

    main_entries = entries + [roya_entry]
    main_entries.sort(key=entry_key)
    main_out = [header]
    for entry in main_entries:
        main_out.extend(entry)
    OUTPUT.write_text("\n".join(main_out) + "\n", encoding="utf-8")

    arab_text, counts = build_arab_playlist(
        header,
        entries,
        roya_entry,
        fetch_text(CHANNELS_CSV),
        fetch_text(BLOCKLIST_CSV),
    )
    ARAB_OUTPUT.write_text(arab_text, encoding="utf-8")

    print(f"Wrote {OUTPUT} with {len(main_entries)} channels")
    print(
        f"Wrote {ARAB_OUTPUT} with {sum(counts.values())} channels "
        f"({counts['available']} available, {counts['unavailable']} unavailable, "
        f"{counts['blocked']} blocked)"
    )


if __name__ == "__main__":
    main()
