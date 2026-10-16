# Kontrola eksportu — Streamlit
Wersja 0.2: formularz przygotowania analizy. Nie ustala kodów i nie sprawdza sankcji.

## Funkcje
- Wspólne hasło, sprawdzane po stronie serwera; bez indywidualnych kont.
- Opis towaru, trasa, odbiorca i osobne partie / daty odpraw.
- Eksport karty JSON i TXT. Dane wyłącznie w sesji.
- Linki do ISZTAR, EUR-Lex i MSWiA.

## Uruchomienie w Streamlit Community Cloud
1. Zaloguj się na https://share.streamlit.io i połącz GitHub.
2. Create app → Yup, I have an app.
3. Repository: MichalGlaza/kontrola-eksportu; Branch: main; Main file: app.py.
4. Advanced settings → Python 3.12.
5. W Secrets ustaw:
```toml
APP_PASSWORD = "WSTAW_TUTAJ_WLASNE_DLUGIE_HASLO"
```
Zastąp przykład własnym losowym hasłem minimum 16 znaków. Nie umieszczaj hasła w GitHub ani czacie. Podany przykładowy tekst jest odrzucany przez aplikację.
6. Zapisz ustawienia i uruchom Deploy.

Brak hasła lub zbyt krótkie hasło blokuje aplikację. Publiczność repozytorium nie daje dostępu do formularza. Sekrety są ustawiane oddzielnie w Streamlit.

## Lokalnie
Python 3.12:
```sh
pip install -r requirements.txt
streamlit run app.py
```
Ustaw prawdziwe hasło w lokalnym .streamlit/secrets.toml (plik ignorowany przez Git).

## Ograniczenia
- Nie podłączono automatycznych danych taryfowych ani przepisów.
- Nie wydaje się oceny dopuszczalności eksportu lub tranzytu.
- Nie ma trwałej historii, synchronizacji między użytkownikami, wczytywania kart ani raportu PDF.
- Hasło jest wspólne. Zmiana sekretu unieważnia sesję przy następnym wykonaniu aplikacji.
- Krótka blokada błędnych prób jest wyłącznie sesyjna, nie zastępuje ochrony przed zautomatyzowanymi atakami.
- Formularz zapisuje kartę dopiero po zatwierdzeniu. Pobranie dotyczy ostatniego zatwierdzenia.

## Kolejne etapy
1. Potwierdzenie sposobu dostępu do ISZTAR/TARIC.
2. Klasyfikacja z uzasadnieniem i pytaniami o brakujące cechy.
3. Wersjonowane źródła prawne i oddzielne kontrole eksportu/tranzytu.
4. Raport z artykułem, załącznikiem, pozycją oraz datą weryfikacji.
