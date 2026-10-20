"""Evidence screening, never an export clearance or an automatic legal opinion."""
import hashlib
import re
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup

SCOPES = {
    'RU_EXPORT': {'label':'Eksport do Rosji', 'regulation':'833/2014', 'celex':'02014R0833', 'annexes':['XXIII'], 'basis':'art. 3k ust. 1'},
    'BY_EXPORT': {'label':'Eksport do Białorusi', 'regulation':'765/2006', 'celex':'02006R0765', 'annexes':['XIV','XVIII'], 'basis':'art. 1s ust. 1; art. 1bb ust. 1'},
    'RU_TRANSIT': {'label':'Tranzyt przez Rosję', 'regulation':'833/2014', 'celex':'02014R0833', 'annexes':['XXXVII'], 'basis':'art. 3k ust. 1a'},
    'BY_TRANSIT': {'label':'Tranzyt przez Białoruś', 'regulation':'765/2006', 'celex':'02006R0765', 'annexes':['XIX'], 'basis':'art. 1bb ust. 2'},
}
GAPS = [
    'Aktualność i autentyczność wczytanych dokumentów oraz zmiany po dacie konsolidacji.',
    'Pozostałe zakazy towarowe i załączniki, w tym towary podwójnego zastosowania i wykazy techniczne.',
    'Zakres opisów, oznaczenia ex, progi wartości, wyjątki, okresy przejściowe i zezwolenia.',
    'Kontrahent, beneficjenci rzeczywiści, banki i przewoźnik — unijne i polskie listy sankcyjne.',
    'Polskie przepisy, zastosowanie końcowe, wywóz pośredni i ryzyko obejścia sankcji.',
    'Klasyfikacja i data każdej odrębnej partii oraz zgodność deklarowanej trasy z rzeczywistą.',
]

def clean_code(value):
    code = re.sub(r'\s+', '', value)
    if not re.fullmatch(r'(?:[0-9]{8}|[0-9]{10})', code):
        raise ValueError('Podaj kod CN (8 cyfr) albo TARIC (10 cyfr).')
    return code


def export_evidence(snapshot, country):
    """Only explicit export headings count. Import/unknown/groups remain visible separately."""
    relevant, other = [], []
    for item in snapshot['data']['nonTariffMeasures']:
        region = item.get('country', {}).get('code')
        title = item.get('description', '').lower()
        if region == country and ('wywo' in title or 'export' in title) and not ('przywo' in title or 'import' in title):
            relevant.append(item)
        else:
            other.append(item)
    return {'status': 'WPISY WYWOZOWE ISZTAR — SPRAWDŹ WARUNKI' if relevant else 'BRAK JEDNOZNACZNYCH WPISÓW WYWOZOWYCH — NIEZWERYFIKOWANE',
            'records': relevant, 'remaining_records': other,
            'note': 'Warunki dopuszczenia z API są możliwościami wymagającymi udokumentowania, a nie wynikiem weryfikacji.'}


def parse_annex_html(raw, source_url, regulation, annex):
    """Parse selected annex from a user-supplied EUR-Lex consolidated HTML.

    URL/content identity checks are structural, not authenticity/currentness verification.
    Unsupported rows are retained; a negative match never clears a shipment.
    """
    allowed = {('833/2014', 'XXIII'), ('833/2014', 'XXXVII'), ('765/2006', 'XIV'), ('765/2006', 'XVIII'), ('765/2006', 'XIX')}
    if (regulation, annex) not in allowed:
        raise ValueError('Ten akt lub załącznik nie jest obsługiwany w tej wersji modułu.')
    if len(raw) > 15_000_000:
        raise ValueError('Plik przekracza 15 MB.')
    parsed = urlparse(source_url.strip())
    if parsed.scheme != 'https' or parsed.hostname != 'eur-lex.europa.eu':
        raise ValueError('Podaj adres HTTPS tekstu skonsolidowanego w EUR-Lex.')
    expected = '02014R0833' if regulation == '833/2014' else '02006R0765'
    uri = parse_qs(parsed.query).get('uri', [''])[0]
    match = re.fullmatch(r'CELEX:('+expected+r')-([0-9]{8})', uri, re.I)
    if not match:
        raise ValueError('Użyj adresu z uri=CELEX:'+expected+'-RRRRMMDD, wskazującego konkretną wersję dokumentu.')
    version = datetime.strptime(match[2], '%Y%m%d').date().isoformat()
    soup = BeautifulSoup(raw, 'html.parser')
    document_text = soup.get_text(' ', strip=True)
    identity = expected+'-'+match[2]
    # PDF-style running headings also carry the instrument and version date.
    running_date = datetime.strptime(match[2], '%Y%m%d').strftime('%d.%m.%Y')
    if identity not in str(soup) and not (expected in document_text and running_date in document_text):
        raise ValueError('Treść pliku nie potwierdza numeru aktu i daty podanych w adresie źródła.')
    heading = re.compile(r'^(?:ANNEX|ZAŁĄCZNIK)\s+([IVXLCDM]+[A-Z]?)$', re.I)
    nodes = [n for n in soup.find_all(['p','h1','h2','h3','h4','table']) if not n.find_parent('table')]
    starts = [i for i,n in enumerate(nodes) if n.name != 'table' and (m:=heading.fullmatch(n.get_text(' ',strip=True))) and m[1].upper()==annex]
    if len(starts) != 1:
        raise ValueError('Nie znaleziono jednego jednoznacznego nagłówka załącznika '+annex+'. Wgraj HTML pełnego tekstu, bez spisu treści.')
    rows, skipped, notes = [], [], []
    for node in nodes[starts[0]+1:]:
        text = node.get_text(' ',strip=True)
        if node.name != 'table':
            if heading.fullmatch(text):
                break
            if text:
                notes.append(text)
            continue
        for tr in node.find_all('tr'):
            cells = tr.find_all(['td','th'],recursive=False)
            if len(cells) < 2:
                if tr.get_text(' ',strip=True): skipped.append(tr.get_text(' ',strip=True))
                continue
            label = cells[0].get_text(' ',strip=True)
            description = ' | '.join(c.get_text(' ',strip=True) for c in cells[1:])
            normalized = re.sub(r'\s+', '', label).lower()
            m = re.fullmatch(r'(ex)?([0-9]{2}|[0-9]{4}|[0-9]{6}|[0-9]{8})',normalized)
            if m:
                rows.append({'code':m[2], 'ex': bool(m[1]), 'label':label,'description':description})
            elif normalized not in ('cncode','kodcn','kodhs','hscode','code','kod'):
                skipped.append(label+' | '+description)
    if not rows:
        raise ValueError('Nie odczytano tabeli kodów CN w wybranym załączniku. Nie można wykonać porównania.')
    return {'regulation':regulation,'annex':annex,'version_date':version,'source_url':source_url.strip(),
            'sha256':hashlib.sha256(raw).hexdigest(),'loaded_at':datetime.now(timezone.utc).isoformat(),
            'provenance':'Plik dostarczony przez użytkownika; autentyczność i aktualność niepotwierdzone automatycznie',
            'rows':rows,'unparsed_rows':skipped,'notes':notes}


