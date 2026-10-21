"""Fun-ASR with private temporary uploads and persistent paid-task checkpoints."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager

import requests

from . import config
from .transcriber import TranscriptionError, _format_srt_time


@contextmanager
def _job_lock(path):
    # OS locks release on process exit, including crashes. Keep the lock file.
    with path.open('a+b') as handle:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            handle.write(b'0')
            handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise TranscriptionError('Fun-ASR: this audio is already being processed.') from None
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise TranscriptionError('Fun-ASR: this audio is already being processed.') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _save(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.asr-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def render_result(raw):
    utterances = []
    for transcript in raw.get('transcripts', []):
        for sentence in transcript.get('sentences', []):
            text = sentence.get('text', '').strip()
            if not text:
                continue
            start, end = int(sentence['begin_time']), int(sentence['end_time'])
            if start < 0 or end < start:
                raise TranscriptionError('Fun-ASR returned invalid timestamps.')
            utterances.append({'start_time': start, 'end_time': end, 'transcript': text})
    utterances.sort(key=lambda item: item['start_time'])
    if not utterances:
        raise TranscriptionError('Fun-ASR returned no timestamped speech.')
    text = '\n'.join(item['transcript'] for item in utterances)
    srt = '\n'.join(
        f"{i}\n{_format_srt_time(u['start_time'])} --> {_format_srt_time(u['end_time'])}\n{u['transcript']}\n"
        for i, u in enumerate(utterances, 1)
    )
    return text, srt, utterances


class FunASRClient:
    model = 'fun-asr'
    base_url = 'https://dashscope.aliyuncs.com/api/v1'

    def __init__(self, api_key=None, state_dir=None, session=None):
        self.key = config.DASHSCOPE_API_KEY if api_key is None else api_key
        if not self.key.strip():
            raise TranscriptionError('Fun-ASR requires DASHSCOPE_API_KEY (Beijing). Run setup or set it in the skill .env.')
        self.state_dir = Path(state_dir or config.FUN_ASR_STATE_DIR)
        self.session = session or requests.Session()

    def _request(self, method, url, *, authorized=False, **kwargs):
        headers = kwargs.pop('headers', {})
        if authorized:
            headers['Authorization'] = 'Bearer ' + self.key
        try:
            response = self.session.request(method, url, headers=headers, timeout=(15, 60), **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            # Signed URLs and credentials must not appear in diagnostics.
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            raise TranscriptionError(f'Fun-ASR HTTP request failed ({status or type(exc).__name__}); checkpoint retained.') from None

    def _upload(self, path):
        policy = self._request('GET', self.base_url + '/uploads', authorized=True,
                               params={'action': 'getPolicy', 'model': self.model}).json()['data']
        if not policy['upload_host'].startswith('https://'):
            raise TranscriptionError('Fun-ASR upload policy requires HTTPS.')
        limit = min(float(policy.get('max_file_size_mb', 1024)), 1024) * 1024 * 1024
        if path.stat().st_size > limit:
            raise TranscriptionError('Audio exceeds Fun-ASR temporary upload size limit; split the lecture first.')
        name = uuid.uuid4().hex + path.suffix
        key = policy['upload_dir'].rstrip('/') + '/' + name
        fields = {'OSSAccessKeyId': policy['oss_access_key_id'], 'Signature': policy['signature'],
                  'policy': policy['policy'], 'x-oss-object-acl': policy['x_oss_object_acl'],
                  'x-oss-forbid-overwrite': policy['x_oss_forbid_overwrite'], 'key': key,
                  'success_action_status': '200'}
        boundary = 'asr-' + uuid.uuid4().hex
        # Disk-backed multipart avoids loading long lecture audio into RAM.
        with tempfile.TemporaryFile() as body:
            for field, value in fields.items():
                body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{value}\r\n'.encode())
            body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
            with path.open('rb') as audio:
                shutil.copyfileobj(audio, body, 1024 * 1024)
            body.write(f'\r\n--{boundary}--\r\n'.encode())
            size = body.tell()
            body.seek(0)
            self._request('POST', policy['upload_host'], data=body,
                          headers={'Content-Type': 'multipart/form-data; boundary=' + boundary,
                                   'Content-Length': str(size)})
        return 'oss://' + key

    def transcribe_file(self, audio_path, timeout=7200):
        path = Path(audio_path)
        if not path.is_file() or not path.stat().st_size:
            raise TranscriptionError('Audio file is missing or empty.')
        digest = hashlib.sha256()
        # Include account key and all recognition settings, without storing the key.
        digest.update(json.dumps([self.key, self.base_url, self.model, 'zh', 0]).encode())
        with path.open('rb') as audio:
            for chunk in iter(lambda: audio.read(1024 * 1024), b''):
                digest.update(chunk)
        job = self.state_dir / digest.hexdigest()
        job.mkdir(parents=True, exist_ok=True, mode=0o700)
        with _job_lock(job / 'job.lock'):
            return self._run(path, job, timeout)

    def _run(self, path, job, timeout):
        result_path, state_path = job / 'result.json', job / 'task.json'
        if result_path.exists():
            print('[Fun-ASR] Reusing cached result.')
            return render_result(json.loads(result_path.read_text(encoding='utf-8')))
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
        if state.get('phase') in ('submitting', 'failed'):
            raise TranscriptionError(f'Fun-ASR task is {state["phase"]}; inspect {state_path}. Do not automatically delete the checkpoint or resubmit.')
        if not state.get('task_id'):
            url = self._upload(path)
            state = {'phase': 'submitting', 'model': self.model}
            _save(state_path, state)  # Persist BEFORE POST: ambiguous timeouts must not duplicate billing.
            response = self._request('POST', self.base_url + '/services/audio/asr/transcription', authorized=True,
                headers={'X-DashScope-Async': 'enable', 'X-DashScope-OssResourceResolve': 'enable'},
                json={'model': self.model, 'input': {'file_urls': [url]},
                      'parameters': {'channel_id': [0], 'language_hints': ['zh']}}).json()
            task_id = response.get('output', {}).get('task_id')
            if not task_id:
                raise TranscriptionError('Fun-ASR submission did not return a task ID; inspect the checkpoint before retrying.')
            state = {'phase': 'queued', 'model': self.model, 'task_id': task_id}
            _save(state_path, state)
        print('[Fun-ASR] Polling saved task ' + state['task_id'])
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            output = self._request('GET', self.base_url + '/tasks/' + state['task_id'], authorized=True).json()['output']
            status = output['task_status']
            if status == 'SUCCEEDED':
                results = output.get('results', [])
                if len(results) != 1 or results[0].get('subtask_status') != 'SUCCEEDED':
                    state['phase'] = 'failed'
                    _save(state_path, state)
                    raise TranscriptionError('Fun-ASR audio subtask failed; checkpoint retained.')
                url = results[0]['transcription_url']
                if not url.startswith('https://'):
                    raise TranscriptionError('Fun-ASR result URL requires HTTPS.')
                raw = self._request('GET', url).json()
                result = render_result(raw)
                _save(result_path, raw)
                state['phase'] = 'done'
                _save(state_path, state)
                return result
            if status not in ('PENDING', 'RUNNING'):
                state.update(phase='failed', status=status)
                _save(state_path, state)
                raise TranscriptionError(f'Fun-ASR task ended with {status}; checkpoint retained.')
            time.sleep(min(10, max(0, deadline - time.monotonic())))
        raise TranscriptionError('Fun-ASR polling timed out; rerun to resume the saved task without resubmitting.')
