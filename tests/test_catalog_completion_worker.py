"""Real host/inside wiring with fake Docker and providers; no network or grants."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

def load(name):
    path = Path(__file__).resolve().parents[1] / 'deployment/catalog' / (name + '.py')
    spec = importlib.util.spec_from_file_location('integration_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeDocker:
    def __init__(self, count):
        entries = [{'key':f'adapter.item_{i:03}', 'digest':f'{i:064x}',
                    'cached':False, 'evidence':True} for i in range(count)]
        self.probe = {'model':'deepseek-flash', 'prompt':'prompt-v1', 'entries':entries,
            'source_index_sha256':hashlib.sha256(json.dumps({item['key']:item['digest'] for item in entries},
                sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
        self.image_id = 'sha256:'+'b'*64
    def image(self):
        return self.image_id, 'release'
    def run(self, image, *, probe):
        assert probe
        return json.loads(json.dumps(self.probe))


def execute(driver, root, docker, worker, *, now=100000):
    return driver.run_job(root, job_id='all557', docker=docker, worker=worker,
                          expected_total=len(docker.probe['entries']), now=now, execute=True)


@pytest.fixture
def worker():
    return load('completion_worker')


@pytest.fixture
def driver():
    return load('complete_catalog')


def frozen_request(root, worker, *, job_id='all557'):
    directory = root/'automation/state/completions'/job_id/'reports'
    directory.mkdir(parents=True)
    key = 'tool.example'
    entries = {key: 'a'*64}
    identity = {'image_id': 'sha256:'+'b'*64, 'model': 'deepseek-flash', 'prompt': 'prompt-v1',
                'entries': entries, 'source_index_sha256': hashlib.sha256(json.dumps(
                    entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
    worker.atomic_json(directory.parent/'job.json', {'job_id': job_id, 'identity': identity})
    return directory, key, identity


def test_worker_entries_require_approval_before_any_file_or_docker(worker, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'load_auto', lambda: pytest.fail('No Docker activity is authorized'))
    with pytest.raises(worker.CompletionWorkerError, match='^ai_paid_execution_required$'):
        worker.run('invalid-without-reading', keys=['tool.example'], feedback={},
                   report_dir=tmp_path/'missing', job_id='job', batch_id='batch-00001')
    with pytest.raises(worker.CompletionWorkerError, match='^ai_paid_execution_required$'):
        worker.inside(tmp_path/'missing-request.json',tmp_path/'output.json')
    assert not (tmp_path/'output.json').exists()


def owned_docker(worker, monkeypatch, *, mode='success', visible=None):
    """Exercise the original nonce cleanup, replacing only daemon calls."""
    auto = worker.load_auto()
    original = auto.Docker
    created = []
    class OwnedDocker(original):
        def __init__(self, root):
            super().__init__(root)
            self.calls, self.removed = [], []
            created.append(self)
        def image(self):
            return 'sha256:'+'b'*64, 'release'
        def call(self, args, **kwargs):
            self.calls.append(args)
            cid = 'c'*64
            if args[0] == 'create':
                self.nonce = json.loads(self.ownerfile.read_text())['nonce']
                assert auto.RUN_LABEL+'='+self.nonce in args
                assert '--cap-drop' in args and args[args.index('--cap-drop')+1] == 'ALL'
                if mode == 'create_timeout':
                    raise auto.SchedulerError('docker_timeout')
                self.cidfile.write_text(cid)
                return subprocess.CompletedProcess(args, 0, cid, '')
            if args[0] == 'start':
                assert kwargs['timeout'] == 3600
                directory = self.root/'automation/state/completions/all557/reports'
                create = next(value for value in self.calls if value[0]=='create')
                request_name = Path(create[create.index('--request')+1]).name
                request = json.loads((directory/request_name).read_text(encoding='utf-8'))
                rows = [{'entry_key': key, 'source_digest': request['identity']['entries'][key]}
                        for key in request['keys']]
                report = {'results': rows, 'completion': {name: request[name] for name in ('job_id','batch_id','identity')}}
                if mode == 'failed':
                    report = {'ok': False, 'error': 'ValueError', 'results': []}
                elif mode == 'private_report':
                    rows[0].update(error='note_evidence_validation_failed', validation_issue='真实接线错误',
                                   previous_tutorial={'code': '仅作资料，不执行'})
                    worker.atomic_json(directory/(request['batch_id']+'.worker.json'), report)
                elif mode == 'wrong_identity':
                    rows[0]['source_digest'] = 'f'*64
                if visible:
                    for item in visible.probe['entries']:
                        if item['key'] in request['keys']:
                            item['cached'] = True
                return subprocess.CompletedProcess(args, 1 if mode in {'failed','private_report'} else 0,
                                                   'truncated stdout' if mode == 'private_report' else json.dumps(report), '')
            if args[0] == 'inspect':
                assert args[-1] in {cid, auto.CONTAINER}
                return subprocess.CompletedProcess(args, 0, f'{cid} /{auto.CONTAINER} managed {self.nonce}', '')
            if args[0] == 'rm':
                assert args == ['rm', '--force', cid]
                self.removed.append(cid)
                return subprocess.CompletedProcess(args, 0, '', '')
            raise AssertionError(args)
    auto.Docker = OwnedDocker
    monkeypatch.setattr(worker, 'load_auto', lambda: auto)
    return created


def test_first_real_worker_call_has_reports_directory_and_exact_owned_cleanup(worker, driver, tmp_path, monkeypatch):
    probe = FakeDocker(1)
    probe.image_id = 'sha256:'+'b'*64
    created = owned_docker(worker, monkeypatch, visible=probe)
    from functools import partial
    result = execute(driver, tmp_path, probe, partial(worker.run, execute=True))
    assert result['complete'] and result['reserved'] == 1
    docker = created[0]
    assert docker.root == tmp_path.resolve()  # reports.parents[4]
    assert docker.removed == ['c'*64]
    assert not docker.ownerfile.exists() and not docker.cidfile.exists()
    create = next(args for args in docker.calls if args[0]=='create')
    assert '/opt/catalog/completion_worker.py' in create
    mounts = [create[i+1] for i, arg in enumerate(create[:-1]) if arg == '--mount']
    assert any('catalog-writer.json' in value and value.endswith(',readonly') for value in mounts)
    assert any('deepseek.json' in value and value.endswith(',readonly') for value in mounts)
    assert not any('catalog-reader.json' in value for value in mounts)


@pytest.mark.parametrize('mode', ['failed','private_report'])
def test_nonzero_exit_retains_exact_failure_and_private_draft(worker, tmp_path, monkeypatch, mode):
    directory, key, identity = frozen_request(tmp_path, worker)
    created = owned_docker(worker, monkeypatch, mode=mode)
    report = worker.run(identity['image_id'], execute=True, keys=[key], feedback={}, report_dir=directory,
                        job_id='all557', batch_id='batch-00001')
    row = report['results'][0]
    assert row['entry_key']==key
    if mode == 'failed':
        assert row['error']=='ValueError'
    else:
        assert row['error']=='note_evidence_validation_failed' and row['validation_issue']=='真实接线错误'
        failure = {key:{'validation_issue':row['validation_issue']}}
        previous = worker.request_feedback([key], failure, directory.parent/'drafts', identity['entries'])[key]
        assert previous['previous_tutorial']=={'code':'仅作资料，不执行'}
    assert created[0].removed == ['c'*64]


def test_create_timeout_cleans_nonce_owned_daemon_container_without_refunding(worker, tmp_path, monkeypatch):
    directory, key, identity = frozen_request(tmp_path, worker)
    created = owned_docker(worker, monkeypatch, mode='create_timeout')
    with pytest.raises(RuntimeError, match='docker_timeout'):
        worker.run(identity['image_id'], execute=True, keys=[key], feedback={}, report_dir=directory,
                   job_id='all557', batch_id='batch-00001')
    assert created[0].removed == ['c'*64]
    assert not created[0].ownerfile.exists()


def test_wrong_report_digest_is_rejected_and_owned_container_still_removed(worker, tmp_path, monkeypatch):
    directory, key, identity = frozen_request(tmp_path, worker)
    created = owned_docker(worker, monkeypatch, mode='wrong_identity')
    with pytest.raises(worker.CompletionWorkerError, match='completion_frozen_identity_mismatch'):
        worker.run(identity['image_id'], execute=True, keys=[key], feedback={}, report_dir=directory,
                   job_id='all557', batch_id='batch-00001')
    assert created[0].removed == ['c'*64]


def test_inside_imports_formal_publisher_and_passes_bound_feedback_without_a_model(worker, tmp_path, monkeypatch):
    from nsgablack.catalog import curate, curation_provider, curation_store, examples
    directory, key, identity = frozen_request(tmp_path, worker)
    identity['prompt'] = curation_provider.PROMPT_VERSION
    request = {'identity':identity, 'job_id':'all557', 'batch_id':'batch-00001', 'keys':[key],
               'feedback':{key:{'source_digest':identity['entries'][key], 'validation_issue':'真实问题'}}}
    request_path, output_path = directory/'inside.request.json', directory/'inside.worker.json'
    worker.atomic_json(request_path, request)
    monkeypatch.setenv('NSGABLACK_CATALOG_DB_URL', 'unset-before-test')
    monkeypatch.setitem(sys.modules,'runtime',types.SimpleNamespace(
        load_mysql_config=lambda path:{}, mysql_url=lambda value:'test-only-no-connection'))
    monkeypatch.setattr(curate,'load_packets',lambda *a,**kw:{key:{'source_digest':identity['entries'][key]}})
    example_index={'examples':{},'entries':{}}
    monkeypatch.setattr(examples,'load_example_index',lambda path:example_index)
    monkeypatch.setattr(curation_provider,'load_deepseek_config',lambda path:curation_provider.DeepSeekConfig('test-only-key'))
    marker = object()
    monkeypatch.setattr(curation_store,'resolve_knowledge_store',lambda **kw:marker)
    monkeypatch.setattr(curation_provider,'DeepSeekGenerator',lambda config, **kw:marker)
    calls = []
    def publish(packets, store, generator, **kw):
        assert store is marker and generator is marker
        assert kw['workers']==4 and kw['keys']==(key,) and kw['include_failed_tutorial'] is True
        assert kw['feedback_by_key']==request['feedback'] and set(kw['source_roots'])=={'nsgablack','mlblack','blackbase'}
        assert kw['examples_index'] is example_index
        calls.append(kw)
        return {'ok':False,'results':[{'entry_key':key,'error':'note_evidence_validation_failed'}]}
    monkeypatch.setattr(curate,'curate_packets',publish)
    report = worker.inside(request_path,output_path,execute=True)
    assert calls and report['results'][0]['source_digest']==identity['entries'][key]
    assert json.loads(output_path.read_text(encoding='utf-8'))==report
    assert report['completion']['identity']==identity
    # An index hash mismatch rejects before any further generator/publisher call.
    request['identity']['source_index_sha256']='f'*64
    worker.atomic_json(request_path,request)
    with pytest.raises(worker.CompletionWorkerError,match='completion_frozen_identity_mismatch'):
        worker.inside(request_path,output_path,execute=True)
    assert len(calls)==1


def test_inside_failure_report_is_per_key_and_never_copies_exception_text(worker):
    report = worker.failure_report({'keys':['tool.example']}, RuntimeError('api_key=sk-secret-do-not-copy'))
    assert report['results']==[{'entry_key':'tool.example','error':'RuntimeError'}]
    assert 'secret' not in json.dumps(report)


@pytest.mark.parametrize('category',['ai_review_format_invalid','ai_review_format_discarded_findings'])
def test_independent_review_failures_keep_their_fixed_categories(worker,driver,category):
    from nsgablack.catalog.curation_provider import CurationProviderError
    report = worker.failure_report({'keys':['tool.example']},CurationProviderError(category))
    assert report['results'][0]['error']==category
    assert driver.safe_failure(report['results'][0])['error']==category


def test_atomic_inside_failure_and_draft_survive_host_interrupt_before_stdout(worker, driver, tmp_path, monkeypatch):
    probe = FakeDocker(1)
    key = probe.probe['entries'][0]['key']
    marker = tmp_path/'never-execute-model-code'
    tutorial = {'code':f"open({str(marker)!r}, 'w').write('never')"}
    def interrupted(image, **kw):
        job = json.loads((kw['report_dir'].parent/'job.json').read_text(encoding='utf-8'))
        worker.atomic_json(kw['report_dir']/(kw['batch_id']+'.worker.json'), {
            'ok':False, 'completion':{'job_id':kw['job_id'],'batch_id':kw['batch_id'],'identity':job['identity']},
            'results':[{'entry_key':key,'source_digest':job['identity']['entries'][key],
                        'error':'note_evidence_validation_failed','validation_issue':'保留真实接线问题',
                        'previous_tutorial':tutorial}]})
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        execute(driver,tmp_path,probe,interrupted)
    directory = tmp_path/'automation/state/completions/all557'
    job = json.loads((directory/'job.json').read_text(encoding='utf-8'))
    assert job['reserved']==1 and job['batches'][0]['worker_report_ref'].endswith('.worker.json')
    controlled = json.loads((directory/job['batches'][0]['report_ref']).read_text(encoding='utf-8'))
    assert controlled['results'][0]['validation_issue']=='保留真实接线问题'
    assert 'previous_tutorial' not in controlled['results'][0]
    assert not (directory/'drafts').exists()  # Host never reached its draft-copy stage.
    owned_docker(worker,monkeypatch,visible=probe)
    from functools import partial
    result = execute(driver,tmp_path,probe,partial(worker.run, execute=True),now=100900)
    request = json.loads((directory/'reports/batch-00002.request.json').read_text(encoding='utf-8'))
    assert request['feedback'][key]['validation_issue']=='保留真实接线问题'
    assert request['feedback'][key]['previous_tutorial']==tutorial
    assert result['complete'] and result['reserved']==2 and not marker.exists()
