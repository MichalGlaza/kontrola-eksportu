import hashlib
import hmac
import json
import re
import time
from datetime import date, datetime, timezone
import streamlit as st

st.set_page_config(page_title="Kontrola eksportu", page_icon="📦", layout="wide")

def password_config():
    try:
        value = st.secrets.get("APP_PASSWORD", "")
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ""
    return value if isinstance(value, str) else ""

def authenticate():
    expected = password_config()
    if len(expected) < 16 or expected == "WSTAW_TUTAJ_WLASNE_DLUGIE_HASLO":
        st.error("Administrator musi ustawić APP_PASSWORD (minimum 16 znaków) w ustawieniach Secrets aplikacji.")
        st.stop()
    marker = hashlib.sha256(expected.encode()).hexdigest()
    if st.session_state.get("auth_marker") == marker:
        return
    st.title("Kontrola eksportu")
    st.caption("Dostęp zespołu — wspólne hasło")
    with st.form("login"):
        entered = st.text_input("Hasło", type="password", key="entered_password")
        submitted = st.form_submit_button("Wejdź")
    if submitted:
        if time.time() < st.session_state.get("retry_after", 0):
            st.error("Odczekaj chwilę przed kolejną próbą.")
        elif hmac.compare_digest(entered.encode(), expected.encode()):
            st.session_state["auth_marker"] = marker
            st.session_state.pop("entered_password", None)
            st.rerun()
        else:
            st.session_state["retry_after"] = time.time() + 3
            st.error("Nieprawidłowe hasło.")
    st.stop()

authenticate()
with st.sidebar:
    st.header("Kontrola eksportu")
    st.caption("Wersja 0.3 · ISZTAR + karta analizy")
    if st.button("Wyloguj"):
        st.session_state.clear()
        st.rerun()
    st.markdown("**Oficjalne źródła**")
    st.link_button("ISZTAR", "https://ext-isztar4.mf.gov.pl/taryfa_celna/Browser?lang=PL")
    st.link_button("Rosja — 833/2014", "https://eur-lex.europa.eu/eli/reg/2014/833")
    st.link_button("Białoruś — 765/2006", "https://eur-lex.europa.eu/eli/reg/2006/765")
    st.link_button("Polska lista sankcyjna", "https://www.gov.pl/web/mswia/lista-osob-i-podmiotow-objetych-sankcjami")
    st.caption("Linki służą do ręcznego sprawdzenia. Ich otwarcie nie zmienia statusu analizy.")

page = st.sidebar.radio("Moduł", ["Wyszukiwarka ISZTAR", "Karta analizy eksportu"])
if page == "Wyszukiwarka ISZTAR":
    from research_ui import render
    render()
    st.stop()

st.title("Karta analizy eksportu")
st.warning("Prototyp nie ustala kodu celnego i nie sprawdza sankcji. Wszystkie wyniki pozostają NIEZWERYFIKOWANE.")
st.caption("Eksport z Polski · Rosja i Białoruś · tranzyt przez oba kraje")
count = st.number_input("Liczba odrębnych wysyłek / odpraw", min_value=1, max_value=50, value=1, step=1)
with st.form("product_form"):
    st.subheader("1. Towar")
    name = st.text_input("Nazwa", "Centrala wentylacyjna do komory uprawowej", max_chars=300)
    materials = st.text_area("Materiały", "Miedź, aluminium. Pozostałe materiały do uzupełnienia.", max_chars=5000)
    purpose = st.text_area("Funkcja i wyposażenie", "Nawiew świeżego powietrza, ogrzewanie i chłodzenie. Wentylator z silnikiem, wymienniki, nagrzewnica i chłodnica.", max_chars=10000)
    left, right = st.columns(2)
    medium = left.text_input("Medium", "Glikol lub woda studzienna", max_chars=500)
    compressor = right.selectbox("Własna sprężarka", ["Nie", "Tak", "Nie ustalono"])
    code = st.text_input("Posiadany kod — opcjonalnie, niezweryfikowany", max_chars=20)
    st.subheader("2. Odbiorca i trasa")
    destination = st.text_input("Kraj docelowy", max_chars=200)
    route = st.text_input("Pełna trasa", placeholder="Polska → kraje tranzytu → kraj docelowy", max_chars=1000)
    enduse = st.text_area("Odbiorca i zastosowanie końcowe", max_chars=5000)
    st.subheader("3. Odrębne wysyłki")
    st.info("Każda partia jest odprawiana oddzielnie. Kod kompletnego urządzenia nie jest automatycznie przypisywany jego elementom.")
    parts = []
    for i in range(int(count)):
        st.markdown(f"**Partia {i + 1}**")
        shipment_date = st.date_input("Data odprawy", value=date.today(), key=f"date_{i}")
        contents = st.text_area("Elementy faktycznie wysyłane", key=f"contents_{i}", max_chars=5000)
        parts.append({"number": i + 1, "date": shipment_date.isoformat(), "contents": contents.strip()})
    submitted = st.form_submit_button("Przygotuj kartę analizy", type="primary")

if submitted:
    errors = []
    for label, value in [("nazwa", name), ("materiały", materials), ("funkcja", purpose), ("kraj docelowy", destination), ("trasa", route)]:
        if not value.strip():
            errors.append(f"Uzupełnij pole: {label}.")
    normalized_code = re.sub(r"\s+", "", code)
    if normalized_code and not re.fullmatch(r"(?:[0-9]{6}|[0-9]{8}|[0-9]{10})", normalized_code):
        errors.append("Kod musi zawierać 6, 8 lub 10 cyfr.")
    if any(not p["contents"] for p in parts):
        errors.append("Opisz zawartość każdej partii.")
    if errors:
        st.session_state.pop("report", None)
        for message in errors:
            st.error(message)
    else:
        st.session_state["report"] = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "product": {"name": name.strip(), "materials": materials.strip(), "purpose": purpose.strip(),
                        "medium": medium.strip(), "compressor": compressor, "user_code": normalized_code},
            "export": {"origin": "Polska", "destination": destination.strip(), "route": route.strip(), "enduse": enduse.strip()},
            "shipments": parts,
            "verification": {key: "NIEZWERYFIKOWANE" for key in ["Klasyfikacja", "Eksport do Rosji", "Eksport do Białorusi", "Tranzyt przez Rosję", "Tranzyt przez Białoruś"]},
            "sources_checked": [],
        }
if "report" in st.session_state:
    report = st.session_state["report"]
    st.subheader("Zapisana karta — ostatnie zatwierdzenie formularza")
    st.caption("Po zmianie pól ponownie kliknij „Przygotuj kartę analizy”. Poniższe pliki zawierają ostatnio zatwierdzone dane.")
    st.json(report, expanded=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    st.download_button("Pobierz kartę JSON", payload, "karta-eksportu.json", "application/json")
    lines = ["KARTA PRZYGOTOWANIA ANALIZY EKSPORTU", "STATUS: NIEZWERYFIKOWANE", "", payload,
             "", "Nie przeprowadzono klasyfikacji ani kontroli sankcji. Karta nie stanowi potwierdzenia dopuszczalności eksportu."]
    st.download_button("Pobierz raport TXT", "\n".join(lines), "karta-eksportu.txt", "text/plain")
st.caption("Dane są przechowywane wyłącznie w bieżącej sesji. Pobierz kartę przed zamknięciem. Nie ma jeszcze wspólnej bazy ani historii analiz.")

