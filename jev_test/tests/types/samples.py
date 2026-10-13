"""무엇: 자료형 합성 표본 · 입력: 없음 · 출력: dataclass 목록 · 계약 §8-5."""

from jeveval.types import (
    AttemptRecord, BoundQuestion, CallRecord, Cost, FinalRecord, Item, LengthInfo,
    ParsedAnswer, Population, QStats, QuestionSpec, Rendered, Request, RequestOutcome, RiskCell,
    ScoreTable, SourceRow, SplitPlan, TaskSpec, Threshold, ThresholdFile,
)


def bound():
    return BoundQuestion(id='ready', role='success', type='noul', instructions='준비됐나요?',
                         options=None, criteria={'true':'준비됨','false':'아직'}, label='ready', gold='true')


def item():
    return Item(set='synthetic', group_id='11', item_id='12', state_fields='등을 켰다.',
                questions=[bound()], meta={'service':None,'stratum':None,'flags':[]}, baseline=None)


def call():
    return CallRecord(call_id='s:g:i', attempts=1, status='ok', reason=None, warnings=[],
        request_sha256='a'*64, length=LengthInfo(length_tokens=12,target_end=7,limit=100,fixed_tokens=5),
        usage={'input_tokens':12}, answers_parsed={'ready':ParsedAnswer(
            type='noul',answer='true',probs={'true':.8,'false':.2},confidence=.8)})


def attempt():
    return AttemptRecord(call_id='s:g:i',logical_id='s:g:i',attempt=1,
        session_id='00000000-0000-4000-8000-000000000001',
        started_at='2026-10-13T00:00:00.000Z',ended_at='2026-10-13T00:00:01.000Z',
        latency_ms=1000,http_status=200,retry_after=None,transport_error=None,
        terminal=True,request_sha256='a'*64,response_raw='{}')


def threshold_file():
    t = Threshold(tau='0.02',status='SELECTED',t_star=.9,n_accepted=1,k_errors=0,coverage={'num':1,'den':1})
    return ThresholdFile(schema='threshold/1',model='m',set='s',variant='full',run_id='r',
        rule='plan-4-2:dev_risk<=tau/2;max_coverage;tie_larger_t',unit='group_representative',
        dev_input={'path':'dev/final.jsonl','sha256':'a'*64,'nbytes':1,
                   'n_groups':1,'n_denom':1,'n_empty_mask':0},by_tau={'0.02':t})


def score():
    calibration = dict(ece=None,brier=None,log_loss=None,bins=[dict(index=i,lo=i/15,
        hi=(i+1)/15,n=0,acc=None,conf=None) for i in range(15)])
    q = QStats(role='success',type='choice',n_scored=0,n_missing=1,accuracy={'num':0,'den':0},
               macro_f1=None,classes={},calibration=calibration,warnings={'choice_not_argmax':0})
    pop = Population(certified=True,unit='group_representative',
        counts={'n_sampled':0,'by_status':{'ok':0,'rejected':0,'truncated':0,'error':0},'n_empty_mask':0},
        request={'n_scored':0,'wrong':{'num':0,'den':0}},questions={'aspect_1':q},pooled={'aspect':q},set_specific={})
    return ScoreTable(schema='scores/1',model='m',set='s',variant='full',run_id='r',
                      populations={'test':pop},cost={'by_stage':{'test':cost().to_dict()}})


def cost():
    return Cost(n_logical=0,n_calls=0,n_attempts=0,n_retries=0,failure={'num':0,'den':0},
        latency_ms={'population':'logical_ok','n':0,'p50':None,'p95':None,'n_excluded_resumed':0},
        input_tokens={'sum':0,'n_calls_missing_usage':0},derived_from=None)


def outcome():
    return RequestOutcome(logical_id='s:g:i',group_id='g',stage='test',status='ok',valid=True,
        mask_empty=False,s=.8,wrong=False,gold={'ready':'true'},answer={'ready':'true'},length_max=12,meta={})


def records():
    c, t, s = call(), threshold_file(), score()
    question = QuestionSpec(id='ready',role='success',type='noul',instructions='준비됐나요?',
                            label='ready',criteria={'true':'예','false':'아니오'})
    task = TaskSpec(set='s',variant='full',state={'kind':'plain_text'},questions=[question],
                    per_item_questions=None,group_key='source')
    return [task,question,item(),bound(),SourceRow(set='s',row_id='i',fields={'text':'등을 켰다.'}),
        SplitPlan(set='s',seed=20261012,pool_rule='all',allocation={},groups={'g':['i']},
                  representative={'g':'s:g:i'},dev=[],test=['g'],diagnostic_demotions=[],extra=[],notes={}),
        Rendered(state='등',target_end_char=1),c.length,*c.answers_parsed.values(),c,attempt(),
        Request(model='m',state='등',questions={}),
        FinalRecord(logical_id='s:g:i',status='ok',reason=None,answered_over_limit=False,warnings=[],calls=[c]),
        t,*t.by_tau.values(),s,*s.populations.values(),s.populations['test'].pooled['aspect'],cost(),outcome(),
        RiskCell(tau='0.02',status='NO_THRESHOLD',insufficient_by_design=True,unit='group_representative',
                 t_star=None,dev={},test={},by_status={},accepted_mix={},by_length_bucket={},diagnostic_error_in_accepted={})]
