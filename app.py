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
    st.caption("Wersja 0.4 · ISZTAR + karta analizy")
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

from analysis_card import render
render()
