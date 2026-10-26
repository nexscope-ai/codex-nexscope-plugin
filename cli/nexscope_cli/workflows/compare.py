# Copyright 2026 Nexscope
# SPDX-License-Identifier: Apache-2.0
"""A single task entry: plan, optional search, details, evidence and report."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ..capabilities.catalog import DOMAINS
from ..capabilities.plan import plan
from ..core.datasets import FIELDS, safe_url
from ..core.errors import Failure
from ..reports.compare import render_format
from ..reports.formats import FORMATS


def workflow_plan(*, asins=None, keyword=None, selected=None, market='amazon.com', max_calls=4, auth_mode='browser-account', api_base=None):
    if bool(asins) == bool(keyword):
        raise Failure('Provide exactly one of asins or keyword.')
    if market not in DOMAINS:
        raise Failure('Choose a supported Amazon marketplace.')
    if selected and not keyword:
        raise Failure('select-asins is only valid with keyword search.')
    if asins or selected:
        detail = plan('amazon-product-detail', {'asins': asins or selected, 'amazonDomain': market}, auth_mode=auth_mode, max_calls=max_calls, api_base=api_base)
        if len(detail['requests']) < 2:
            raise Failure('A comparison requires two or three distinct ASINs.')
    else:
        detail = None
    search = plan('amazon-search', {'keyword': keyword, 'amazonDomain': market}, auth_mode=auth_mode, max_calls=max_calls, api_base=api_base) if keyword else None
    maximum = (len(detail['requests']) if detail else 0) + (1 if search else 0)
    if maximum > max_calls:
        raise Failure('Search plus details exceeds max-calls; no requests were sent.')
    return {'schemaVersion': 'nexscope.comparison-plan.v1', 'status': 'PLANNED',
            'authMode': auth_mode, 'marketplace': market, 'asins': asins, 'keyword': keyword,
            'selectedAsins': selected, 'maximumRequests': maximum, 'maxCalls': max_calls,
            'estimatedCredits': None, 'billingCap': None, 'requestsSent': 0,
            'selectionPolicy': 'explicit-ASINs-only; otherwise return candidates',
            'steps': [item for item in (search, detail) if item], 'liveExecutionAvailable': False}


class Artifacts:
    def __init__(self, folder, execution_plan):
        self.root = Path(folder).resolve()
        # Preflight before any transport access. Never replace existing output.
        self.root.mkdir(mode=0o700)
        self.write('plan.json', execution_plan)

    def write(self, name, value):
        with (self.root / name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)

    def record(self, result):
        self.write('request-' + str(result['sequence']) + '.json', result)


def product(result, market):
    raw = result['response']['data']['products'][0]
    row = dict.fromkeys(FIELDS)
    row.update(product_id=raw['asin'], title=raw['title'], marketplace=market,
               price=raw.get('extractedPrice') if raw.get('currency') else None,
               currency=raw.get('currency'), rating=raw.get('rating') if raw.get('ratingScale') else None,
               rating_scale=raw.get('ratingScale'), review_count=raw.get('ratings', raw.get('reviews')))
    link = raw.get('asinUrl') or raw.get('linkClean') or raw.get('link')
    row['source_url'] = link if isinstance(link, str) and safe_url(link) else None
    row['source_row'] = 1
    row['extra'] = {'evidenceFile': 'request-' + str(result['sequence']) + '.json',
                    'sourcePointer': '/response/data/products/0', 'fetchedAt': result['fetchedAt'],
                    'cacheHit': result['cacheHit'], 'contractVersion': result['contractVersion'],
                    'missingFields': [field for field in FIELDS if row[field] is None]}
    return row


def compare(executor, folder, *, asins=None, keyword=None, selected=None, market='amazon.com', mock=False, format='html', allow_paid=False):
    if not mock and not allow_paid:
        raise Failure('LIVE_EXECUTION_UNAVAILABLE: remote execution requires explicit --allow-paid authorization.')
    source_type = 'mock' if mock else 'remote'
    if format not in (*FORMATS, 'all'):
        raise Failure('Choose html, csv, markdown or all.')
    execution_plan = workflow_plan(asins=asins, keyword=keyword, selected=selected, market=market,
                                   max_calls=executor.max_calls, auth_mode=executor.context.mode,
                                   api_base=executor.context.base if executor.context.mode == 'browser-account' else None)
    execution_plan['execution'] = {'sourceType': source_type, 'origin': executor.context.base, 'requestsSent': 0}
    execution_plan['liveExecutionAvailable'] = allow_paid and not mock
    execution_plan['reportFormat'] = format
    for step in execution_plan['steps']:
        step['auth'].update(origin=executor.context.base, originSource='fictional mock transport' if mock else 'selected authentication context')
    artifacts = Artifacts(folder, execution_plan)
    executor.record = artifacts.record
    chosen = asins or selected
    if keyword:
        search = executor.execute('amazon-search', {'keyword': keyword, 'amazonDomain': market})[0]
        candidates = search['response']['data']['products'] if search['status'] == 'SUCCESS' else []
        artifacts.write('candidates.json', candidates)
        available = {row['asin'] for row in candidates}
        if search['status'] != 'SUCCESS' or not chosen or not set(chosen.split(',')) <= available:
            status = 'CANDIDATES_READY' if search['status'] == 'SUCCESS' and not chosen else 'FAILED'
            result = {'status': status, 'sourceType': source_type, 'report': None,
                      'error': 'SELECTION_REQUIRED' if status == 'CANDIDATES_READY' else 'SEARCH_OR_SELECTION_FAILED',
                      'candidates': candidates, 'output': str(artifacts.root), 'budget': executor.summary()}
            artifacts.write('result.json', result)
            return result
    details = executor.execute('amazon-product-detail', {'asins': chosen, 'amazonDomain': market})
    rows = [product(result, market) for result in details if result['status'] == 'SUCCESS']
    for row in rows:
        evidence_file = artifacts.root / row['extra']['evidenceFile']
        row['extra']['evidenceSha256'] = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
    errors = [{'asin': result['params']['asins'], 'status': result['status'], 'error': result['error']}
              for result in details if result['status'] != 'SUCCESS']
    status = ('COMPLETE' if not errors else 'PARTIAL') if len(rows) >= 2 else 'INSUFFICIENT_DATA'
    digest = hashlib.sha256((artifacts.root / 'plan.json').read_bytes()).hexdigest()
    dataset = {'schemaVersion': 1, 'sourceType': source_type, 'inputName': 'plan.json', 'inputSha256': digest,
               'importedAt': datetime.now(timezone.utc).isoformat(), 'products': rows,
               'collectionStatus': status, 'errors': errors, 'budget': executor.summary()}
    artifacts.write('dataset.json', dataset)
    result = {'status': status, 'sourceType': source_type, 'requested': len(chosen.split(',')),
              'succeeded': len(rows), 'errors': errors, 'budget': executor.summary(),
              'output': str(artifacts.root), 'report': None, 'reports': {}, 'liveRequests': 0 if mock else executor.sent}
    if len(rows) >= 2:
        # Report beside its evidence; all links stay relative when sharing folder.
        for selected_format in FORMATS if format == 'all' else (format,):
            report = artifacts.root / ('comparison' + FORMATS[selected_format])
            with report.open('x', encoding='utf-8', newline='') as stream:
                stream.write(render_format(dataset, '.', selected_format))
            result['reports'][selected_format] = str(report)
        result['report'] = next(iter(result['reports'].values()))
        result['reportFormat'] = format
    artifacts.write('result.json', result)
    return result


def command(args):
    if args.mock and args.api_base is not None:
        raise Failure('Mock workflow uses a fictional origin only; omit --api-base.')
    execution_plan = workflow_plan(asins=args.asins, keyword=args.keyword, selected=args.select_asins,
                                   market=args.market, max_calls=args.max_calls, auth_mode=args.auth_mode, api_base=args.api_base)
    if args.dry_run:
        execution_plan['reportFormat'] = args.format
        return execution_plan
    if not args.mock and not args.allow_paid:
        raise Failure('LIVE_EXECUTION_UNAVAILABLE: --execute requires --mock or explicit --allow-paid.')
    if args.mock and args.allow_paid:
        raise Failure('Choose mock execution or paid execution, not both.')
    if not args.out:
        raise Failure('Choose a new output directory with --out.')
    from ..core.remote import engine_for
    engine = engine_for(args)
    return compare(engine, args.out, asins=args.asins, keyword=args.keyword,
                   selected=args.select_asins, market=args.market, mock=bool(args.mock), format=args.format, allow_paid=args.allow_paid)
