"""무엇: 분할 fixture 검산 · 입력: 합성 행·묶음 · 출력: 검증 · 계약 §6·§9."""

from collections import defaultdict
import json
import random

from test_fixtures_wellformed import ROOT, read


def test_label_conflict_groups_use_ids():
    f = read(ROOT / 'splits/label_conflicts.json')
    grouped = defaultdict(list)
    for row in f['rows']:
        grouped[row['text']].append(row)
    groups = {min(rows,key=lambda r:int(r['row_id']))['row_id']:[r['row_id'] for r in rows]
              for rows in grouped.values()}
    conflicts = sum(len({r['gold'] for r in rows}) > 1 for rows in grouped.values())
    assert f['expected'] == {'groups':groups,'notes':{
        'label_conflict_groups_total':conflicts, 'label_conflict_groups_pool':conflicts}}
    assert not set(groups).intersection(grouped)


def test_union_find_components():
    f = read(ROOT / 'splits/union_find.json')
    rows = f['rows']
    component = {r['serial_num']:{r['serial_num']} for r in rows}
    for a in rows:
        for b in rows:
            same_text = a['input_messages'][0]['content'] == b['input_messages'][0]['content']
            same_tools = json.dumps(a['input_tools'],sort_keys=True,ensure_ascii=False) == json.dumps(b['input_tools'],sort_keys=True,ensure_ascii=False)
            if same_text or same_tools:
                merged = component[a['serial_num']] | component[b['serial_num']]
                for member in merged:
                    component[member] = merged
    groups = {str(min(v)):sorted(map(str, v)) for v in component.values()}
    assert groups == f['expected']['groups']
    assert len(groups) == f['expected']['group_count']


def test_pool_representatives_and_split():
    f = read(ROOT / 'splits/deterministic.json')
    prefix = f"{f['seed']}:{f['set']}"
    pool = random.Random(prefix+':pool').sample(sorted(f['groups']),f['cap'])
    assert pool == f['expected']['pool']
    reps = {g:f"{f['set']}:{g}:"+random.Random(prefix+':rep:'+g).choice(sorted(f['groups'][g])) for g in pool}
    assert reps == f['expected']['representative']
    shuffled = sorted(pool)
    random.Random(prefix+':split').shuffle(shuffled)
    boundary = len(shuffled)//5
    assert shuffled[:boundary] == f['expected']['dev']
    assert shuffled[boundary:] == f['expected']['test']


def allocation(counts, cap):
    total = sum(counts.values())
    result = {k:cap*n//total for k,n in counts.items()}
    order = sorted(counts,key=lambda k:(-(cap*counts[k]%total),k))
    for k in order[:cap-sum(result.values())]:
        result[k] += 1
    return result


def test_proportional_and_demotions():
    f = read(ROOT / 'splits/proportional.json')
    assigned = allocation({k:len(v) for k,v in f['strata'].items()},f['cap'])
    assert assigned == f['expected']['allocation']
    tie = f['tie_case']
    assert allocation(tie['stratum_counts'],tie['cap']) == tie['expected_allocation']
    for k,n in assigned.items():
        rng = random.Random(f"{f['seed']}:{f['set']}:pool:{k}")
        assert rng.sample(sorted(f['strata'][k]),n) == f['expected']['selected_by_stratum'][k]
    d = read(ROOT / 'splits/diagnostic_demotions.json')
    assert sorted(k for k,n in d['positive_counts'].items() if n < 50) == d['expected']['diagnostic_demotions']
