#!/usr/bin/env python3
import argparse
import csv
import re
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
DEFAULT_UA = "Mozilla/5.0"


def parse_playlist(path):
    entries = []
    current = None
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#EXTINF:"):
            if current:
                entries.append(current)
            attrs = dict(ATTR_RE.findall(line))
            current = {
                "extinf": line,
                "name": line.split(",", 1)[1].strip() if "," in line else line,
                "tvg_id": attrs.get("tvg-id", ""),
                "country": attrs.get("group-title", "Other"),
                "availability": attrs.get("availability", "available"),
                "referer": attrs.get("http-referrer", ""),
                "user_agent": attrs.get("http-user-agent", DEFAULT_UA),
                "url": "",
                "lines": [line],
            }
        elif current and line.startswith("#EXTVLCOPT:http-referrer="):
            current["lines"].append(line)
            current["referer"] = line.split("=", 1)[1].strip()
        elif current and line.startswith("#EXTVLCOPT:http-user-agent="):
            current["lines"].append(line)
            current["user_agent"] = line.split("=", 1)[1].strip()
        elif current and line and not line.startswith("#"):
            current["lines"].append(line)
            current["url"] = line.strip()
        elif current and line:
            current["lines"].append(line)
    if current:
        entries.append(current)
    return entries


def compact_error(stderr):
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if not lines:
        return "No diagnostic returned"
    message = lines[-1]
    return message[:300]


def classify_failure(stderr, timed_out=False):
    text = stderr.casefold()
    if timed_out:
        return "Timeout"
    if "403 forbidden" in text or "server returned 403" in text:
        return "Restricted (403)"
    if "401 unauthorized" in text or "server returned 401" in text:
        return "Unauthorized (401)"
    if "451" in text:
        return "Restricted (451)"
    if "404 not found" in text or "server returned 404" in text:
        return "Not found (404)"
    if "410 gone" in text or "server returned 410" in text:
        return "Gone (410)"
    if "name or service not known" in text or "temporary failure in name resolution" in text:
        return "DNS failure"
    if "connection refused" in text:
        return "Connection refused"
    if "certificate" in text or "tls" in text or "ssl" in text:
        return "TLS failure"
    if "invalid data found" in text:
        return "Invalid stream"
    return "Failed"


def token_expired(url):
    match = re.search(r"exp=(\d+)", url)
    return bool(match and int(match.group(1)) <= int(time.time()))


def probe_once(entry, timeout):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-rw_timeout",
        str(timeout * 1_000_000),
        "-user_agent",
        entry["user_agent"] or DEFAULT_UA,
    ]
    if entry["referer"]:
        command.extend(["-headers", f'Referer: {entry["referer"]}\r\n'])
    command.extend(
        [
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            entry["url"],
        ]
    )
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = round((time.monotonic() - started) * 1000)
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        return "Timeout", compact_error(stderr), elapsed

    elapsed = round((time.monotonic() - started) * 1000)
    media_types = {line.strip() for line in completed.stdout.splitlines() if line.strip()}
    if completed.returncode == 0 and media_types.intersection({"audio", "video"}):
        detail = "+".join(sorted(media_types.intersection({"audio", "video"})))
        return "Working", detail, elapsed
    status = classify_failure(completed.stderr)
    return status, compact_error(completed.stderr), elapsed


def probe_entry(entry, timeout, retries):
    result = dict(entry)
    availability = entry["availability"]
    if availability == "blocked":
        result.update(test_status="Not tested — blocklisted", detail="IPTV-org blocklist", latency_ms="", attempts=0)
        return result
    if availability != "available" or "example.invalid" in entry["url"]:
        result.update(test_status="Not tested — no public stream", detail="No real stream URL", latency_ms="", attempts=0)
        return result
    if not entry["url"]:
        result.update(test_status="Missing URL", detail="Playlist entry has no URL", latency_ms="", attempts=0)
        return result
    if token_expired(entry["url"]):
        result.update(test_status="Expired token", detail="Signed URL expired before testing", latency_ms="", attempts=0)
        return result

    last = ("Failed", "No result", "")
    for attempt in range(1, retries + 2):
        last = probe_once(entry, timeout)
        if last[0] == "Working":
            result.update(test_status=last[0], detail=last[1], latency_ms=last[2], attempts=attempt)
            return result
        if attempt <= retries:
            time.sleep(1)
    result.update(test_status=last[0], detail=last[1], latency_ms=last[2], attempts=retries + 1)
    return result


