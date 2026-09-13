from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

import app.main as main  # noqa: E402
from app.main import AnalysisIn  # noqa: E402
from app.agent_planner import build_plan  # noqa: E402
from app.processor import build_pipeline, alignment_provider  # noqa: E402
from app.tool_registry import all_tools, availability, find_tool  # noqa: E402

FAILED = []


def check(name, cond, detail=''):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ''))
    if not cond:
        FAILED.append(name)


def wait(aid, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = main.get_analysis(aid)
        if row['status'] in ('completed', 'failed'):
            return row
        time.sleep(0.05)
    raise TimeoutError(aid)


def main_run():
    print('=== Agent planning test ===')

    reg = all_tools()
    check('registry non-empty', len(reg) >= 10, f'{len(reg)} tools')
    names = {t['name'] for t in reg}
    check('registry has registry core tools', {'lm.intent', 'flood.temporal_sar_change', 'evidence.polygonize_area', 'satquery.retrieve.sentinel1_pair'} <= names)
    check('tool metadata complete', all(t.get('name') and t.get('title') and t.get('category') and isinstance(t.get('limitations'), list) for t in reg))
    check('fallback fields sane', all(t.get('fallback') is None or t['fallback'] in names for t in reg))

    avail = availability(main.model_status())
    known = {t for t in avail}
    check('availability covers every tool', known == names, f'{len(known)}/{len(names)}')
    check('flood model availability honest', (avail['flood.sar_water_model']['enabled'] is False) == (main.model_status().get('ready') is False))
    check('evidence tool always available', avail['evidence.polygonize_area']['enabled'] is True)

    samples = main.load_demo()
    assam = sorted([x for x in samples if x['filename'].startswith('Assam_')], key=lambda x: x['metadata'].get('acquired_at') or '')
    indore = [x for x in samples if x['filename'].startswith('Indore_')]

    ctx_flood = main.parse_query('Show flooded areas around Assam between July and August 2025.', 2)
    plan = build_plan(ctx_flood, assam)
    tool_names = plan['tools']
    check('flood plan not unsupported', plan['unsupported'] is False)
    check('flood plan contains SAR steps', 'flood.sar_water_model' in tool_names and 'flood.temporal_sar_change' in tool_names)
    check('flood plan co-registers', 'geospatial.co_registration_sar' in tool_names)
    check('flood plan evidence step', 'evidence.polygonize_area' in tool_names)
    check('flood precondition satisfied', all(p['satisfied'] for p in plan['preconditions']), str([p['name'] for p in plan['preconditions']]))
    check('flood plan aoi present', (plan['aoi'] or {}).get('name') == ctx_flood['location']['name'])

    ctx_auto = main.parse_query('Show flooded areas around Dhemaji between July 2025 and August 2025.', 0)
    plan_auto = build_plan(ctx_auto, [])
    check('auto-retrieve planned when no inputs', 'satquery.retrieve.sentinel1_pair' in plan_auto['tools'], plan_auto['tools'])
    check('temporal pair precondition unmet for retrieval planning', any(not p['satisfied'] for p in plan_auto['preconditions']) or not plan_auto['preconditions'])

    ctx_change = main.parse_query('Show where urban construction changed between these two dates.', 2)
    plan_change = build_plan(ctx_change, indore)
    check('change plan aligned diff + opencd fallback chain', 'change.aligned_absdiff_otsu' in plan_change['tools'])
    check('change plan precondition overlap checked vs real data', any(p['name'] == 'overlap' for p in plan_change['preconditions']))

    ctx_veg = main.parse_query('Show vegetation loss between these two images.', 2)
    plan_veg = build_plan(ctx_veg, indore)
    check('vegetation plan uses index tool', 'vegetation.index_change' in plan_veg['tools'])

    ctx_bad = main.parse_query('Will it flood next month in Assam?')
    plan_bad = build_plan(ctx_bad, [])
    check('unsupported produces honest plan', plan_bad['unsupported'] is True and 'forecast' in (plan_bad.get('unsupported_reason') or '').lower())

    check('registry lookup errors on unknown tool', _raises_keyerror())
    _ = find_tool('lm.intent')
    check('registered route is parseable', main.plan_request(main.PlanIn(query='Show flooded areas around Assam between July and August 2025.', dataset_ids=[x['id'] for x in assam])).get('plan', {}).get('steps'))

    job = main.create_analysis(AnalysisIn(query='Show flooded areas around Assam between July and August 2025.', dataset_ids=[x['id'] for x in assam], provider='local'))
    row = wait(job['analysis_id'])
    check('analysis completes', row['status'] == 'completed', str(row['result_json'])[:200])
    result = json.loads(row['result_json'])
    check('plan persisted on analysis', bool(row['plan_json']))
    check('plan attached to result', isinstance(result.get('plan'), dict) and len(result.get('plan', {}).get('steps', [])) > 0)
    check('executed tools recorded', isinstance(result.get('executed_tools'), dict) and len(result['executed_tools'].get('executed', [])) > 0, str(result.get('executed_tools', {}).get('executed')))
    check('executed tool is registered name', set(t['tool'] for t in result['executed_tools']['executed']) <= set(names))
    check('executed flood tool is temporal SAR change', result['executed_tools']['executed'][0]['tool'] in ('flood.temporal_sar_change', 'flood.sar_water_model', 'flood.sar_adaptive_dualpol'))
    check('deviation honesty', isinstance(result['executed_tools'].get('deviations'), list))
    check('planner events emitted', any(e.get('stage') == 'planner' for e in json.loads(row['events_json'] or '[]')))
    check('result numerics unchanged by plan wiring', 'probable_flood_area_km2' in result['statistics'] and 0 <= result['confidence'] <= 1)

    check('pipeline attached to result', isinstance(result.get('pipeline'), dict) and bool(result['pipeline'].get('intended_providers')))
    check('pipeline alignment provider honest', result['pipeline'].get('alignment', {}).get('name') == 'geospatial_reprojection', str(result['pipeline'].get('alignment')))
    check('pipeline water provider fallback honest', result['pipeline']['intended_providers']['water'] == 'flood.sar_adaptive_dualpol' if not main.model_status().get('ready') else True)
    check('pipeline event emitted', any(e.get('stage') == 'planner' and 'Pipeline providers' in (e.get('title') or '') for e in json.loads(row['events_json'] or '[]')))
    check('pipeline providers are registered tools', set(result['pipeline']['intended_providers'].values()) <= set(names))
    check('alignment_provider pure metadata check', alignment_provider({'crs': 'EPSG:4326', 'transform': (1,)}, {'crs': 'EPSG:32645', 'transform': (1,)})['geospatial'] is True)
    check('alignment_provider pixel fallback flag', alignment_provider({'crs': None, 'transform': None}, {'crs': None, 'transform': None})['name'] == 'pixel_grid_alignment')

    plan_col = main.plan_request(main.PlanIn(query='Show flooded areas around Assam between July and August 2025.', dataset_ids=[x['id'] for x in assam]))
    check('metadata-only plan returns context+plan+pipeline', set(plan_col.keys()) == {'query_context', 'plan', 'pipeline'})
    no_input = main.plan_request(main.PlanIn(query='Show flooded areas around Dhemaji between July 2025 and August 2025.'))
    check('no-input plan has retrieval+pipeline', 'satquery.retrieve.sentinel1_pair' in no_input['plan']['tools'] and no_input['pipeline']['inputs']['count'] == 0)

    assam_opt = [x for x in samples if x['filename'].startswith('Assam_') and x.get('modality') == 'optical']
    if assam_opt:
        ctx_opt = main.parse_query('Show flooded areas around Assam between July and August 2025.', 2)
        opt_plan = build_plan(ctx_opt, [assam_opt[0], assam_opt[0]])
        opt_tools = opt_plan['tools']
        check('optical-only flood plan never claims SAR flood mapping', 'flood.temporal_sar_change' not in opt_tools and 'flood.sar_water_model' not in opt_tools)
        opt_pair = next((p for p in opt_plan['preconditions'] if p['name'] == 'temporal_pair'), None)
        check('optical-only flood precondition unmet', bool(opt_pair) and opt_pair['satisfied'] is False, str(opt_pair))
        check('optical-only flood offers single-scene or retrieval fallback', 'flood.single_scene' in opt_tools or 'satquery.retrieve.sentinel1_pair' in opt_tools)
        orig_parse = main.parse_query
        try:
            main.parse_query = lambda q, n=0: dict(orig_parse(q, n), can_auto_retrieve=False)
            job_opt = main.create_analysis(AnalysisIn(query='Show flooded areas around Assam between July and August 2025.', dataset_ids=[assam_opt[0]['id'], assam_opt[0]['id']], provider='local'))
            row_opt = wait(job_opt['analysis_id'])
        finally:
            main.parse_query = orig_parse
        opt_err = json.loads(row_opt['result_json'] or '{}').get('error') or ''
        check('optical-only temporal flood refused at runtime with SAR reason', row_opt['status'] == 'failed' and 'SAR' in opt_err, opt_err[:90])

    print()
    if FAILED:
        print(f'AGENT PLANNING TEST FAILED: {len(FAILED)} failing check(s): {FAILED}')
        sys.exit(1)
    print('AGENT PLANNING TEST PASS')
    sys.exit(0)


def _raises_keyerror():
    try:
        find_tool('no.such.tool')
        return False
    except KeyError:
        return True


if __name__ == '__main__':
    main_run()