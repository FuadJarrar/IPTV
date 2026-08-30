import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import build_playlist as builder
import test_channels as tester
from roya import row_for_url


def fresh_url():
    return ('https://live.kwikmotion.com/royatvlive/royatv.smil/playlist.m3u8'
            f'?hdnts=exp={int(time.time()) + 3600}~hmac=test')


class RoyaPlaylistTests(unittest.TestCase):
    def test_build_uses_direct_url_without_hosted_resolver(self):
        source = '#EXTM3U\n#EXTINF:-1 tvg-id="Other.jo" group-title="Jordan",Other\nhttps://example.com/other.m3u8\n'
        fetched = {builder.SOURCE_M3U: source,
                   builder.CHANNELS_CSV: 'id,name,country,closed\nRoyaTV.jo,Roya TV,JO,\n',
                   builder.BLOCKLIST_CSV: 'channel,reason\n'}
        url = fresh_url()
        with tempfile.TemporaryDirectory() as folder:
            main, arab = Path(folder) / 'index.m3u', Path(folder) / 'arab.m3u'
            with patch.object(builder, 'OUTPUT', main), patch.object(builder, 'fresh_roya', return_value=row_for_url(url)), patch.object(builder, 'fetch_text', side_effect=fetched.__getitem__), patch('sys.argv', ['build_playlist.py', '--arab-output', str(arab)]):
                builder.main()
            for path in (main, arab):
                self.assertIn(url, path.read_text())
                self.assertNotIn('chatgpt.site', path.read_text())
            self.assertIn('https://example.com/other.m3u8', main.read_text())

    def test_refresh_can_restore_verified_roya_and_remove_failed_roya(self):
        other = '#EXTM3U\n#EXTINF:-1 tvg-id="Other.jo" group-title="Jordan",Other\nhttps://example.com/other.m3u8\n'
        roya = row_for_url(fresh_url())['lines']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'arab-countries.m3u'
            path.write_text(other)
            builder.update_roya_entry(path, roya)
            self.assertEqual(path.read_text(), other + '\n'.join(roya) + '\n')
            builder.update_roya_entry(path, roya)
            self.assertEqual(path.read_text().count('tvg-id="RoyaTV.jo"'), 1)
            builder.update_roya_entry(path, None)
            self.assertEqual(path.read_text(), other)

    def test_refresh_rejects_short_lived_urls_without_modifying_list(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'arab-countries.m3u'
            path.write_text('#EXTM3U\n')
            entry = row_for_url('https://live.kwikmotion.com/royatvlive/royatv.smil/playlist.m3u8?hdnts=exp=1~hmac=test')
            with self.assertRaises(ValueError):
                builder.update_roya_entry(path, entry['lines'])
            self.assertEqual(path.read_text(), '#EXTM3U\n')

    def test_roya_api_failure_keeps_candidate_unavailable(self):
        text, counts = builder.build_arab_playlist('#EXTM3U', [], None,
            'id,name,country,closed\nRoyaTV.jo,Roya TV,JO,\n', 'channel,reason\n')
        self.assertIn('availability="unavailable"', text)
        self.assertEqual(counts['available'], 0)

    def test_refresh_only_does_not_fetch_other_catalogs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'arab-countries.m3u'
            path.write_text('#EXTM3U\n')
            result = row_for_url(fresh_url())
            result.update(test_status='Working', detail='audio+video', attempts=1)
            with patch.object(builder, 'verified_roya', return_value=result), patch.object(builder, 'OUTPUT', Path(folder) / 'absent.m3u'), patch.object(builder, 'fetch_text', side_effect=AssertionError('Unnecessary catalog request')), patch('sys.argv', ['build_playlist.py', '--refresh-roya-only', '--refresh-working-playlist', str(path)]):
                builder.main()
            self.assertIn(result['url'], path.read_text())

    def test_working_playlist_rejects_failed_roya_and_placeholder_hosts(self):
        rows = [dict(test_status='Failed', url=fresh_url(), lines=['#EXTINF:-1,Roya', fresh_url()]),
                dict(test_status='Working', url='https://example.invalid/test', lines=['#EXTINF:-1,Placeholder', 'https://example.invalid/test'])]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'working.m3u'
            self.assertEqual(tester.write_working_playlist(path, rows), 0)
            rows[0]['test_status'] = 'Working'
            self.assertEqual(tester.write_working_playlist(path, rows), 1)
            self.assertNotIn('example.invalid', path.read_text())


if __name__ == '__main__':
    unittest.main()
