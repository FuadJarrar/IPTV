import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_playlist as builder
import test_channels as tester


class RoyaPlaylistTests(unittest.TestCase):
    def test_build_uses_stable_endpoint_without_fetching_roya_api(self):
        source = '#EXTM3U\n#EXTINF:-1 tvg-id="Other.jo" group-title="Jordan",Other\nhttps://example.com/other.m3u8\n'
        fetched = {
            builder.SOURCE_M3U: source,
            builder.CHANNELS_CSV: 'id,name,country,closed\nRoyaTV.jo,Roya TV,JO,\n',
            builder.BLOCKLIST_CSV: 'channel,reason\n',
        }
        with tempfile.TemporaryDirectory() as folder:
            main = Path(folder) / 'index.m3u'
            arab = Path(folder) / 'arab.m3u'
            with patch.object(builder, 'OUTPUT', main), patch.object(builder, 'fetch_text', side_effect=fetched.__getitem__), patch('sys.argv', ['build_playlist.py', '--arab-output', str(arab)]):
                builder.main()
            for path in (main, arab):
                text = path.read_text()
                self.assertIn(builder.ROYA_STREAM_URL, text)
                self.assertNotIn('hdnts=', text)
            self.assertIn('https://example.com/other.m3u8', main.read_text())

    def test_refresh_preserves_other_channels_and_does_not_readd_roya(self):
        other = '#EXTM3U\n#EXTINF:-1 tvg-id="Other.jo",Other\nhttps://example.com/other.m3u8\n'
        roya = ['#EXTINF:-1 tvg-id="RoyaTV.jo",Roya TV', builder.ROYA_STREAM_URL]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'working.m3u'
            path.write_text(other)
            self.assertFalse(builder.replace_channel_entry(path, roya))
            self.assertEqual(path.read_text(), other)
            path.write_text(other + '#EXTINF:-1 tvg-id="RoyaTV.jo",Roya TV\nhttps://example.com/expired\n')
            self.assertTrue(builder.replace_channel_entry(path, roya))
            self.assertEqual(path.read_text(), other + '\n'.join(roya) + '\n')

    def test_working_playlist_rejects_failed_roya_and_placeholder_hosts(self):
        rows = [
            dict(test_status='Failed', url=builder.ROYA_STREAM_URL, lines=['#EXTINF:-1,Roya', builder.ROYA_STREAM_URL]),
            dict(test_status='Working', url='https://example.invalid/test', lines=['#EXTINF:-1,Placeholder', 'https://example.invalid/test']),
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'working.m3u'
            self.assertEqual(tester.write_working_playlist(path, rows), 0)
            rows[0]['test_status'] = 'Working'
            self.assertEqual(tester.write_working_playlist(path, rows), 1)
            self.assertIn(builder.ROYA_STREAM_URL, path.read_text())
            self.assertNotIn('example.invalid', path.read_text())


if __name__ == '__main__':
    unittest.main()
