import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops_status import STAGES, summarize


def fixture():
    return {'evidence': [{'id': 'E1', 'verified': True, 'locator': 'private-session:check-1'}],
            'stages': {name: {'status': 'passed', 'evidence': ['E1']} for name in STAGES},
            'cleanup': {'status': 'passed', 'evidence': ['E1']}}


class CompletionTests(unittest.TestCase):
    def test_complete_declarations_are_not_a_truth_certificate(self):
        report, code = summarize(fixture())
        self.assertEqual(code, 0)
        self.assertEqual(report['assurance'], 'declared-evidence-only')

    def test_startup_does_not_imply_business_success(self):
        record = fixture()
        record['stages']['business'] = {'status': 'unknown', 'evidence': []}
        report, code = summarize(record)
        self.assertEqual(code, 1)
        self.assertEqual(report['completion'], 'partial')

    def test_cleanup_uncertainty_blocks_completion(self):
        record = fixture()
        record['cleanup'] = {'status': 'unknown', 'evidence': []}
        self.assertEqual(summarize(record)[1], 1)

    def test_failed_connection_is_partial_not_complete(self):
        record = fixture()
        record['stages']['connected']['status'] = 'failed'
        self.assertEqual(summarize(record)[1], 1)

    def test_pass_and_fail_need_verified_evidence(self):
        for status in ('passed', 'failed'):
            for refs, verified in [([], True), (['MISSING'], True), (['E1'], False)]:
                with self.subTest(status=status, refs=refs, verified=verified):
                    record = fixture()
                    record['evidence'][0]['verified'] = verified
                    record['stages']['started'] = {'status': status, 'evidence': refs}
                    self.assertEqual(summarize(record)[1], 2)

    def test_not_applicable_needs_rationale_and_business_is_required(self):
        record = fixture()
        record['stages']['connected'] = {'status': 'not_applicable', 'evidence': []}
        self.assertEqual(summarize(record)[1], 2)
        record['stages']['connected']['rationale'] = 'No account/backend in task'
        self.assertEqual(summarize(record)[1], 0)
        record['stages']['business'] = copy.deepcopy(record['stages']['connected'])
        self.assertEqual(summarize(record)[1], 2)

    def test_missing_stage_and_duplicate_ids_rejected(self):
        record = fixture()
        del record['stages']['started']
        self.assertEqual(summarize(record)[1], 2)
        record = fixture()
        record['evidence'].append(copy.deepcopy(record['evidence'][0]))
        self.assertEqual(summarize(record)[1], 2)

    def test_malformed_values_return_invalid_without_raw_data(self):
        for record in [None, [], {'evidence': [], 'stages': []}]:
            self.assertEqual(summarize(record)[1], 2)
        record = fixture()
        record['stages']['installed']['status'] = ['passed']
        self.assertEqual(summarize(record)[1], 2)

    def test_private_locator_and_unknown_fields_are_not_echoed(self):
        record = fixture()
        record['evidence'][0]['locator'] = 'sensitive-private-record'
        record['private_note'] = 'sensitive-private-record'
        self.assertNotIn('sensitive-private-record', json.dumps(summarize(record)[0]))

    def test_cli_valid_partial_and_unreadable_exit_codes(self):
        script = Path(__file__).with_name('ops_status.py')
        with tempfile.TemporaryDirectory(prefix='server-status-test-') as root:
            file = Path(root) / 'record.json'
            for expected, record in [(0, fixture()), (1, fixture())]:
                if expected == 1:
                    record['cleanup'] = {'status': 'unknown', 'evidence': []}
                file.write_text(json.dumps(record), encoding='utf-8')
                completed = subprocess.run([sys.executable, '-B', str(script), str(file)],
                                           capture_output=True, text=True, timeout=5)
                self.assertEqual(completed.returncode, expected)
            missing = subprocess.run([sys.executable, '-B', str(script), str(Path(root) / 'missing')],
                                     capture_output=True, text=True, timeout=5)
            self.assertEqual(missing.returncode, 2)
            self.assertNotIn(root, missing.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
