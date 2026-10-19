"""Read-only client for the documented public ISZTAR API. No legal verdicts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import re
import unicodedata
from urllib.parse import parse_qs, urlparse
import requests

BASE = 'https://ext-isztar4.mf.gov.pl/tariff/rest/goods-nomenclature/'
class SourceError(RuntimeError):
    pass

def request_json(endpoint, params):
    try:
        r = requests.get(BASE + endpoint, params=params, timeout=(8, 25), headers={'Accept': 'application/json'})
        if r.status_code != 200:
            try:
                reason = '; '.join(e.get('error-reason', '') for e in r.json().get('errors', []))
            except (ValueError, AttributeError, TypeError):
                reason = ''
            raise SourceError(f'ISZTAR: HTTP {r.status_code}. {reason}')
        data = r.json()
        if not isinstance(data, dict) or data.get('errors'):
            raise SourceError('ISZTAR zwrócił błąd lub nieznany format danych.')
        return data, r.url
    except (requests.RequestException, ValueError) as exc:
        raise SourceError('Nie udało się pobrać poprawnej odpowiedzi ISZTAR. Spróbuj później.') from exc

def validate_date(value):
    parsed = date.fromisoformat(value)
    if parsed > datetime.now(timezone.utc).date():
        raise ValueError('Wyszukiwanie obejmuje daty do dnia dzisiejszego. Przyszłą odprawę trzeba sprawdzić ponownie przed wysyłką.')
    return parsed.isoformat()

def flatten(node, parents=()):
    if not isinstance(node, dict) or not isinstance(node.get('description'), str):
        raise SourceError('Zmieniła się struktura nomenklatury ISZTAR.')
    path = parents + (node['description'],)
    children = node.get('subgroup', [])
    if not isinstance(children, list):
        raise SourceError('Nieprawidłowa struktura podgrup ISZTAR.')
    rows = []
    if node.get('code') and not children:
        code = str(node['code'])
        if not re.fullmatch(r'\d{10}', code):
            raise SourceError('Nieoczekiwany format kodu końcowego ISZTAR.')
        rows.append({'code': code, 'description': ' / '.join(path), 'leaf_description': node['description']})
    for child in children:
        rows.extend(flatten(child, path))
    return rows

def load_catalog(on_date, scope='machines'):
    on_date = validate_date(on_date)
    first_page = 16 if scope == 'machines' else 1
    first, source = request_json('codes', {'date': on_date, 'language': 'PL', 'page': first_page})
    pages = [first_page]
    documents = [first]
    if scope == 'all':
        last_url = first.get('links', {}).get('last', '')
        parsed = urlparse(last_url)
        if parsed.hostname != 'ext-isztar4.mf.gov.pl' or parsed.path != '/tariff/rest/goods-nomenclature/codes':
            raise SourceError('Nieprawidłowe odwołanie do kolejnych stron ISZTAR.')
        try:
            last = int(parse_qs(parsed.query)['page'][0])
        except (KeyError, ValueError, IndexError) as exc:
            raise SourceError('Brak informacji o kompletności nomenklatury.') from exc
        if not 1 <= last <= 50:
            raise SourceError('Nieoczekiwana liczba stron ISZTAR.')
        pages = list(range(1, last + 1))
        def fetch(page):
            return request_json('codes', {'date': on_date, 'language': 'PL', 'page': page})[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            documents.extend(pool.map(fetch, pages[1:]))
    elif scope != 'machines':
        raise ValueError('Nieznany zakres wyszukiwania.')
    rows = []
    for doc in documents:
        rows.extend(flatten(doc))
    if not rows:
        raise SourceError('Nie uzyskano kodów. Wynik nie jest kompletny.')
    unique = {row['code']: row for row in rows}
    return {'rows': list(unique.values()), 'date': on_date, 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'source': source, 'pages': pages, 'scope': scope, 'sections': [d['description'] for d in documents]}

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower().replace('ł', 'l')) if not unicodedata.combining(c))

def search_catalog(rows, query, limit=100):
    query = query.strip()
    compact = re.sub(r'\s+', '', query)
    if re.fullmatch(r'\d{2,10}', compact):
        found = [r for r in rows if r['code'].startswith(compact)]
    else:
        terms = [t for t in re.findall(r'[a-z0-9]+', normalize(query)) if len(t) >= 3]
        if not terms:
            raise ValueError('Wpisz kod (2–10 cyfr) lub słowo zawierające co najmniej 3 znaki.')
        # ALL supplied terms must match; ranking is deliberately not a classification score.
        found = [r for r in rows if all(t in normalize(r['description']) for t in terms)]
    return found[:limit], len(found)

def get_measures(code, on_date):
    on_date = validate_date(on_date)
    code = re.sub(r'\s+', '', code)
    if not re.fullmatch(r'\d{10}', code):
        raise ValueError('Wybierz pełny, 10-cyfrowy kod końcowy z ISZTAR.')
    data, url = request_json('measures', {'nomenclatureCode': code, 'date': on_date, 'language': 'PL'})
    if data.get('nomenclature', {}).get('code') != code or not isinstance(data.get('nonTariffMeasures'), list):
        raise SourceError('Odpowiedź nie potwierdza żądanego kodu lub listy środków.')
    return {'data': data, 'source': url, 'date': on_date, 'code': code,
            'fetched_at': datetime.now(timezone.utc).isoformat(), 'legal_assessment': 'NIEZWERYFIKOWANE'}

def group_measures(data):
    """Keep ALL non-tariff measures; never treat country groups as inapplicable."""
    groups = {'RU': [], 'BY': [], 'other': []}
    for measure in data['nonTariffMeasures']:
        code = measure.get('country', {}).get('code')
        groups[code if code in ('RU', 'BY') else 'other'].append(measure)
    return groups
