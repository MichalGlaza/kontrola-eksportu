import copy
import json
import re
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import streamlit as st
from card_export import report_html
from sanctions import shipment_coverage

def render():
    st.title("Karta analizy eksportu")
    st.warning("Karta robocza: odczyt ISZTAR nie potwierdza klasyfikacji ani dopuszczalności eksportu lub tranzytu.")
    source = st.session_state.get("card_source")
    if source:
        st.info(f"Załączony odczyt ISZTAR: {source['code']} · stan na {source['date']} · pobrano {source['fetched_at']}")
        if st.button("Usuń odczyt z karty"):
            st.session_state.pop("card_source", None)
            st.rerun()
    else:
        st.info("Możesz dołączyć odczyt przyciskiem w Wyszukiwarce ISZTAR po pobraniu środków.")
    st.caption("Eksport z Polski · Rosja i Białoruś · tranzyt przez oba kraje")
    sanctions = st.session_state.get('card_sanctions')
    if sanctions:
        st.info(f"Załączona kontrola częściowa sankcji: {sanctions['code']} · data {sanctions['date']}. Po zmianie kodu lub daty odprawy wykonaj nową kontrolę.")
        if st.button('Usuń wynik sankcji z karty'):
            st.session_state.pop('card_sanctions', None)
            st.rerun()
    count = st.number_input("Liczba odrębnych wysyłek / odpraw", min_value=1, max_value=50, value=1, step=1)
    with st.form("product_form"):
        st.subheader("1. Towar")
        name = st.text_input("Nazwa", "Centrala wentylacyjna do komory uprawowej", max_chars=300)
        materials = st.text_area("Materiały", "Miedź, aluminium. Pozostałe materiały do uzupełnienia.", max_chars=5000)
        purpose = st.text_area("Funkcja i wyposażenie", "Nawiew świeżego powietrza, ogrzewanie i chłodzenie. Wentylator z silnikiem, wymienniki, nagrzewnica i chłodnica.", max_chars=10000)
        left, right = st.columns(2)
        medium = left.text_input("Medium", "Glikol lub woda studzienna", max_chars=500)
        compressor = right.selectbox("Własna sprężarka", ["Nie", "Tak", "Nie ustalono"])
        code = st.text_input("Roboczy kod towaru — wymaga potwierdzenia", value=source["code"] if source else sanctions["code"] if sanctions else "", max_chars=20)
        rationale = st.text_area("Uzasadnienie wyboru kodu / brakujące cechy techniczne", max_chars=5000)
        st.subheader("2. Odbiorca i trasa")
        destination = st.text_input("Kraj docelowy", max_chars=200)
        route = st.text_input("Pełna trasa", placeholder="Polska → kraje tranzytu → kraj docelowy", max_chars=1000)
        enduse = st.text_area("Odbiorca i zastosowanie końcowe", max_chars=5000)
        st.subheader("3. Odrębne wysyłki")
        st.info("Każda partia jest odprawiana oddzielnie. Kod kompletnego urządzenia nie jest automatycznie przypisywany jego elementom.")
        parts = []
        for i in range(int(count)):
            st.markdown(f"**Partia {i + 1}**")
            shipment_date = st.date_input("Data odprawy", value=datetime.now(ZoneInfo("Europe/Warsaw")).date(), key=f"date_{i}")
            contents = st.text_area("Elementy faktycznie wysyłane", key=f"contents_{i}", max_chars=5000)
            part_code = st.text_input("Roboczy kod partii (opcjonalnie)", key=f"part_code_{i}", max_chars=10)
            parts.append({"number": i + 1, "date": shipment_date.isoformat(), "contents": contents.strip(), "code": part_code.strip(), "classification": "NIEZWERYFIKOWANE"})
        notes = st.text_area("Uwagi i dokumenty do uzyskania", max_chars=10000)
        author = st.text_input("Osoba przygotowująca (opcjonalnie)", max_chars=200)
        submitted = st.form_submit_button("Przygotuj kartę analizy", type="primary")
    
    if submitted:
        errors = []
        for label, value in [("nazwa", name), ("materiały", materials), ("funkcja", purpose), ("kraj docelowy", destination), ("trasa", route)]:
            if not value.strip():
                errors.append(f"Uzupełnij pole: {label}.")
        normalized_code = re.sub(r"\s+", "", code)
        if normalized_code and not re.fullmatch(r"(?:[0-9]{6}|[0-9]{8}|[0-9]{10})", normalized_code):
            errors.append("Kod musi zawierać 6, 8 lub 10 cyfr.")
        if source and normalized_code != source["code"]:
            errors.append("Kod karty różni się od załączonego odczytu ISZTAR. Usuń odczyt lub wybierz zgodny kod.")
        if sanctions and normalized_code != sanctions["code"]:
            errors.append("Kod karty różni się od załączonego wyniku sankcji. Usuń wynik lub wykonaj kontrolę właściwego kodu.")
        if any(p["code"] and not re.fullmatch(r"(?:[0-9]{6}|[0-9]{8}|[0-9]{10})", p["code"]) for p in parts):
            errors.append("Kod partii musi zawierać 6, 8 lub 10 cyfr.")
        if any(not p["contents"] for p in parts):
            errors.append("Opisz zawartość każdej partii.")
        if errors:
            st.session_state.pop("report", None)
            for message in errors:
                st.error(message)
        else:
            st.session_state["report"] = {
                "schema_version": 2,
                "id": str(uuid.uuid4()), "author": author.strip(), "notes": notes.strip(),
                "classification_rationale": rationale.strip(),
                "isztar_snapshot": copy.deepcopy(source),
                "sanctions_screening": copy.deepcopy(sanctions),
                "shipment_screening_coverage": shipment_coverage(parts, sanctions),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "product": {"name": name.strip(), "materials": materials.strip(), "purpose": purpose.strip(),
                            "medium": medium.strip(), "compressor": compressor, "user_code": normalized_code},
                "export": {"origin": "Polska", "destination": destination.strip(), "route": route.strip(), "enduse": enduse.strip()},
                "shipments": parts,
                "verification": {key: "NIEZWERYFIKOWANE" for key in ["Klasyfikacja", "Eksport do Rosji", "Eksport do Białorusi", "Tranzyt przez Rosję", "Tranzyt przez Białoruś", "Polskie przepisy i lista sankcyjna", "Kontrahent i beneficjent rzeczywisty", "Zastosowanie końcowe / podwójne zastosowanie"]},
                "sources_checked": [{"url": source["source"], "date": source["date"], "fetched_at": source["fetched_at"], "scope": "Odczyt API ISZTAR; bez analizy przepisów"}] if source else [],
            }
    if "report" in st.session_state:
        report = st.session_state["report"]
        st.subheader("Zapisana karta — ostatnie zatwierdzenie formularza")
        st.caption("Po zmianie pól ponownie kliknij „Przygotuj kartę analizy”. Poniższe pliki zawierają ostatnio zatwierdzone dane.")
        st.write(f"Numer karty: {report['id']}")
        st.subheader(report['product']['name'])
        st.write(f"Trasa: {report['export']['route']}")
        st.dataframe([{'Obszar': k, 'Status': v} for k, v in report['verification'].items()], hide_index=True)
        st.dataframe(report['shipments'], hide_index=True)
        if report.get('sanctions_screening'):
            st.subheader('Zakres kontroli sankcji dla partii')
            st.dataframe(report.get('shipment_screening_coverage', []), hide_index=True)
        st.warning('Każda odrębna odprawa wymaga oceny faktycznie wysyłanych elementów. Odczyt dla kodu urządzenia nie obejmuje automatycznie kodów wszystkich partii.')
        with st.expander('Pełna karta i załączone dane źródłowe'):
            st.json(report)
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        st.download_button('Pobierz kartę JSON', payload, 'karta-eksportu.json', 'application/json')
        st.download_button('Pobierz kartę do druku / PDF', report_html(report), 'karta-eksportu.html', 'text/html')
        st.caption('Otwórz pobrany plik HTML w przeglądarce. Drukuj → Zapisz jako PDF. Plik zawiera dane karty i odczyt ISZTAR.')
    st.caption("Dane są przechowywane wyłącznie w bieżącej sesji. Pobierz kartę przed zamknięciem. Nie ma jeszcze wspólnej bazy ani historii analiz.")
    
