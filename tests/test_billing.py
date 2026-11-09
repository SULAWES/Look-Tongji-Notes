"""Offline balance contracts: no account access or paid requests."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from tongji_backend.billing import BillingError, format_balance, query_balance
import look_tongji


def reply(cash='9.99', currency='CNY'):
    return Mock(returncode=0, stdout=json.dumps({'Success': True, 'Data': {
        'AvailableCashAmount': cash, 'AvailableAmount': '100.00', 'Currency': currency}}))


class BillingTests(unittest.TestCase):
    @patch('tongji_backend.billing.subprocess.run')
    def test_command_and_decimal_threshold(self, run):
        run.return_value = reply()
        result = query_balance('billing profile', '10')
        self.assertTrue(result['low_balance'])
        self.assertEqual(result['available_amount'], '100.00')
        self.assertEqual(run.call_args.args[0], [
            'aliyun', 'bssopenapi', 'QueryAccountBalance', '--profile', 'billing profile',
            '--region', 'cn-hangzhou', '--endpoint', 'business.aliyuncs.com'])
        self.assertEqual(run.call_args.kwargs['timeout'], 20)
        run.return_value = reply('10')
        self.assertFalse(query_balance('billing', '10')['low_balance'])

    @patch('tongji_backend.billing.subprocess.run')
    def test_currency_and_disabled_threshold(self, run):
        run.return_value = reply(currency='USD')
        result = query_balance('billing', '10')
        self.assertIsNone(result['low_balance'])
        self.assertIn('币种不同', format_balance(result))
        self.assertIsNone(query_balance('billing')['low_balance'])

    @patch('tongji_backend.billing.subprocess.run')
    def test_bad_configuration_never_calls_cli(self, run):
        for profile, threshold in [('', '10'), ('billing', 'NaN'), ('billing', 'Infinity'),
                                   ('billing', '-1'), ('billing', 'invalid')]:
            with self.assertRaises(BillingError):
                query_balance(profile, threshold)
        run.assert_not_called()

    @patch('tongji_backend.billing.subprocess.run')
    def test_failures_do_not_expose_diagnostics(self, run):
        for response in [Mock(returncode=1, stdout='secret', stderr='secret'),
                         Mock(returncode=0, stdout='secret'),
                         Mock(returncode=0, stdout='{"Success": false}'),
                         Mock(returncode=0, stdout='[]'), reply('NaN')]:
            run.return_value = response
            with self.assertRaises(BillingError) as error:
                query_balance('billing')
            self.assertNotIn('secret', str(error.exception))
        for error in [FileNotFoundError(), subprocess.TimeoutExpired('aliyun', 20), OSError()]:
            run.side_effect = error
            with self.assertRaises(BillingError):
                query_balance('billing')

    @patch('look_tongji._env_path', return_value=Path('/nonexistent/test-billing.env'))
    @patch.dict(os.environ, {'ALIYUN_BILLING_PROFILE': 'billing',
                            'ALIYUN_LOW_BALANCE_THRESHOLD': '10', 'ASR_ENGINE': 'fun-asr'}, clear=True)
    @patch('tongji_backend.billing.subprocess.run')
    def test_cli_json_and_batch_nonblocking(self, run, env_path):
        run.return_value = reply()
        args = look_tongji.build_parser().parse_args(['balance', '--json'])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(args.func(args), 0)
        self.assertTrue(json.loads(output.getvalue())['low_balance'])
        run.side_effect = FileNotFoundError()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(args.func(args), 1)
        self.assertFalse(json.loads(output.getvalue())['success'])
        batch = look_tongji.build_parser().parse_args(['batch-transcribe', '--course-id', '123'])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            look_tongji._show_batch_balance(batch)
        self.assertIn('继续执行', output.getvalue())
        run.reset_mock()
        with patch.dict(os.environ, {'ASR_ENGINE': 'bcut'}):
            look_tongji._show_batch_balance(batch)
        run.assert_not_called()
        args.profile = 'override'
        self.assertEqual(look_tongji._billing_options(args)[0], 'override')


if __name__ == '__main__':
    unittest.main()
