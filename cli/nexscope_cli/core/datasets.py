# Copyright 2026 Nexscope
# SPDX-License-Identifier: Apache-2.0
"""Validate user-owned UTF-8 data without accessing credentials or the network."""
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000
FIELDS = (
    'product_id', 'title', 'marketplace', 'price', 'currency', 'rating',
    'rating_scale', 'review_count', 'source_url', 'observed_at',
)


class DatasetError(ValueError):
    def __init__(self, issues):
        super().__init__('Input validation failed; no rows were silently discarded.')
        self.issues = issues


def safe_url(value):
    try:
        url = urlsplit(value)
        return (url.scheme in ('https', 'http') and bool(url.hostname)
                and not url.username and not url.password
                and not any(c.isspace() or ord(c) < 32 for c in value))
    except ValueError:
        return False


def read_dataset(filename):
    path = Path(filename)
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise DatasetError([{'row': 0, 'field': 'file', 'message': 'Maximum input size is 10 MiB; split the file.'}])
    try:
        text = raw.decode('utf-8-sig')
        if path.suffix.lower() == '.csv':
            reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)) or not {'product_id', 'title'} <= set(headers):
                raise ValueError('CSV needs unique headers including product_id and title.')
            rows = []
            for row in reader:
                if len(rows) >= MAX_ROWS:
                    raise ValueError('Maximum input is 10000 products; split the file.')
                rows.append(row)
        elif path.suffix.lower() == '.json':
            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('Duplicate JSON object key.')
                    result[key] = value
                return result
            def invalid_constant(value):
                raise ValueError('Non-finite JSON numbers are not supported.')
            rows = json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid_constant)
            if not isinstance(rows, list):
                raise ValueError('JSON must be an array of product objects.')
        else:
            raise ValueError('Use a .csv or .json file.')
    except (UnicodeError, ValueError, csv.Error) as error:
        raise DatasetError([{'row': 0, 'field': 'file', 'message': str(error)}]) from None
    if not rows or len(rows) > MAX_ROWS:
        raise DatasetError([{'row': 0, 'field': 'file', 'message': 'Provide 1 to 10000 products; no account is required.'}])
    issues, products, seen = [], [], set()
    for index, row in enumerate(rows, 1):
        # CSV row is a logical record number, with its header counted as row 1.
        row_number = index + (path.suffix.lower() == '.csv')
        def issue(field, message):
            issues.append({'row': row_number, 'field': field, 'message': message})
        if not isinstance(row, dict):
            issue('record', 'Expected a product object.')
            continue
        if None in row:
            issue('record', 'CSV record has more values than headers.')
        product = {}
        for field in FIELDS:
            value = row.get(field)
            if value is None or value == '':
                product[field] = None
            elif field in ('price', 'rating', 'rating_scale', 'review_count'):
                try:
                    if isinstance(value, bool):
                        raise InvalidOperation
                    number = Decimal(str(value).strip())
                    if not number.is_finite() or number < 0:
                        raise InvalidOperation
                    if field == 'rating_scale' and number == 0:
                        raise InvalidOperation
                    if field == 'review_count' and number != number.to_integral_value():
                        raise InvalidOperation
                    product[field] = str(number.normalize()) if field == 'rating_scale' else str(number)
                except (InvalidOperation, ValueError):
                    product[field] = None
                    issue(field, 'Expected a finite non-negative number, positive scale, or integer count as applicable.')
            elif not isinstance(value, str):
                product[field] = None
                issue(field, 'Expected a string; identifiers must remain strings.')
            else:
                product[field] = value.strip() or None
        for field in ('product_id', 'title'):
            if not product[field]:
                issue(field, 'Required non-empty string.')
        identity = (product['marketplace'], product['product_id'])
        if product['product_id'] and identity in seen:
            issue('product_id', 'Duplicate identifier within this marketplace.')
        seen.add(identity)
        if product['price'] is not None and not product['currency']:
            issue('currency', 'Required when price is supplied.')
        if product['currency'] and not re.fullmatch(r'[A-Z]{3}', product['currency']):
            issue('currency', 'Use a three-letter uppercase currency code.')
        if product['rating'] is not None:
            if product['rating_scale'] is None:
                issue('rating_scale', 'Required when rating is supplied.')
            elif Decimal(product['rating']) > Decimal(product['rating_scale']):
                issue('rating', 'Rating exceeds its scale.')
        if product['source_url'] and not safe_url(product['source_url']):
            issue('source_url', 'Use an HTTP(S) URL without credentials or whitespace.')
        if product['observed_at']:
            try:
                moment = datetime.fromisoformat(product['observed_at'].replace('Z', '+00:00'))
                if moment.tzinfo is None:
                    raise ValueError
            except ValueError:
                issue('observed_at', 'Use an ISO 8601 timestamp with a timezone.')
        product['source_row'] = row_number
        product['extra'] = {k: v for k, v in row.items() if k is not None and k not in FIELDS}
        products.append(product)
    if issues:
        raise DatasetError(issues)
    return {
        'schemaVersion': 1, 'sourceType': 'user_import',
        'inputName': path.name, 'inputSha256': hashlib.sha256(raw).hexdigest(),
        'importedAt': datetime.now(timezone.utc).isoformat(), 'products': products,
    }, raw
