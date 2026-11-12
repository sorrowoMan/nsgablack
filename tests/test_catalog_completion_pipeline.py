"""Completion retains exact failures and cannot publish a definite API error."""
import importlib.util
import json
from pathlib import Path
import pytest

from nsgablack.catalog.curate import curate_packets
from nsgablack.catalog.curation_provider import DeepSeekConfig, DeepSeekGenerator
from tests.test_catalog_curate import packet, Store, Generator


@pytest.mark.parametrize('match', [True, False])
def test_retry_feedback_belongs_to_exact_frozen_source(tmp_path, match):
    value = packet(tmp_path)
    class Retrying(Generator):
        def generate(self, request):
            assert ('editor_feedback' in request) is match
            if match:
                assert request['editor_feedback']['validation_issue'] == 'prior real finding'
            return super().generate(request)
    result = curate_packets({value['entry_key']:value}, Store(), Retrying(), model='test-model',
        feedback_by_key={value['entry_key']:{'source_digest':value['source_digest'] if match else '0'*64,
                                          'validation_issue':'prior real finding'}})
    assert result['ok']


def test_definite_api_error_never_reaches_review_or_store(tmp_path):
    from nsgablack.catalog.curation import prepare_packet
    from nsgablack.catalog.registry import CatalogEntry
    from tests.test_catalog_curation_tutorial import tutorial
    (tmp_path/'component.py').write_text('class Example:\n    def __init__(self, *, plan):\n        self.plan = plan\n')
    entry = CatalogEntry(key='tool.example',title='Example',kind='tool',import_path='mlblack.component:Example')
    value = prepare_packet(entry,[entry],{'mlblack':tmp_path})
    class Bad(Generator):
        requires_source_review = True
        def generate(self, request):
            result=super().generate(request)
            result['note']['tutorial']=tutorial(result['note']['evidence_ids'])
            result['note']['tutorial']['code']='from mlblack.component import Example\nitem = Example(wrong=1)'
            return result
        def review(self, *args):
            raise AssertionError('Definite API mismatch must be fixed before model review')
    store,generator=Store(),Bad()
    result=curate_packets({entry.key:value},store,generator,model='test-model',
        source_roots={'mlblack':tmp_path},include_failed_tutorial=True)
    assert not result['ok'] and not store.records and generator.calls==2
    row=result['results'][0]
    assert row['error']=='note_evidence_validation_failed'
    assert row['validation_issue'].startswith('Usage API contract mismatch:')
    assert row['previous_tutorial']['code'].endswith('Example(wrong=1)')


def test_independent_review_shape_repair_keeps_rejection_and_usage(monkeypatch):
    generator=DeepSeekGenerator(DeepSeekConfig('test-only-key'))
    calls=[]
    valid={'decision':'revise','issues':[{'location':'code','problem':'Wrong binding',
        'required_change':'Use actual constructor','evidence_ids':['e1']}],
        'checks':['Constructor checked'],'evidence_ids':['e1']}
    def complete(messages, **kwargs):
        calls.append(messages)
        return {'note':{**valid,**({'version':'unrequested-field'} if len(calls)==1 else {})},
                'usage':{'total_tokens':7},'actual_model':'deepseek-flash'}
    monkeypatch.setattr(generator,'_complete',complete)
    result=generator.review({'evidence':[{'id':'e1'}]},{'tutorial':{'code':'same candidate'}})
    assert result['note']==valid and result['usage']['total_tokens']==14
    assert result['usage']['review_format_repairs']==1
    assert len(calls)==2 and calls[0][:2]==calls[1][:2]
    assert '不是要求批准' in calls[1][-1]['content']


def test_private_retry_draft_is_source_bound_and_never_executed(tmp_path):
    import hashlib
    location=Path(__file__).resolve().parents[1]/'deployment/catalog/completion_worker.py'
    spec=importlib.util.spec_from_file_location('completion_worker_test',location)
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    key='tool.example';marker=tmp_path/'never-written'
    path=tmp_path/(hashlib.sha256(key.encode()).hexdigest()+'.json')
    code=f"open({str(marker)!r}, 'w').write('never')"
    path.write_text(json.dumps({'source_digest':'1'*64,'previous_tutorial':{'code':code}}))
    failure={key:{'validation_issue':'Prior error'}}
    assert 'previous_tutorial' not in worker.request_feedback([key],failure,tmp_path,{key:'2'*64})[key]
    assert worker.request_feedback([key],failure,tmp_path,{key:'1'*64})[key]['previous_tutorial']['code']==code
    assert not marker.exists()


def guide_packet(tmp_path):
    import hashlib
    from nsgablack.catalog.curation import prepare_packet
    from nsgablack.catalog.registry import CatalogEntry
    from tests.test_catalog_curation_seed import example
    base=packet(tmp_path)
    guide=example()
    snippet=guide['snippets'][0]
    doc=tmp_path/'guide-root/docs/catalog_usage/EXAMPLE_CN.md'
    doc.parent.mkdir(parents=True)
    doc.write_text(snippet['text'],encoding='utf-8')
    snippet.update(start_line=1,end_line=len(snippet['text'].splitlines()),
                   file_sha256=hashlib.sha256(doc.read_bytes()).hexdigest())
    guide.update(origin='manifest',title='Source guide')
    entry=CatalogEntry(**{key:base['entry'][key] for key in ('key','title','kind','import_path')})
    value=prepare_packet(entry,[entry],{'sample':tmp_path,'nsgablack':tmp_path/'guide-root'},usage_examples=[guide])
    return value,{'examples':{guide['id']:guide},'entries':{entry.key:[guide['id']]}}


def test_reference_is_source_bound_and_survives_format_repair_without_changing_packet(tmp_path):
    from copy import deepcopy
    value,index=guide_packet(tmp_path)
    original=deepcopy(value)
    class Guided(Generator):
        def generate(self,request):
            reference=request['source_guide_reference']
            assert reference['reference_only'] is True
            assert len(reference['variants'])==1
            assert set(reference['evidence_ids']) <= {e['id'] for e in value['evidence']}
            assert 'factory' in reference['main']['code_fragments'][0]['text']
            self.invalid=self.calls==0
            return super().generate(request)
    generator=Guided()
    result=curate_packets({value['entry_key']:value},Store(),generator,model='test-model',examples_index=index)
    assert result['ok'] and generator.calls==2 and value==original


def test_source_reference_does_not_override_independent_rejection(tmp_path):
    value,index=guide_packet(tmp_path)
    class Rejected(Generator):
        requires_source_review=True
        def generate(self,request):
            assert request['source_guide_reference']['reference_only']
            return super().generate(request)
        def review(self,source,note):
            assert 'source_guide_reference' not in source
            identifier=source['evidence'][0]['id']
            return {'note':{'decision':'revise','checks':['Actual source checked'],
                'issues':[{'location':'code','problem':'A real binding is missing',
                    'required_change':'Connect the actual consumer','evidence_ids':[identifier]}],
                'evidence_ids':[identifier]},'usage':{},'actual_model':'independent-test-model'}
    store,generator=Store(),Rejected()
    result=curate_packets({value['entry_key']:value},store,generator,model='test-model',examples_index=index)
    assert not result['ok'] and generator.calls==2 and not store.records
    assert result['results'][0]['source_review']['decision']=='revise'
