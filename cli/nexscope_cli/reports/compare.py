# Copyright 2026 Nexscope
# SPDX-License-Identifier: Apache-2.0
"""Self-contained HTML reports with input evidence alongside the report."""
from collections import defaultdict
from html import escape
from importlib.resources import files
import json
from pathlib import Path
import re
from string import Template
from urllib.parse import quote

from nexscope_cli.core.datasets import FIELDS, read_dataset
from .formats import FORMATS, render_csv, render_markdown


def resource(name):
    return files('nexscope_cli.resources').joinpath(name)


def display(value):
    if value is None or value == '':
        return 'Not provided'
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return escape(str(value))


def render(dataset, evidence_name):
    groups = defaultdict(list)
    for product in dataset['products']:
        groups[(product['marketplace'], product['currency'], product['rating_scale'])].append(product)
    sections = []
    for (market, currency, scale), products in groups.items():
        title = f'Market: {display(market)} | Currency: {display(currency)} | Rating scale: {display(scale)}'
        headers = ''.join(f'<th>{field}</th>' for field in (*FIELDS, 'source_row', 'extra'))
        rows = []
        for product in products:
            cells = []
            for field in (*FIELDS, 'source_row', 'extra'):
                value = product[field]
                content = display(value)
                if field == 'source_url' and value:
                    content = f'<a rel="noreferrer noopener" href="{escape(value, quote=True)}">{content}</a>'
                if field == 'extra' and dataset['sourceType'] in ('mock', 'remote'):
                    filename = value.get('evidenceFile', '')
                    if re.fullmatch(r'request-[0-9]+\.json', filename):
                        href = escape(quote(evidence_name) + '/' + filename, quote=True)
                        content = f'<a href="{href}">Request evidence</a><br>' + content
                cells.append(f'<td>{content}</td>')
            rows.append('<tr>' + ''.join(cells) + '</tr>')
        sections.append(f'<section><h2>{title}</h2><p>{len(products)} products</p><div class="scroll"><table><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')
    missing = sum(any(product[field] is None for field in FIELDS) for product in dataset['products'])
    notice = 'Source: user_import. Data was supplied by the user and has not been refreshed or independently verified. Bundled samples are fictional.'
    if dataset['sourceType'] in ('mock', 'remote'):
        notice = ('MOCK / FICTIONAL DATA: no live service was queried. This report tests the workflow; it is not market research.'
                  if dataset['sourceType'] == 'mock' else 'REMOTE DATA: retrieved at the recorded times; missing fields are not inferred. Review the request evidence and partial failures.')
        sections.insert(0, '<section><h2>Collection status: ' + display(dataset['collectionStatus']) + '</h2><p>Failed or skipped products: ' + display(dataset['errors']) + '</p><p>Request accounting: ' + display(dataset['budget']) + '</p></section>')
    return Template(resource('report.html').read_text(encoding='utf-8')).substitute(
        count=len(dataset['products']), missing=missing, groups=len(groups),
        imported=escape(dataset['importedAt']), digest=dataset['inputSha256'],
        evidence=escape(quote(evidence_name), quote=True), sections='\n'.join(sections),
        source_notice=escape(notice),
    )


def render_format(dataset, evidence_name, format='html'):
    if format == 'html':
        return render(dataset, evidence_name)
    if format == 'csv':
        return render_csv(dataset, evidence_name)
    if format == 'markdown':
        return render_markdown(dataset, evidence_name)
    raise ValueError('Choose html, csv or markdown.')


def compare(input_path, output_path, dry_run=False, format='html'):
    dataset, original = read_dataset(input_path)
    output = Path(output_path).resolve()
    evidence = output.with_name(output.name + '.evidence')
    if format not in FORMATS or output.suffix.lower() != FORMATS[format]:
        raise ValueError('Report format must match its .html, .csv or .md output suffix.')
    if dry_run:
        return {'status': 'PLAN_READY', 'rows': len(dataset['products']), 'networkCalls': 0,
                'output': str(output), 'evidence': str(evidence), 'sourceType': 'user_import', 'format': format}
    if output.exists() or evidence.exists():
        raise FileExistsError('Choose a new report path; report or evidence already exists.')
    # Exclusive creation prevents replacement of either the input or existing outputs.
    evidence.mkdir()
    created = []
    try:
        source = evidence / ('input' + Path(input_path).suffix.lower())
        with source.open('xb') as stream:
            created.append(source)
            stream.write(original)
        index = evidence / 'dataset.json'
        with index.open('x', encoding='utf-8') as stream:
            created.append(index)
            json.dump(dataset, stream, ensure_ascii=False, indent=2)
        with output.open('x', encoding='utf-8', newline='') as stream:
            created.append(output)
            stream.write(render_format(dataset, evidence.name, format))
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        evidence.rmdir()
        raise
    return {'status': 'REPORT_READY', 'rows': len(dataset['products']), 'networkCalls': 0,
            'file': str(output), 'evidence': str(evidence), 'sourceType': 'user_import', 'format': format}


def command(args):
    if args.report_action == 'compare':
        return compare(args.input, args.out, args.dry_run, args.format)
    if args.report_action == 'describe':
        name = 'products.schema.json' if args.schema else 'fields.json'
        return json.loads(resource(name).read_text(encoding='utf-8'))
    name = 'products-template.csv' if args.report_action == 'template' else 'products-sample.' + args.format
    with open(args.out, 'xb') as stream:
        stream.write(resource(name).read_bytes())
    return {'status': 'EXPORTED', 'file': str(Path(args.out).resolve()), 'networkCalls': 0}
