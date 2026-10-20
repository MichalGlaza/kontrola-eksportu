import copy
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from isztar import SourceError
from research_ui import measures, render_measure
from sanctions import clean_code, parse_annex_html, screen


def render():
    st.title('Sankcje i tranzyt')
    st.warning('Kontrola częściowa. Moduł pokazuje dowody i dopasowania kodów; nie wydaje zgody na wysyłkę. Tranzyt jest oceniany oddzielnie od eksportu.')
    st.caption('Zakres tabel CN: Rosja — XXIII (eksport), XXXVII (tranzyt); Białoruś — XIV i XVIII (eksport), XIX (tranzyt). Pozostałe wykazy, kryteria techniczne i sankcje osobowe wymagają dodatkowej kontroli.')
    seed = st.session_state.get('card_source') or {}
    code = st.text_input('Kod do kontroli sankcyjnej (CN / TARIC)', value=seed.get('code',''), key='sanction_code')
    today = datetime.now(ZoneInfo('Europe/Warsaw')).date()
    on_date = st.date_input('Data analizy sankcyjnej', value=today, max_value=today, key='sanction_date')
    st.caption('Analiza dotyczy jednego kodu i daty. Dla innych kodów partii lub innych dat odpraw wykonaj osobne sprawdzenia.')
    docs = st.session_state.setdefault('sanction_documents', {})
    with st.expander('Dokumenty EUR-Lex — wczytaj załączniki do kontroli tranzytu i eksportu'):
        st.caption('Importer HTML jest w fazie testowej. Nie potwierdzono jeszcze poprawności odczytu rzeczywistego pliku EUR-Lex; porównaj podgląd z dokumentem źródłowym.')
        st.write('Automatyczne pobranie pełnych tekstów EUR-Lex nie jest obecnie dostępne. Otwórz akt, wybierz właściwy tekst skonsolidowany i zapisz jego wersję HTML. Wczytaj plik oraz wklej adres tej wersji zawierający CELEX i datę. Nie wgrywaj PDF ani strony spisu treści.')
        st.link_button('EUR-Lex — 833/2014', 'https://eur-lex.europa.eu/eli/reg/2014/833')
        st.link_button('EUR-Lex — 765/2006', 'https://eur-lex.europa.eu/eli/reg/2006/765')
        st.info('Pliki pozostają w sesji. Numer i data są sprawdzane w treści; nie potwierdza to autentyczności ani kompletności dokumentu. Po imporcie przejrzyj odczytane i pominięte wiersze.')
        reg = st.selectbox('Rozporządzenie dokumentu', ['833/2014','765/2006'])
        annex = st.selectbox('Załącznik do odczytu', ['XXIII','XXXVII'] if reg=='833/2014' else ['XIV','XVIII','XIX'])
        url = st.text_input('Adres konkretnej wersji EUR-Lex', placeholder='https://eur-lex.europa.eu/legal-content/PL/TXT/HTML/?uri=CELEX:02014R0833-RRRRMMDD')
        uploaded = st.file_uploader('HTML tekstu skonsolidowanego (do 15 MB)', type=['html','htm'])
        if st.button('Wczytaj wybrany załącznik'):
            try:
                if not uploaded:
                    raise ValueError('Wybierz plik HTML.')
                doc = parse_annex_html(uploaded.getvalue(), url, reg, annex)
                docs[reg+':'+annex] = doc
                st.session_state.pop('sanction_result', None)
                st.success(f"Odczytano {len(doc['rows'])} wierszy. Wersja dokumentu: {doc['version_date']}.")
            except ValueError as exc:
                st.error(str(exc))
        if docs:
            for name, doc in list(docs.items()):
                st.write(f"{name} · wersja {doc['version_date']} · {len(doc['rows'])} odczytanych wierszy · {len(doc['unparsed_rows'])} nieprzetworzonych")
                st.dataframe(doc['rows'], hide_index=True)
                if doc['unparsed_rows']:
                    st.warning('Nieprzetworzone wiersze: wynik porównania może być niepełny.')
                    st.text('\n'.join(doc['unparsed_rows']))
                if st.button('Usuń '+name, key='remove_'+name):
                    del docs[name]
                    st.session_state.pop('sanction_result', None)
                    st.rerun()
    fingerprint = hashlib.sha256(json.dumps({k:[v['sha256'],v['version_date'],v['source_url']] for k,v in docs.items()},sort_keys=True).encode()).hexdigest()
    key=(code.strip(),on_date.isoformat(),fingerprint)
    if st.button('Sprawdź eksport i tranzyt', type='primary'):
        st.session_state.pop('sanction_result', None)
        try:
            normalized = clean_code(code)
            source = None
            fetch_error = None
            if len(normalized)==10:
                try:
                    with st.spinner('Pobieram wpisy ISZTAR dla wskazanego kodu i daty…'):
                        source = measures(normalized,on_date.isoformat())
                except (SourceError, ValueError) as exc:
                    fetch_error = str(exc)
            else:
                fetch_error='Dla 8-cyfrowego CN porównano wyłącznie wczytane załączniki. ISZTAR wymaga wybranego kodu końcowego TARIC (10 cyfr).'
            result=screen(normalized,on_date.isoformat(),docs,source)
            result['isztar_error']=fetch_error
            result['input_key']=key
            st.session_state['sanction_result']=result
        except ValueError as exc:
            st.error(str(exc))
    result=st.session_state.get('sanction_result')
    if not result or tuple(result['input_key']) != key:
        if result:
            st.info('Zmieniono dane. Uruchom kontrolę ponownie.')
        return
    st.subheader(result['status'])
    st.caption(f"Kod: {result['code']} · data analizy: {result['date']} · wykonano: {result['created_at']}")
    st.dataframe([{'Obszar':case['label'],
                   'Wpisy wywozowe ISZTAR':str(len(case.get('isztar',{}).get('records',[]))) if case.get('isztar') else 'Nie wykonano / nie dotyczy',
                   'Dopasowania w załącznikach':sum(len(c['matches']) for c in case['annex_checks']),
                   'Brakujące dokumenty':sum('BRAK DOKUMENTU' in c['status'] for c in case['annex_checks']),
                   'Status':case['status']} for case in result['cases']], hide_index=True)
    if result['isztar_error']:
        st.error(result['isztar_error'])
    for case in result['cases']:
        st.subheader(case['label'])
        st.caption(f"Wybrany zakres: rozporządzenie {case['regulation']}, {case['basis']}. Aktualność podstawy i ewentualne wyjątki wymagają potwierdzenia.")
        evidence=case.get('isztar')
        if evidence:
            st.warning(evidence['status'])
            for i,item in enumerate(evidence['records'],1):
                with st.expander(f"{case['label']} — wpis ISZTAR {i}: {item.get('description','')}"):
                    render_measure(item)
            with st.expander(case['label']+' — pozostałe rekordy (w tym grupy krajów, import i niejednoznaczne kierunki)'):
                st.json(evidence['remaining_records'])
        for check in case['annex_checks']:
            st.warning(f"Załącznik {check['annex']}: {check['status']}")
            document=check.get('document')
            if document:
                st.caption(f"Wersja: {document['version_date']} · plik użytkownika · aktualność NIEPOTWIERDZONA · nieprzetworzone wiersze: {len(document['unparsed_rows'])}")
                if document['unparsed_rows']:
                    st.error('Tabela nie została w całości rozpoznana. Sprawdź nieprzetworzone wiersze w dokumentach.')
            if check['matches']:
                st.dataframe(check['matches'],hide_index=True)
                st.info('Dopasowano prefiks kodu. Dla pozycji „ex” należy dodatkowo sprawdzić opis i parametry towaru. Wyjątki i zezwolenia nie są automatycznie uznawane za spełnione.')
            if document:
                with st.expander(case['label']+' — źródło i uwagi załącznika '+check['annex']):
                    st.json(document)
    st.subheader('Pozostałe obowiązkowe obszary kontroli')
    for gap in result['gaps']:
        st.write('• '+gap)
    st.download_button('Pobierz wynik sankcji i tranzytu JSON',json.dumps(result,ensure_ascii=False,indent=2),'sankcje-tranzyt.json','application/json')
    if st.button('Dołącz ten wynik do karty analizy'):
        st.session_state['card_sanctions']=copy.deepcopy(result)
        st.success('Załączono wynik częściowy. Przejdź do karty i ponownie ją zatwierdź. Kod karty musi być identyczny; data wyniku pozostaje widoczna w raporcie.')
