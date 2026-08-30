#!/usr/bin/env python3
"""Read-only test of a fresh direct Roya stream; never edits playlists."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roya import verified_roya, print_result


if __name__ == "__main__":
    result = verified_roya()
    print_result(result)
    if result["test_status"] != "Working":
        raise SystemExit("Direct Roya audio/video verification failed")
    print("PASS: direct Roya playback verified, with at least 30 minutes remaining")