def screen(code, on_date, documents, snapshot=None):
    code = clean_code(code)
    date.fromisoformat(on_date)
    cases = []
    for key, spec in SCOPES.items():
        case = {'key':key, 'label':spec['label'],'basis':spec['basis'],'regulation':spec['regulation'], 'annex_checks':[]}
        for annex in spec['annexes']:
            doc = documents.get(spec['regulation']+':'+annex)
            result = {'annex':annex,'status':'BRAK DOKUMENTU — NIEZWERYFIKOWANE','matches':[]}
            if doc:
                result['document']={k:v for k,v in doc.items() if k != 'rows'}
                if doc['regulation'] != spec['regulation'] or doc['annex'] != annex:
                    result['status']='NIEZGODNY DOKUMENT — NIEZWERYFIKOWANE'
                elif doc['version_date'] > on_date:
                    result['status']='DOKUMENT PÓŹNIEJSZY NIŻ DATA ANALIZY — NIEZWERYFIKOWANE'
                else:
                    result['matches']=[row for row in doc['rows'] if code.startswith(row['code'])]
                    result['parsed_rows_count']=len(doc['rows'])
                    if result['matches']:
                        result['status']='DOPASOWANIE KODU — WYMAGA OCENY ZAKRESU I WYJĄTKÓW'
                    else:
                        result['status']='BRAK DOPASOWANIA W ODCZYTANYCH WIERSZACH — NIE OZNACZA ZGODY'
            case['annex_checks'].append(result)
        if key.endswith('EXPORT') and snapshot and snapshot['code'][:8] == code[:8]:
            # CN siblings may have different TARIC measures: only an exact code can supply evidence.
            if snapshot['code']==code and snapshot['date']==on_date:
                case['isztar']=export_evidence(snapshot,key[:2])
                case['isztar_source']={k:snapshot[k] for k in ['code','date','fetched_at','source']}
        case['status']='WYMAGA WERYFIKACJI — NIE WYDANO ZGODY'
        cases.append(case)
    return {'schema_version':1,'code':code,'date':on_date,'created_at':datetime.now(timezone.utc).isoformat(),
            'status':'ANALIZA CZĘŚCIOWA — BRAK OCENY DOPUSZCZALNOŚCI','cases':cases,'gaps':GAPS,
            'scope':'Porównanie wybranych załączników przemysłowych i odczyt wpisów wywozowych ISZTAR. Nie jest to pełna kontrola sankcyjna.'}


def shipment_coverage(shipments, screening):
    """A code/date match is coverage by the partial screen, never legal clearance."""
    coverage = []
    for part in shipments:
        same = bool(screening and part.get('code') == screening['code'] and part['date'] == screening['date'])
        coverage.append({'part_number': part['number'], 'code': part.get('code', ''), 'date': part['date'],
                         'status': 'ZGODNY KOD I DATA Z KONTROLĄ CZĘŚCIOWĄ — WYMAGA WERYFIKACJI' if same else 'BRAK KONTROLI DLA KODU I DATY TEJ PARTII'})
    return coverage
