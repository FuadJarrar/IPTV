# IPTV

Automated IPTV playlists for OTT Navigator.

## Playlists

- [Arab countries — arab-list](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/arab-countries.m3u)
- [Existing all-country list](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/index.country.m3u)
- [Latest full Arab channel test summary](channel-status.md)
- [Detailed full-scan results](channel-status.csv)

Subscribe only to `arab-countries.m3u` for Arab channels, including Roya TV.
There is no separate Roya playlist and no hosted resolver in its playback path.
The existing all-country list remains available independently; it is not required.

## Direct Roya renewal

Roya's direct, signed HLS URL is obtained from its official public page API and
written inside `arab-countries.m3u`, with the Roya referrer and user-agent hints.
Observed initial links last approximately one hour; the broadcaster controls expiry.

The `Refresh direct Roya in arab-list` workflow is scheduled every 15 minutes,
at minutes 7, 22, 37 and 52 UTC. It obtains a fresh URL, probes the stream, decodes
at least five seconds of audio/video, and requires at least 30 minutes of token
validity remaining before publishing. Success adds or replaces Roya; failure
removes Roya until a later test passes. Other Arab channel entries are preserved.
The same verified Roya entry is mirrored into the existing all-country list.

Set the player to refresh arab-list every 10 minutes and disable persistent
playlist caching. GitHub cannot force a player to reload its cached URL, and a
playlist refresh may not restart a stream already playing. Reopen the channel
if the app retains an old playback session.

## Full channel testing

The full workflow is scheduled daily at 02:20 UTC. It refreshes the source catalog
and tests active registered channels from the 22 Arab League countries, including
previously failed channels. Only passing channels are published in arab-list;
`example.invalid` placeholders and blocklisted entries are never published there.
Roya is resolved and decoded last so its key does not age during the full scan.
The CSV and Markdown reports describe this full scan; subsequent Roya-only
refreshes are recorded in their workflow logs.

`Verify direct Roya playback` is also available as a read-only diagnostic job.
Regression tests run before either publishing workflow.

These are point-in-time tests from GitHub runners; results can differ by player,
network or region. Schedules have no configured end date, but GitHub can delay,
drop or disable scheduled jobs. Freshness and uninterrupted playback cannot be
guaranteed indefinitely. No server setup is needed on the player's device.
