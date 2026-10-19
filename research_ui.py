import json
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import streamlit as st
from isztar import SourceError, load_catalog, search_catalog, get_measures, group_measures

@st.cache_data(ttl=3600, show_spinner=False)
def catalog(on_date, scope):
    return load_catalog(on_date, scope)

@st.cache_data(ttl=900, show_spinner=False)
def measures(code, on_date):
    return get_measures(code, on_date)

def render_measure(item):
    country = item.get('country', {})
    st.write(f"Obszar: {country.get('description', '')} ({country.get('code', '')})")
    if item.get('excludedCountries'):
        st.write('Wyłączone kraje:', item['excludedCountries'])
    regulation = item.get('regulation', {})
    st.write('Akt prawny wskazany przez ISZTAR:', regulation.get('abbreviation', 'brak'))
    url = regulation.get('link', '')
    if urlparse(url).hostname in ('eur-lex.europa.eu', 'isap.sejm.gov.pl'):
        st.link_button('Otwórz wskazany akt prawny', url.replace('http://', 'https://', 1))
    for footnote in item.get('footnotes', []):
        st.text(f"{footnote.get('code', '')}: {footnote.get('description', '')}")
    conditions = item.get('measureConditions', {})
    if conditions.get('conditions'):
        st.write('Warunki — wymagają sprawdzenia; nie są automatycznie spełnione:')
        st.dataframe(conditions['conditions'], hide_index=True)
    for info in conditions.get('additionalInformations', []):
        st.text(f"{info.get('code', '')}: {info.get('description', '')}")
    with st.expander('Pełny rekord źródłowy'):
        st.json(item)

def render():
    st.title('Wyszukiwanie kodów i środków ISZTAR')
    st.info('Dane z oficjalnego API Ministerstwa Finansów. Wyszukiwanie słów w taryfie pomaga znaleźć kandydatów, ale nie ustala wiążącej klasyfikacji na podstawie opisu.')
    st.warning('To odczyt ISZTAR, nie pełna kontrola sankcyjna. Tranzyt, aktualne treści załączników, polskie przepisy, kontrahent i zastosowanie końcowe pozostają NIEZWERYFIKOWANE.')
    today = datetime.now(ZoneInfo('Europe/Warsaw')).date()
    on_date = st.date_input('Stan danych na dzień', value=today, max_value=today, key='research_date')
    scope_label = st.selectbox('Zakres nomenklatury', ['Maszyny i sprzęt elektryczny — sekcja XVI', 'Cała nomenklatura'])
    scope = 'machines' if scope_label.startswith('Maszyny') else 'all'
    st.caption('Na początek wyszukaj „klimatyzator”. Słowa są szukane dosłownie w pełnej ścieżce opisu; wszystkie wpisane słowa muszą pasować. Możesz też wpisać początek kodu.')
    query = st.text_input('Słowa z opisu taryfowego lub kod', 'klimatyzator', key='tariff_query')
    key = (on_date.isoformat(), scope, query.strip())
    if st.button('Szukaj w ISZTAR', type='primary'):
        st.session_state.pop('tariff_results', None)
        st.session_state.pop('measure_result', None)
        try:
            with st.spinner('Pobieram nomenklaturę. Pełna baza wymaga pobrania wszystkich stron API…'):
                data = catalog(on_date.isoformat(), scope)
                rows, total = search_catalog(data['rows'], query)
            st.session_state['tariff_results'] = {'key': key, 'rows': rows, 'total': total,
                'metadata': {k: v for k, v in data.items() if k != 'rows'}}
        except (SourceError, ValueError) as exc:
            st.error(str(exc))
    result = st.session_state.get('tariff_results')
    if not result or tuple(result['key']) != key:
        if result:
            st.info('Zmieniono zapytanie, datę lub zakres. Uruchom wyszukiwanie ponownie.')
        return
    meta = result['metadata']
    st.caption(f"Data zapytania: {meta['date']} · pobrano: {meta['fetched_at']} · strony API: {meta['pages']}. Czas pobrania nie oznacza daty ostatniej aktualizacji bazy przez MF.")
    st.link_button('Źródło nomenklatury (API)', meta['source'])
    st.write(f"Znaleziono {result['total']} kodów końcowych. Pokazano {len(result['rows'])}.")
    if not result['rows']:
        st.info('Brak dopasowań w wybranym zakresie. Skróć słowo, użyj nazwy taryfowej lub wybierz całą nomenklaturę. Nie oznacza to braku kodu ani ograniczeń.')
        return
    st.dataframe([{'Kod TARIC': r['code'], 'Kod CN': r['code'][:8], 'Pełny opis': r['description']} for r in result['rows']], hide_index=True)
    selected = st.selectbox('Kod do odczytu środków — wybór roboczy', [r['code'] for r in result['rows']])
    row = next(r for r in result['rows'] if r['code'] == selected)
    st.write(row['description'])
    st.caption('Nie przypisuj kodu kompletnego urządzenia automatycznie każdej osobnej partii dostawy.')
    if st.button('Pobierz środki i ograniczenia dla tego kodu'):
        st.session_state.pop('measure_result', None)
        try:
            with st.spinner('Pobieram środki z ISZTAR…'):
                response = measures(selected, on_date.isoformat())
            response['search_key'] = key
            st.session_state['measure_result'] = response
        except (SourceError, ValueError) as exc:
            st.error(str(exc))
    response = st.session_state.get('measure_result')
    if not response or response['code'] != selected or response['date'] != on_date.isoformat() or tuple(response['search_key']) != key:
        return
    st.subheader('Środki pozataryfowe przypisane do kodu')
    st.caption(f"Pobrano: {response['fetched_at']} · stan na: {response['date']}")
    st.link_button('Źródłowa odpowiedź ISZTAR', response['source'])
    groups = group_measures(response['data'])
    for group, label in [('RU', 'Rosja'), ('BY', 'Białoruś'), ('other', 'Pozostałe kraje i grupy krajów — również wymagają przeglądu')]:
        st.subheader(label)
        if groups[group]:
            st.warning(f"ISZTAR zwrócił {len(groups[group])} rekordów. Sprawdź zakres, kierunek operacji, warunki i wyjątki.")
        else:
            st.info('Brak rekordów w tej grupie odpowiedzi. Nie potwierdza to dopuszczalności eksportu ani tranzytu.')
        for i, item in enumerate(groups[group], 1):
            with st.expander(f"{i}. {item.get('description', 'Środek')} / {item.get('country', {}).get('code', '')}"):
                render_measure(item)
    st.error('Tranzyt przez Rosję i Białoruś: NIEZWERYFIKOWANY. Zakaz eksportu nie jest automatycznie zakazem tranzytu; brak rekordu tranzytowego nie stanowi zgody.')
    st.download_button('Pobierz dane źródłowe i metrykę JSON', json.dumps(response, ensure_ascii=False, indent=2), f'isztar-{selected}-{on_date.isoformat()}.json', 'application/json')
    with st.expander('Pełna odpowiedź — także cła i podatki'):
        st.json(response['data'])
