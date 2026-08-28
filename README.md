# IPTV

Automated IPTV playlists for OTT Navigator.

## Playlists

- [All countries](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/index.country.m3u)
- [Arab countries](https://raw.githubusercontent.com/FuadJarrar/IPTV/main/arab-countries.m3u)
- [Latest Arab channel test summary](channel-status.md)
- [Detailed Arab channel test results](channel-status.csv)

The arab-countries.m3u playlist contains all active registered channels from
the 22 Arab League countries:

- Available channels use a stream from the current IPTV-org playlist.
- Registered channels without a public stream remain listed without a visible
  status suffix.
- IPTV-org blocklisted channels are marked `[Blocked: reason]`.
- Unavailable and blocked entries use `example.invalid` placeholder URLs so
  they remain visible in IPTV applications but do not connect anywhere.
- Roya TV uses the refreshed stream obtained directly from the Roya TV page
  API.

Both playlists are rebuilt automatically every 30 minutes, at minutes 7 and
37 UTC.

All Arab playlist entries are tested automatically every day at 02:20 UTC.
The report checks real streams with ffprobe and records working, failed,
restricted, unavailable, and blocklisted channels. Tests run from a
GitHub-hosted runner, so geo-restricted results may differ from Jordan.
