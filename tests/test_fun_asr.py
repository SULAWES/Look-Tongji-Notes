"""Offline contract tests; no cloud credentials or paid requests required."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import requests
from tongji_backend import config
from tongji_backend.fun_asr import FunASRClient, render_result, _job_lock
from tongji_backend.transcriber import Transcriber, TranscriptionError

RAW = {'transcripts': [{'sentences': [
    {'begin_time': 1250, 'end_time': 3000, 'text': '汽车理论。'},
    {'begin_time': 3723004, 'end_time': 3725000, 'text': '驱动力。'}]}]}
POLICY = {'data': {'upload_host': 'https://storage.example/upload', 'upload_dir': 'private/test',
    'oss_access_key_id': 'upload-id', 'signature': 'sig', 'policy': 'policy',
    'x_oss_object_acl': 'private', 'x_oss_forbid_overwrite': 'true', 'max_file_size_mb': 10}}
DONE = {'output': {'task_status': 'SUCCEEDED', 'results': [
    {'subtask_status': 'SUCCEEDED', 'transcription_url': 'https://storage.example/result'}]}}


def response(value):
    return Mock(json=Mock(return_value=value), raise_for_status=Mock())


class FunASRTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio = self.root / 'audio.mp3'
        self.audio.write_bytes(b'test-audio')
        self.http = Mock()
        self.client = FunASRClient('private-test-key', self.root / 'state', self.http)

    def state(self):
        return json.loads(next((self.root / 'state').glob('*/task.json')).read_text())

    def test_timestamps_and_empty_speech(self):
        text, srt, utterances = render_result(RAW)
        self.assertIn('汽车理论', text)
        self.assertIn('00:00:01,250 --> 00:00:03,000', srt)
        self.assertIn('01:02:03,004', srt)
        self.assertEqual(utterances[0]['start_time'], 1250)
        with self.assertRaises(TranscriptionError):
            render_result({'transcripts': []})

    def test_default_selection_and_no_missing_key_fallback(self):
        with patch.object(config, 'ASR_ENGINE', 'fun-asr'), patch.object(config, 'DASHSCOPE_API_KEY', ''):
            with patch.object(Transcriber, '_download_audio') as download:
                with self.assertRaisesRegex(TranscriptionError, 'DASHSCOPE_API_KEY'):
                    Transcriber().transcribe_url('https://example/audio')
                download.assert_not_called()
        with patch.object(config, 'ASR_ENGINE', 'typo'):
            with self.assertRaisesRegex(TranscriptionError, 'Unsupported'):
                Transcriber()._get_asr()
        with patch.object(config, 'ASR_ENGINE', 'bcut'):
            self.assertEqual(type(Transcriber()._get_asr()).__name__, 'BcutASRClient')

    def test_upload_submission_cache_and_credential_separation(self):
        bodies = []
        values = iter([POLICY, {}, {'output': {'task_id': 'task-123'}}, DONE, RAW])
        def request(method, url, **kwargs):
            if url.endswith('/upload'):
                bodies.append(kwargs['data'].read())
            return response(next(values))
        self.http.request.side_effect = request
        expected = self.client.transcribe_file(self.audio)
        self.assertIn(b'test-audio', bodies[0])
        self.assertIn(b'name="file"', bodies[0])
        calls = self.http.request.call_args_list
        self.assertNotIn('Authorization', calls[1].kwargs['headers'])
        self.assertNotIn('Authorization', calls[4].kwargs['headers'])
        self.assertEqual(calls[2].kwargs['headers']['X-DashScope-OssResourceResolve'], 'enable')
        self.assertTrue(calls[2].kwargs['json']['input']['file_urls'][0].startswith('oss://'))
        self.http.request.reset_mock()
        self.assertEqual(self.client.transcribe_file(self.audio), expected)
        self.http.request.assert_not_called()
        self.assertEqual(self.state()['phase'], 'done')
        for path in (self.root / 'state').rglob('*.json'):
            self.assertNotIn('private-test-key', path.read_text())

    def test_uncertain_submit_cannot_repeat_paid_post(self):
        self.client._upload = Mock(return_value='oss://test/audio')
        self.http.request.side_effect = requests.Timeout('signed secret URL')
        with self.assertRaises(TranscriptionError) as error:
            self.client.transcribe_file(self.audio)
        self.assertNotIn('signed secret', str(error.exception))
        self.assertEqual(self.state()['phase'], 'submitting')
        with self.assertRaisesRegex(TranscriptionError, 'submitting'):
            self.client.transcribe_file(self.audio)
        self.assertEqual(self.http.request.call_count, 1)
        self.assertEqual(self.client._upload.call_count, 1)

    def test_resume_after_polling_network_failure(self):
        self.client._upload = Mock(return_value='oss://test/audio')
        self.http.request.side_effect = [response({'output': {'task_id': 'saved'}}), requests.Timeout()]
        with self.assertRaises(TranscriptionError):
            self.client.transcribe_file(self.audio)
        self.assertEqual(self.state()['task_id'], 'saved')
        self.http.request.reset_mock()
        self.http.request.side_effect = [response(DONE), response(RAW)]
        self.client.transcribe_file(self.audio)
        self.assertTrue(all(call.args[0] == 'GET' for call in self.http.request.call_args_list))
        self.assertEqual(self.client._upload.call_count, 1)

    def test_failed_subtask_cannot_be_resubmitted_by_batch(self):
        self.client._upload = Mock(return_value='oss://test/audio')
        self.http.request.side_effect = [response({'output': {'task_id': 'saved'}}),
            response({'output': {'task_status': 'SUCCEEDED', 'results': [{'subtask_status': 'FAILED'}]}})]
        with self.assertRaises(TranscriptionError):
            self.client.transcribe_file(self.audio)
        self.http.request.reset_mock()
        with self.assertRaisesRegex(TranscriptionError, 'failed'):
            self.client.transcribe_file(self.audio)
        self.http.request.assert_not_called()

    def test_timeout_preserves_task(self):
        self.client._upload = Mock(return_value='oss://test/audio')
        self.http.request.return_value = response({'output': {'task_id': 'saved'}})
        with self.assertRaisesRegex(TranscriptionError, 'timed out'):
            self.client.transcribe_file(self.audio, timeout=0)
        self.assertEqual(self.state()['task_id'], 'saved')
        self.assertEqual(self.http.request.call_count, 1)

    def test_cli_writes_provider_metadata(self):
        import look_tongji
        client = Mock()
        client.get_video_url.return_value = 'https://example/video'
        client.get_stream_params.return_value = ('https://example/stream', None)
        output = self.root / 'output'
        with patch.object(config, 'ASR_ENGINE', 'fun-asr'), patch.object(
                Transcriber, 'transcribe_url', return_value=render_result(RAW)):
            code = look_tongji._run_transcript_job(client=client, username='test',
                course_id='course', sub_id='lecture', lecture_url='', output_dir=str(output))
        self.assertEqual(code, 0)
        metadata = json.loads((output / 'course_lecture.json').read_text())
        self.assertEqual(metadata['asr_engine'], 'fun-asr')
        self.assertEqual(metadata['asr_model'], 'fun-asr')
        self.assertIn('汽车理论', (output / 'course_lecture.txt').read_text())
        self.assertIn('00:00:01,250', (output / 'course_lecture.srt').read_text())

    def test_simultaneous_job_rejected_and_lock_released(self):
        path = self.root / 'test.lock'
        with _job_lock(path):
            with self.assertRaises(TranscriptionError):
                with _job_lock(path):
                    self.fail('second job acquired lock')
        with _job_lock(path):
            pass


if __name__ == '__main__':
    unittest.main()
