"""Isolated writer adapter for an explicitly authorized frozen completion job.

The host never opens a grant. Generated drafts are private diagnostic data and
are never executed; publication still uses validate_note and independent review.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import uuid


class CompletionWorkerError(RuntimeError):
    """Only fixed host/inside categories may cross the private worker boundary."""


_CATEGORIES = {
    'completion_image_invalid', 'completion_identity_invalid', 'completion_directory_invalid',
    'completion_job_image_mismatch', 'completion_keys_invalid', 'completion_release_changed',
    'completion_frozen_identity_mismatch', 'completion_worker_create_failed',
    'completion_worker_output_oversized', 'completion_worker_report_invalid',
    'completion_worker_exit_failed', 'completion_request_invalid',
    'ai_review_format_invalid', 'ai_review_format_discarded_findings',
    'ai_paid_execution_required',
}


def failure_report(request, exc):
    category = (str(exc) if (isinstance(exc, CompletionWorkerError) or type(exc).__name__ == 'CurationProviderError')
                and str(exc) in _CATEGORIES else type(exc).__name__)
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,99}', category):
        category = 'RuntimeError'
    return {'ok': False, 'error': category, 'results': [
        {'entry_key': key, 'error': category} for key in request.get('keys', [])
        if isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', key)]}


def atomic_json(path, value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('completion_report_oversized')
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def request_feedback(keys, feedback, directory, digests, *, previous_reports=None, identity=None, job_id=None):
    result = {}
    for key in keys:
        previous = feedback.get(key)
        if not isinstance(previous, dict):
            continue
        previous = {name: previous[name] for name in
                    ('validation_issue', 'source_review', 'issue') if name in previous}
        previous['source_digest'] = digests[key]
        # A draft belongs to this exact entry and frozen evidence, never a
        # different run's arbitrary model response or a caller-supplied path.
        path = directory / (hashlib.sha256(key.encode()).hexdigest() + '.json')
        if path.is_file() and path.stat().st_size < 256 * 1024:
            draft = json.loads(path.read_text(encoding='utf-8'))
            if draft.get('source_digest') == digests[key] and isinstance(draft.get('previous_tutorial'), dict):
                previous['previous_tutorial'] = draft['previous_tutorial']
        if 'previous_tutorial' not in previous and key in (previous_reports or {}):
            report_path = previous_reports[key]
            if report_path.is_file() and report_path.stat().st_size <= 8 * 1024 * 1024:
                report = json.loads(report_path.read_text(encoding='utf-8'))
                expected = {'job_id': job_id, 'batch_id': report_path.name.removesuffix('.worker.json'),
                            'identity': identity}
                if report.get('completion') == expected:
                    for row in report.get('results', []):
                        if (row.get('entry_key') == key and row.get('source_digest') == digests[key]
                                and isinstance(row.get('previous_tutorial'), dict)):
                            previous['previous_tutorial'] = row['previous_tutorial']
                            break
        result[key] = previous
    return result


def load_auto():
    spec = importlib.util.spec_from_file_location('completion_auto', Path(__file__).with_name('auto_curate.py'))
    auto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auto)
    return auto


def run(image, *, keys, feedback, report_dir, job_id, batch_id, execute=False):
    """Host entry, called only while complete_catalog holds worker.lock."""
    if execute is not True:
        raise CompletionWorkerError('ai_paid_execution_required')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise CompletionWorkerError('completion_image_invalid')
    if (not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', job_id)
            or not re.fullmatch(r'batch-[0-9]{5}', batch_id)):
        raise CompletionWorkerError('completion_identity_invalid')
    report_dir = Path(report_dir).resolve(strict=True)
    if (report_dir.name != 'reports' or report_dir.parent.name != job_id
            or [p.name for p in list(report_dir.parents)[1:4]] != ['completions', 'state', 'automation']):
        raise CompletionWorkerError('completion_directory_invalid')
    root = report_dir.parents[4]
    job = json.loads((report_dir.parent/'job.json').read_text(encoding='utf-8'))
    identity = job['identity']
    if job.get('job_id') != job_id or identity['image_id'] != image:
        raise CompletionWorkerError('completion_job_image_mismatch')
    if (not isinstance(keys, list) or not 1 <= len(keys) <= 20 or len(keys) != len(set(keys))
            or any(key not in identity['entries'] for key in keys)):
        raise CompletionWorkerError('completion_keys_invalid')
    drafts = report_dir.parent/'drafts'
    drafts.mkdir(mode=0o700, exist_ok=True)
    previous_reports = {}
    for key in keys:
        reference = job.get('targets', {}).get(key, {}).get('last_report_ref', '')
        match = re.fullmatch(r'reports/(batch-[0-9]{5})\.driver\.json', reference)
        if match:
            previous_reports[key] = report_dir/(match[1]+'.worker.json')
    request = {'keys': keys, 'identity': identity, 'job_id': job_id, 'batch_id': batch_id,
               'feedback': request_feedback(keys, feedback, drafts, identity['entries'],
                   previous_reports=previous_reports, identity=identity, job_id=job_id)}
    request_file = report_dir/(batch_id+'.request.json')
    atomic_json(request_file, request)

    auto = load_auto()
    docker = auto.Docker(root)
    if docker.image()[0] != image:
        raise CompletionWorkerError('completion_release_changed')
    docker.cleanup()
    nonce = uuid.uuid4().hex
    auto.atomic_json(docker.ownerfile, {'nonce': nonce})
    args = ['create', '--name', auto.CONTAINER, '--cidfile', str(docker.cidfile),
            '--label', auto.LABEL+'=managed', '--label', auto.RUN_LABEL+'='+nonce,
            '--user', '0:0', '--network', 'trs_capture_demo_default', '--read-only',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m', '--memory', '1g', '--cpus', '1',
            '--pids-limit', '128', '--security-opt', 'no-new-privileges:true', '--cap-drop', 'ALL',
            '--log-driver', 'none', '--mount', 'type=bind,src='+str(report_dir.parent)+',dst=/run/completion',
            '--env', 'NSGABLACK_CATALOG_WRITER_CONFIG=/run/secrets/catalog-writer.json']
    for name in ('catalog-writer.json', 'deepseek.json'):
        args += ['--mount', 'type=bind,src='+str(root/'secrets'/name)+',dst=/run/secrets/'+name+',readonly']
    args += [image, 'python', '/opt/catalog/completion_worker.py', '--inside', '--execute',
             '--request', '/run/completion/reports/'+request_file.name,
             '--output', '/run/completion/reports/'+batch_id+'.worker.json']
    try:
        created = docker.call(args)
        if created.returncode or not re.fullmatch(r'[0-9a-f]{64}', created.stdout.strip()):
            raise CompletionWorkerError('completion_worker_create_failed')
        docker.cid = created.stdout.strip()
        done = docker.call(['start', '--attach', docker.cid], timeout=3600)
        if len(done.stdout.encode()) > 8 * 1024 * 1024:
            raise CompletionWorkerError('completion_worker_output_oversized')
        # A completed atomic private report survives truncated attach output or
        # a nonzero exit; never discard actual row failures in favor of stdout.
        output_file = report_dir/(batch_id+'.worker.json')
        if output_file.is_file() and output_file.stat().st_size <= 8 * 1024 * 1024:
            report = json.loads(output_file.read_text(encoding='utf-8'))
        else:
            try:
                report = json.loads(done.stdout)
            except (ValueError, TypeError):
                raise CompletionWorkerError('completion_worker_report_invalid') from None
        if not isinstance(report, dict) or not isinstance(report.get('results'), list):
            raise CompletionWorkerError('completion_worker_report_invalid')
        if not report['results'] and report.get('error'):
            # Older inside entrypoints returned only a top-level safe category.
            report['results'] = [{'entry_key': key, 'error': report['error']} for key in keys]
        if done.returncode and not report['results']:
            raise CompletionWorkerError('completion_worker_exit_failed')
        metadata = report.get('completion')
        expected = {'job_id': job_id, 'batch_id': batch_id, 'identity': identity}
        if metadata is not None and metadata != expected:
            raise CompletionWorkerError('completion_frozen_identity_mismatch')
        seen = set()
        for row in report['results']:
            key = row.get('entry_key') if isinstance(row, dict) else None
            if key not in keys or key in seen:
                raise CompletionWorkerError('completion_worker_report_invalid')
            seen.add(key)
            if row.get('source_digest', identity['entries'][key]) != identity['entries'][key]:
                raise CompletionWorkerError('completion_frozen_identity_mismatch')
        # Preserve failed draft data privately so the next explicitly reserved
        # attempt can repair the previous code rather than start blindly.
        for row in report['results']:
            key = row.get('entry_key')
            if key in keys and isinstance(row.get('previous_tutorial'), dict):
                atomic_json(drafts/(hashlib.sha256(key.encode()).hexdigest()+'.json'),
                    {'source_digest': identity['entries'][key], 'previous_tutorial': row['previous_tutorial']})
        return report
    finally:
        docker.cleanup()


def inside(request_file, output_file, *, execute=False):
    if execute is not True:
        raise CompletionWorkerError('ai_paid_execution_required')
    from dataclasses import replace
    from runtime import load_mysql_config, mysql_url
    from nsgablack.catalog.curate import load_packets, curate_packets
    from nsgablack.catalog.curation_provider import DeepSeekGenerator, load_deepseek_config, PROMPT_VERSION
    from nsgablack.catalog.curation_store import resolve_knowledge_store
    from nsgablack.catalog.examples import load_example_index
    request = json.loads(request_file.read_text(encoding='utf-8'))
    packets = load_packets(Path('/opt/catalog/knowledge-packets.json'),
                           index_path=Path('/opt/catalog/knowledge-sources.json'))
    identity = request['identity']
    config = load_deepseek_config('/run/secrets/deepseek.json')
    entries = {key: packet['source_digest'] for key, packet in packets.items()}
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if (config.model != identity['model'] or PROMPT_VERSION != identity['prompt']
            or entries != identity['entries'] or digest != identity['source_index_sha256']):
        raise CompletionWorkerError('completion_frozen_identity_mismatch')
    if (not isinstance(request.get('keys'), list) or not 1 <= len(request['keys']) <= 20
            or len(set(request['keys'])) != len(request['keys'])
            or any(key not in entries for key in request['keys'])):
        raise CompletionWorkerError('completion_request_invalid')
    config = replace(config, max_output_tokens=max(config.max_output_tokens, 12288), timeout_seconds=120)
    os.environ['NSGABLACK_CATALOG_DB_URL'] = mysql_url(load_mysql_config('/run/secrets/catalog-writer.json'))
    store = resolve_knowledge_store(readonly=False)
    report = curate_packets(packets, store, DeepSeekGenerator(config, allow_paid_requests=True), model=config.model,
        limit=len(request['keys']), workers=4, keys=tuple(request['keys']),
        source_roots={name:Path('/opt/src')/name for name in ('nsgablack','blackbase','mlblack')},
        examples_index=load_example_index(Path('/opt/catalog/examples.json')),
        feedback_by_key=request.get('feedback'), include_failed_tutorial=True)
    for row in report['results']:
        row['source_digest'] = packets[row['entry_key']]['source_digest']
    report['completion'] = {'job_id': request['job_id'], 'batch_id': request['batch_id'], 'identity': identity}
    atomic_json(output_file, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inside', action='store_true', required=True)
    parser.add_argument('--execute', action='store_true', help='Explicitly allow paid model requests for this batch')
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        parser.error('--execute is required for paid model requests')
    try:
        report = inside(args.request,args.output,execute=True)
        print(json.dumps(report,ensure_ascii=False))
        if not report.get('ok'):
            raise SystemExit(1)
    except Exception as exc:
        try:
            request = json.loads(args.request.read_text(encoding='utf-8'))
            report = failure_report(request, exc)
            report['completion'] = {name: request[name] for name in ('job_id', 'batch_id', 'identity')}
            atomic_json(args.output, report)
        except Exception:
            report = {'ok': False, 'error': 'RuntimeError', 'results': []}
        print(json.dumps(report, ensure_ascii=False))
        raise SystemExit(1)
