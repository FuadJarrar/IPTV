"""Resolve and verify Roya's direct stream without publishing another playlist."""
import json
import http.client
import re
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROYA_API = "https://ticket.roya-tv.com/api/v5/fastchannel/1"
ROYA_LOGO = "https://en.roya.tv/images/logo.png"
MIN_VALIDITY = 30 * 60


def safe_error(value):
    return re.sub(r"https?://\S+", "[URL]", str(value))[-1000:]


def expires_at(url):
    match = re.search(r"(?:^|[=~?&/])exp=(\d+)", urllib.parse.unquote(url))
    return int(match.group(1)) if match else 0


def validate_url(url, minimum=MIN_VALIDITY):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "live.kwikmotion.com"
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or not parsed.path.startswith("/royatvlive/royatv.smil/")):
        raise ValueError("Unexpected Roya stream address")
    if expires_at(url) - time.time() < minimum:
        raise ValueError("Roya link has insufficient validity remaining")
    return url


def find_secured_url(data):
    if isinstance(data, dict):
        if isinstance(data.get("secured_url"), str):
            return data["secured_url"]
        children = data.values()
    elif isinstance(data, list):
        children = data
    else:
        return None
    return next((found for item in children if (found := find_secured_url(item))), None)


def row_for_url(url):
    extinf = (f'#EXTINF:-1 tvg-id="RoyaTV.jo" tvg-name="Roya TV" '
              f'tvg-logo="{ROYA_LOGO}" group-title="Jordan" '
              'availability="available",Roya TV (Roya Page)')
    return dict(extinf=extinf, name="Roya TV (Roya Page)", tvg_id="RoyaTV.jo",
                country="Jordan", availability="available", referer="https://roya.tv/",
                user_agent="Mozilla/5.0", url=url,
                lines=[extinf, '#EXTVLCOPT:http-referrer=https://roya.tv/',
                       '#EXTVLCOPT:http-user-agent=Mozilla/5.0', url])


def fresh_roya():
    request = urllib.request.Request(ROYA_API, headers={
        "Referer": "https://roya.tv/", "User-Agent": "Mozilla/5.0",
        "Accept": "application/json", "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read(1048577)
    if len(payload) > 1048576:
        raise ValueError("Roya API response too large")
    url = find_secured_url(json.loads(payload))
    if not url:
        raise ValueError("Roya API returned no stream")
    return row_for_url(validate_url(url))


def verified_roya(probe=None):
    # Import only when called, keeping the shared provider module independent
    # of the daily tester's initialization and allowing isolated unit tests.
    if probe is None:
        from test_channels import probe_entry
        probe = probe_entry
    row = row_for_url("")
    try:
        row = fresh_roya()
        result = probe(row, timeout=15, retries=1)
        if result["test_status"] != "Working":
            result["detail"] = safe_error(result["detail"])
            return result
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-rw_timeout", "15000000", "-user_agent", row["user_agent"],
            "-headers", "Referer: https://roya.tv/\r\n", "-i", row["url"],
            "-map", "0:v:0", "-map", "0:a:0", "-t", "6",
            "-progress", "pipe:1", "-f", "null", "-",
        ]
        decoded = subprocess.run(command, capture_output=True, text=True,
                                 timeout=75, check=False)
        fields = dict(re.findall(r"^(frame|out_time_us|progress)=(.*)$",
                                 decoded.stdout, re.MULTILINE))
        frames = int(fields.get("frame", "0"))
        seconds = int(fields.get("out_time_us", "0")) / 1000000
        if decoded.returncode or frames < 1 or seconds < 5:
            raise ValueError("Audio/video decode failed: " + safe_error(decoded.stderr))
        # Recheck AFTER decoding. Never publish a link about to expire.
        validate_url(row["url"])
        result.update(detail=f"audio+video; {frames} frames / {seconds:.2f}s decoded",
                      expires_utc=datetime.fromtimestamp(expires_at(row["url"]), timezone.utc).isoformat())
        return result
    except (OSError, ValueError, TypeError, http.client.HTTPException, subprocess.TimeoutExpired) as error:
        row.update(test_status="Roya verification failed", detail=safe_error(error),
                   latency_ms="", attempts=1)
        return row


def print_result(result):
    print(json.dumps({key: result[key] for key in
                      ("test_status", "detail", "attempts", "expires_utc")
                      if key in result}))
