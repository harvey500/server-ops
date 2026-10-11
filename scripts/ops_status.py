"""Offline validation of declared deployment evidence, not a health or truth check."""

import json
import re
import sys
from pathlib import Path


STAGES = ('installed', 'started', 'connected', 'business')
STATUSES = {'passed', 'failed', 'unknown', 'not_applicable'}
ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')


def summarize(record):
    errors = set()
    if not isinstance(record, dict):
        return {'completion': 'invalid', 'errors': ['invalid-record']}, 2
    evidence = record.get('evidence')
    stages = record.get('stages')
    if not isinstance(evidence, list) or not isinstance(stages, dict):
        return {'completion': 'invalid', 'errors': ['invalid-schema']}, 2
    verified = {}
    for item in evidence:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or
                not ID.fullmatch(item['id']) or type(item.get('verified')) is not bool or
                not isinstance(item.get('locator'), str) or not item['locator'].strip()):
            errors.add('invalid-evidence')
            continue
        if item['id'] in verified:
            errors.add('duplicate-evidence')
        verified[item['id']] = item['verified']
    if set(stages) != set(STAGES):
        errors.add('stage-set-mismatch')
    result = {}
    for name in (*STAGES, 'cleanup'):
        item = record.get('cleanup') if name == 'cleanup' else stages.get(name)
        if not isinstance(item, dict) or not isinstance(item.get('status'), str) or item['status'] not in STATUSES:
            errors.add('invalid-stage')
            continue
        status = item['status']
        refs = item.get('evidence')
        if (not isinstance(refs, list) or any(not isinstance(ref, str) or not ID.fullmatch(ref) for ref in refs)):
            errors.add('invalid-evidence-reference')
            continue
        if len(set(refs)) != len(refs):
            errors.add('duplicate-evidence-reference')
        if any(ref not in verified for ref in refs):
            errors.add('missing-evidence-reference')
        if status in ('passed', 'failed') and (not refs or any(not verified.get(ref, False) for ref in refs)):
            errors.add('unsupported-status')
        if status == 'not_applicable':
            if not isinstance(item.get('rationale'), str) or not item['rationale'].strip():
                errors.add('missing-rationale')
            if name == 'business':
                errors.add('business-required')
        result[name] = {'status': status, 'evidence': sorted(set(refs))}
    if errors:
        return {'completion': 'invalid', 'errors': sorted(errors)}, 2
    complete = all(item['status'] in ('passed', 'not_applicable') for item in result.values())
    return {'completion': 'complete' if complete else 'partial', 'stages': result,
            'assurance': 'declared-evidence-only'}, 0 if complete else 1


def main():
    if len(sys.argv) != 2:
        print('{"completion":"invalid","errors":["usage"]}')
        return 2
    try:
        file = Path(sys.argv[1])
        if file.stat().st_size > 262144:
            raise ValueError('Record too large')
        report, code = summarize(json.loads(file.read_text(encoding='utf-8')))
    except (OSError, ValueError, UnicodeError):
        print('{"completion":"invalid","errors":["unreadable-record"]}')
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
