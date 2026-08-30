import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import roya

NOW = 1800000000
URL = 'https://live.kwikmotion.com/royatvlive/royatv.smil/playlist.m3u8?hdnts=exp=1800003600~hmac=test'


class RoyaProviderTests(unittest.TestCase):
    @patch('roya.time.time', return_value=NOW)
    def test_url_checks_host_and_expiry(self, _):
        self.assertEqual(roya.validate_url(URL), URL)
        for url in (URL.replace('live.kwikmotion.com', 'example.invalid'),
                    URL.replace('https:', 'http:'), URL.replace('1800003600', '1800000010'),
                    URL.replace('royatvlive', 'different-channel')):
            with self.assertRaises(ValueError):
                roya.validate_url(url)

    @patch('roya.time.time', return_value=NOW)
    def test_public_api_response_preserves_original_signature(self, _):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'data': {'secured_url': URL}}).encode()
        with patch('roya.urllib.request.urlopen', return_value=response):
            result = roya.fresh_roya()
        self.assertEqual(result['url'], URL)
        self.assertEqual(result['lines'][-1], URL)

    def probe_success(self, row, **kwargs):
        return dict(row, test_status='Working', detail='audio+video', attempts=1, latency_ms=10)

    @patch('roya.time.time', return_value=NOW)
    def test_success_requires_decoding_and_remaining_lifetime(self, _):
        decoded = subprocess.CompletedProcess([], 0, 'frame=150\nout_time_us=6000000\nprogress=end\n', '')
        with patch('roya.fresh_roya', return_value=roya.row_for_url(URL)), patch('roya.subprocess.run', return_value=decoded):
            result = roya.verified_roya(probe=self.probe_success)
        self.assertEqual(result['test_status'], 'Working')
        self.assertIn('150 frames', result['detail'])

    @patch('roya.time.time', return_value=NOW + 2000)
    def test_link_that_ages_during_test_is_rejected(self, _):
        decoded = subprocess.CompletedProcess([], 0, 'frame=150\nout_time_us=6000000\n', '')
        with patch('roya.fresh_roya', return_value=roya.row_for_url(URL)), patch('roya.subprocess.run', return_value=decoded):
            self.assertNotEqual(roya.verified_roya(probe=self.probe_success)['test_status'], 'Working')

    def test_html_or_empty_video_is_not_working(self):
        decoded = subprocess.CompletedProcess([], 0, 'frame=0\nout_time_us=0\n', '')
        with patch('roya.fresh_roya', return_value=roya.row_for_url(URL)), patch('roya.subprocess.run', return_value=decoded):
            self.assertNotEqual(roya.verified_roya(probe=self.probe_success)['test_status'], 'Working')

    def test_failed_probe_does_not_decode_or_publish(self):
        def failed(row, **kwargs):
            return dict(row, test_status='Restricted (403)', detail='Denied', attempts=2)
        with patch('roya.fresh_roya', return_value=roya.row_for_url(URL)), patch('roya.subprocess.run') as decode:
            result = roya.verified_roya(probe=failed)
        self.assertEqual(result['test_status'], 'Restricted (403)')
        decode.assert_not_called()

    def test_api_failure_is_reported_without_a_url(self):
        with patch('roya.fresh_roya', side_effect=OSError('API unavailable')):
            result = roya.verified_roya(probe=self.probe_success)
        self.assertNotEqual(result['test_status'], 'Working')
        self.assertEqual(result['url'], '')


if __name__ == '__main__':
    unittest.main()
