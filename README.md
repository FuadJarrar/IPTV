# IPTV

Automated IPTV playlists for OTT Navigator.

## Playlists

- [All countries](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/index.country.m3u)
- [Arab countries](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/arab-countries.m3u)
- [Latest Arab channel test summary](channel-status.md)
- [Detailed Arab channel test results](channel-status.csv)

The public `arab-countries.m3u` playlist contains only channels that passed
the latest automated stream test. OTT Navigator therefore receives working
channels only.

Every day at 02:20 UTC, the workflow rebuilds a private candidate catalog from
all active registered channels in the 22 Arab League countries, including
channels that previously failed or had no stream. It tests every real stream
with ffprobe, adds channels that pass, and removes channels that fail. The
candidate catalog is temporary and is not published in the repository.

Roya TV uses the stream obtained directly from the Roya TV page API. Its
short-lived signed URL is refreshed every 30 minutes, at minutes 7 and 37 UTC,
without re-adding Roya if it did not pass the latest full test.

Tests run from a GitHub-hosted runner, so geo-restricted results may differ
from Jordan. The scheduled workflows have no end date.
