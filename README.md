# IPTV

Automated IPTV playlists for OTT Navigator.

## Playlists

- [All countries](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/index.country.m3u)
- [Arab countries](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/arab-countries.m3u)
- [Latest Arab channel test summary](channel-status.md)
- [Detailed Arab channel test results](channel-status.csv)

The public `arab-countries.m3u` playlist contains only channels that passed
the latest automated stream test. This is a point-in-time check, not a
guarantee that a broadcaster remains available between checks.

The daily workflow is scheduled for 02:20 UTC and rebuilds a temporary candidate catalog from
all active registered channels in the 22 Arab League countries, including
channels that previously failed or had no stream. It tests every real stream
with ffprobe, adds channels that pass, and removes channels that fail. The
candidate catalog is temporary and is not published in the repository.

## Roya TV

Roya uses a stable [on-demand HLS endpoint](https://roya-tv-on-demand.fuad-azzam-jarrar.chatgpt.site/roya.m3u8).
It obtains current signed playlists from Roya's public API when requested.
Variant playlist addresses remain stable as signatures rotate, and video
segments are delivered directly from Roya's CDN. Playlist responses instruct
players not to cache them; the resolver reuses its upstream catalog for at most
five minutes, always within the token's lifetime. It returns an error rather
than serving an expired link if Roya is unavailable or denies access.

Both playlist-generation workflows preserve this endpoint instead of writing
short-lived signatures into the repository. The source refresh remains scheduled
at minutes 7 and 37 UTC and does not re-add Roya if the full stream test removed
it. The daily stream test checks this endpoint like any other channel, removing
it on failure and restoring it on a later successful test.

Keep the existing Arab playlist subscription in OTT Navigator. It will pick up
the new Roya address on its next playlist refresh; a manual provider refresh is
only needed if the app continues using its cached old address.

Tests run from a GitHub-hosted runner, so geo-restricted results may differ
from Jordan. GitHub may delay or disable scheduled workflows; cron timing is
not guaranteed. Roya token renewal no longer depends on those schedules.
The schedules have no configured end date, but neither hosting nor upstream
availability can be guaranteed indefinitely.
