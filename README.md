# Kontrola eksportu — Streamlit
Wersja 0.3: wyszukiwarka oficjalnej nomenklatury ISZTAR i odczyt środków. Nie jest pełną kontrolą sankcyjną.

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
- Podłączono oficjalne API ISZTAR. Nie pobrano pełnych aktualnych aktów ani załączników prawnych.
- Tranzyt, kontrahenci, zastosowanie końcowe i polskie sankcje nie są automatycznie oceniane.
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


## Moduł ISZTAR
Wybierz moduł w bocznym panelu, datę i zakres. Wpisz słowo z nomenklatury, np. klimatyzator, lub prefiks kodu. Domyślny zakres to strona 16 API (sekcja XVI). Cała nomenklatura pobiera wszystkie strony z parametru links.last; błąd dowolnej strony blokuje wynik zamiast udawać kompletną bazę.
Wybierz kod końcowy i pobierz środki. Pokazywane są wszystkie środki pozataryfowe, rozdzielone na RU, BY i pozostałe kraje/grupy. Grupy krajów nie są automatycznie rozstrzygane. Warunki i wyłączenia zawsze wymagają oceny.
Wyszukiwanie jest tekstowe (wszystkie słowa), nie semantyczne. Nie klasyfikuje dowolnych produktów na podstawie składu. Wyniki zawierają pełną ścieżkę opisu; brak dopasowania nie jest zgodą na eksport. Limit widoku: 100 wyników, ze wskazaniem pełnej liczby.
Cache nomenklatury: godzina; środków: 15 minut. Każdy wynik podaje datę zapytania i rzeczywisty czas pobrania. Czas pobrania nie dowodzi aktualności przepisów. Daty przyszłe są blokowane. Karta analizy i odczyt ISZTAR mają oddzielne eksporty; odczyt nie zmienia automatycznie statusu karty.
Dokumentacja źródła: https://ext-isztar4.mf.gov.pl/taryfa_celna/json-api?lang=PL
Endpointy: /tariff/rest/goods-nomenclature/codes oraz /tariff/rest/goods-nomenclature/measures.

## Testy
python -m unittest discover -s tests

## Wersja 0.4 — karta analizy
Po pobraniu środków w Wyszukiwarce ISZTAR wybierz „Dołącz ten odczyt do karty analizy”, następnie przejdź do modułu karty. Dołączenie jest świadomym wyborem użytkownika, a zatwierdzona karta zawiera kopię odczytu z datą i adresem źródła. Kod karty musi odpowiadać kodowi odczytu. Dane nie są ponownie pobierane przy generowaniu karty.

Karta zawiera opis centrali, trasę, odbiorcę i zastosowanie końcowe, osobne partie z roboczymi kodami, uzasadnienie klasyfikacji, uwagi oraz zakres niewykonanej weryfikacji. Można pobrać JSON lub samodzielny HTML do wydruku i zapisania jako PDF w przeglądarce. Eksport TXT został zastąpiony czytelnym HTML. Nie ma automatycznej oceny prawnej ani trwałego zapisu formularza. Pobierz zatwierdzoną kartę przed opuszczeniem sesji.

Test interfejsu: `PYTHONPATH=. python tests/smoke_card.py` (wyłącznie fikcyjne dane i hasło testowe).

## Wersja 0.5 — sankcje i tranzyt (kontrola częściowa)
Moduł „Sankcje i tranzyt” wykonuje osobne zestawienia dla eksportu do Rosji, eksportu do Białorusi i tranzytu przez każdy z tych krajów. Dla dokładnego kodu TARIC i daty pobiera ISZTAR. Wpisy o jednoznacznym kierunku wywozowym pokazuje wraz z warunkami; pozostałe rekordy, w tym import i grupy krajów, pozostają dostępne do przeglądu. Żaden warunek zezwolenia nie jest automatycznie uznawany za spełniony.

Porównanie kodów CN obejmuje wyłącznie wybrane załączniki przemysłowe: 833/2014 XXIII i XXXVII oraz 765/2006 XIV, XVIII i XIX. Wymaga wczytania HTML konkretnej wersji tekstu skonsolidowanego EUR-Lex i podania jej adresu z identyfikatorem CELEX i datą. Importer odczytuje tabelę od wskazanego nagłówka do następnego załącznika, zachowuje „ex”, kontekst i wiersze nierozpoznane. Sprawdzenie identyfikatora w pliku jest kontrolą struktury, a nie potwierdzeniem pochodzenia. Moduł nie potwierdza aktualności, kompletności prawnej ani autentyczności dokumentu. Automatyczny import najnowszych aktów nie został wdrożony.

Brak dopasowania oznacza wyłącznie brak kodu w odczytanych wierszach. Brak dokumentu, nieprzetworzony wiersz lub nowszy dokument dla historycznej daty nie daje wyniku „dozwolone”. Pozycje techniczne, towary podwójnego zastosowania, pozostałe załączniki, kontrahenci, banki, przewoźnicy, sankcje polskie i wyjątki nie są automatycznie weryfikowane.

Wynik można pobrać do JSON i świadomie dołączyć do karty. Karta wymaga zgodności kodu głównego, a dla każdej partii pokazuje zgodność jej własnego kodu i daty z datą kontroli częściowej. Brak kodu partii nie powoduje odziedziczenia kodu centrali. Taki wynik pozostaje analizą częściową, bez zgody na wysyłkę.

Testy: `python -m unittest discover -s tests -v`, `PYTHONPATH=. python tests/smoke_sanctions.py`. Testy importera korzystają z jawnie fikcyjnego HTML. Nie przeprowadzono jeszcze walidacji importera na rzeczywistym pliku prawnym EUR-Lex; należy ją wykonać przed poleganiem na wynikach porównania załączników.