def write_working_playlist(path, rows):
    working = [
        row
        for row in rows
        if row["test_status"] == "Working"
        and row["url"]
        and "example.invalid" not in row["url"].casefold()
    ]
    output = ["#EXTM3U"]
    for row in working:
        output.extend(row["lines"])
    Path(path).write_text("\n".join(output) + "\n", encoding="utf-8")
    return len(working)


def write_csv(path, rows, checked_at):
    fields = [
        "Checked At UTC",
        "Country",
        "Channel Name",
        "tvg-id",
        "Availability",
        "Test Result",
        "Detail",
        "Latency ms",
        "Attempts",
        "Stream Host",
        "Stream URL",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "Checked At UTC": checked_at,
                    "Country": row["country"],
                    "Channel Name": row["name"],
                    "tvg-id": row["tvg_id"],
                    "Availability": row["availability"],
                    "Test Result": row["test_status"],
                    "Detail": row["detail"],
                    "Latency ms": row["latency_ms"],
                    "Attempts": row["attempts"],
                    "Stream Host": urlparse(row["url"]).hostname or "",
                    "Stream URL": row["url"],
                }
            )


def write_markdown(path, rows, checked_at, csv_name):
    counts = Counter(row["test_status"] for row in rows)
    tested = [row for row in rows if row["availability"] == "available"]
    working = counts.get("Working", 0)
    failed = len(tested) - working

    country_stats = defaultdict(lambda: Counter(total=0, tested=0, working=0, failed=0, unavailable=0, blocked=0))
    for row in rows:
        stats = country_stats[row["country"]]
        stats["total"] += 1
        if row["availability"] == "blocked":
            stats["blocked"] += 1
        elif row["availability"] != "available":
            stats["unavailable"] += 1
        else:
            stats["tested"] += 1
            if row["test_status"] == "Working":
                stats["working"] += 1
            else:
                stats["failed"] += 1

    lines = [
        "# Arab Countries Channel Status",
        "",
        f"Last automated test: **{checked_at}**",
        "",
        "> Tests run from a GitHub-hosted runner. Geo-restricted streams may work in Jordan even when they fail here.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total playlist entries | {len(rows)} |",
        f"| Real streams tested | {len(tested)} |",
        f"| Working | {working} |",
        f"| Failed or restricted | {failed} |",
        f"| No public stream | {sum(1 for row in rows if row['availability'] == 'unavailable')} |",
        f"| Blocklisted | {sum(1 for row in rows if row['availability'] == 'blocked')} |",
        "",
        f"[Download detailed CSV]({csv_name})",
        "",
        "## By country",
        "",
        "| Country | Total | Tested | Working | Failed | No stream | Blocked |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for country in sorted(country_stats, key=str.casefold):
        stats = country_stats[country]
        lines.append(
            f"| {country} | {stats['total']} | {stats['tested']} | {stats['working']} | "
            f"{stats['failed']} | {stats['unavailable']} | {stats['blocked']} |"
        )

    lines.extend(["", "## Test results", ""])
    for status, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- **{status}:** {count}")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Test streams in an M3U playlist with ffprobe")
    parser.add_argument("--playlist", default="arab-countries.m3u")
    parser.add_argument("--csv", default="channel-status.csv")
    parser.add_argument("--markdown", default="channel-status.md")
    parser.add_argument(
        "--working-playlist",
        help="Write only streams that pass the current test to this M3U file",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--retries", type=int, default=1)
    args = parser.parse_args()

    entries = parse_playlist(args.playlist)
    results = [None] * len(entries)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(probe_entry, entry, args.timeout, args.retries): index
            for index, entry in enumerate(entries)
        }
        completed = 0
        for future in as_completed(futures):
            index = futures[future]
            results[index] = future.result()
            completed += 1
            if completed % 25 == 0 or completed == len(entries):
                print(f"Completed {completed}/{len(entries)}")

    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    write_csv(args.csv, results, checked_at)
    write_markdown(args.markdown, results, checked_at, Path(args.csv).name)
    if args.working_playlist:
        written = write_working_playlist(args.working_playlist, results)
        print(f"Wrote {args.working_playlist} with {written} verified working channels")
    counts = Counter(row["test_status"] for row in results)
    print("Results:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
