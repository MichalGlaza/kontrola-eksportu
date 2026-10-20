"""Run from repository root: PYTHONPATH=. python tests/smoke_sanctions.py.

All documents, credentials and source records here are fictional test inputs.
"""
import hashlib
from unittest.mock import patch
from datetime import timedelta
from streamlit.testing.v1 import AppTest
from test_sanctions import HTML, URL
from sanctions import parse_annex_html
from card_export import report_html

app = AppTest.from_file('app.py')
app.secrets['APP_PASSWORD'] = 'test-only-password-123456'
app.session_state['auth_marker'] = hashlib.sha256(b'test-only-password-123456').hexdigest()
app.session_state['sanction_documents'] = {'833/2014:XXXVII':parse_annex_html(HTML, URL, '833/2014','XXXVII')}
app.run()
app.sidebar.radio[0].set_value('Sankcje i tranzyt').run()
assert not app.exception, app.exception
app.text_input[0].set_value('8415830090')
day = app.date_input[0].value.isoformat()
source = {'code':'8415830090','date':day,'source':'https://ext-isztar4.mf.gov.pl/test',
          'fetched_at':day+'T08:00:00+00:00','data':{'nonTariffMeasures':[
              {'country':{'code':'RU'},'description':'Kontrola wywozu', 'footnotes':[{'code':'TEST','description':'Fikcyjny rekord testowy'}]},
              {'country':{'code':'BY'},'description':'Kontrola wywozu'}]}}
with patch('sanctions_ui.measures', return_value=source):
    next(b for b in app.button if b.label=='Sprawdź eksport i tranzyt').click().run()
assert not app.exception, app.exception
result = app.session_state['sanction_result']
assert len(result['cases']) == 4
assert len(result['cases'][2]['annex_checks'][0]['matches']) == 2
assert len(result['cases'][0]['isztar']['records']) == 1
next(b for b in app.button if b.label=='Dołącz ten wynik do karty analizy').click().run()
assert not app.exception, app.exception
assert app.session_state['card_sanctions']['code'] == '8415830090'
# A changed date must hide the old result and its attachment button.
app.date_input[0].set_value(app.date_input[0].value - timedelta(days=1)).run()
assert not any(b.label=='Dołącz ten wynik do karty analizy' for b in app.button)
app.sidebar.radio[0].set_value('Karta analizy eksportu').run()
for el in app.text_input:
    if el.label=='Kraj docelowy':el.set_value('Kazachstan — dane testowe')
    if el.label=='Pełna trasa':el.set_value('Polska → Rosja → Kazachstan — dane testowe')
    if el.label=='Roboczy kod partii (opcjonalnie)':el.set_value('8415830090')
for el in app.text_area:
    if el.label=='Elementy faktycznie wysyłane':el.set_value('Fikcyjna partia testowa')
next(b for b in app.button if b.label=='Przygotuj kartę analizy').click().run()
assert not app.exception, app.exception
report = app.session_state['report']
assert report['sanctions_screening']['code'] == '8415830090'
assert 'ZGODNY KOD I DATA' in report['shipment_screening_coverage'][0]['status']
assert '7. Sankcje i tranzyt' in report_html(report)
assert 'XXXVII' in report_html(report)
print('PASS: four scenarios, export evidence, transit matches, stale result hidden, card attachment and printable report')
