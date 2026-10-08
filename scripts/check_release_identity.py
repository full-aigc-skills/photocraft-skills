#!/usr/bin/env python3
"""只读核验技能发行与实际运行时的身份映射。"""
import argparse
import json
import re
from pathlib import Path


def check(root):
    package = json.loads((root / '.claude-plugin/plugin.json').read_text())
    suite = json.loads((root / 'skill-suite.json').read_text())
    runtime = json.loads((root / 'skills/photocraft-use/scripts/runtime.lock.json').read_text())
    errors = []
    if suite['version'] != package['version']:
        errors.append('suite_version_mismatch')
    if suite['runtimeVersion'] != runtime['resolvedVersion']:
        errors.append('runtime_version_mismatch')
    official='https://github.com/storytold/photocraft'
    if runtime.get('repository','').removesuffix('.git')!=official and not runtime.get('runtimeVariant'):
        errors.append('maintained_runtime_variant_missing')
    if runtime.get('runtimeVariant') and (runtime.get('upstreamRepository','').removesuffix('.git')!=official or not re.fullmatch(r'[a-f0-9]{40}',runtime.get('upstreamCommit',''))):
        errors.append('maintained_runtime_provenance_missing')
    if runtime['artifact'] != suite['pluginId'] + '-cli':
        errors.append('runtime_domain_mismatch')
    return {'status': 'FAIL' if errors else 'PASS', 'packageVersion': package['version'],
            'runtimeVersion': runtime['resolvedVersion'], 'runtimeVariant': runtime.get('runtimeVariant', 'upstream'),
            'runtimeRepository': runtime['repository'], 'errors': errors,
            'scope': 'release identity only; native and host acceptance separate'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = check(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['errors']))
