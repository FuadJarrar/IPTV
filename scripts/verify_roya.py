#!/usr/bin/env python3
"""Read-only playback gate for the public Roya resolver; never edits playlists."""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_channels import probe_entry

URL = "https://roya-tv-on-demand.fuad-azzam-jarrar.chatgpt.site/roya.m3u8"


def safe_error(value):
    return re.sub(r"https?://\S+", "[URL]", value or "")[-3000:]


def main():
    entry = {
        "url": URL,
        "availability": "available",
        "user_agent": "Mozilla/5.0",
        "referer": "https://roya.tv/",
    }
    # Use the same probe budget and retry policy as the daily channel job.
    result = probe_entry(entry, timeout=15, retries=1)
    print(json.dumps({key: safe_error(str(result[key])) for key in
                      ("test_status", "detail", "latency_ms", "attempts")}))
    if result["test_status"] != "Working":
        raise SystemExit("Roya failed the normal working-channel gate")

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-rw_timeout", "15000000", "-user_agent", "Mozilla/5.0",
        "-headers", "Referer: https://roya.tv/\r\n", "-i", URL,
        "-map", "0:v:0", "-map", "0:a:0", "-t", "6",
        "-progress", "pipe:1", "-f", "null", "-",
    ]
    try:
        decoded = subprocess.run(command, capture_output=True, text=True,
                                 timeout=75, check=False)
    except subprocess.TimeoutExpired:
        raise SystemExit("Video/audio decoding timed out")
    fields = dict(re.findall(r"^(frame|out_time_us|progress)=(.*)$",
                             decoded.stdout, re.MULTILINE))
    frames = int(fields.get("frame", "0"))
    duration_us = int(fields.get("out_time_us", "0"))
    print(json.dumps({"decode_exit": decoded.returncode, "video_frames": frames,
                      "decoded_seconds": duration_us / 1000000,
                      "progress": fields.get("progress")}))
    if decoded.returncode or frames < 1 or duration_us < 5000000:
        print(safe_error(decoded.stderr))
        raise SystemExit("Roya did not decode at least five seconds of video/audio")
    print("PASS: public Roya endpoint passes the channel probe and audio/video decoding")


if __name__ == "__main__":
    main()
