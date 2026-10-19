import hashlib
from streamlit.testing.v1 import AppTest
at=AppTest.from_file('app.py')
at.secrets['APP_PASSWORD']='test-only-password-123456'
at.session_state['auth_marker']=hashlib.sha256(b'test-only-password-123456').hexdigest()
at.run()
at.sidebar.radio[0].set_value('Karta analizy eksportu').run()
assert not at.exception, at.exception
for el in at.text_input:
 if el.label=='Kraj docelowy':el.set_value('Kazachstan')
 if el.label=='Pełna trasa':el.set_value('Polska → Litwa → Rosja → Kazachstan')
for el in at.text_area:
 if el.label=='Elementy faktycznie wysyłane':el.set_value('Wentylator z silnikiem; dane testowe')
next(b for b in at.button if b.label=='Przygotuj kartę analizy').click().run()
assert not at.exception, at.exception
r=at.session_state['report']
assert r['schema_version']==2 and r['isztar_snapshot'] is None
assert all(v=='NIEZWERYFIKOWANE' for v in r['verification'].values())
from card_export import report_html
r['notes']='<script>alert(1)</script>'
h=report_html(r)
assert '<script>' not in h and '&lt;script&gt;' in h
print('PASS: karta, statusy, eksport HTML, escaping')
source={'code':'8415830090','date':'2026-10-19','fetched_at':'2026-10-19T08:00:00+00:00','source':'https://ext-isztar4.mf.gov.pl/','data':{'nonTariffMeasures':[]}}
at.session_state['card_source']=source
at.run()
next(b for b in at.button if b.label=='Przygotuj kartę analizy').click().run()
assert not at.exception,at.exception
r=at.session_state['report']
assert r['isztar_snapshot']['code']=='8415830090'
assert '8415830090' in report_html(r)
for el in at.text_input:
 if el.label=='Roboczy kod towaru — wymaga potwierdzenia':el.set_value('1111111111')
next(b for b in at.button if b.label=='Przygotuj kartę analizy').click().run()
assert any('różni się' in e.value for e in at.error)
assert 'report' not in at.session_state
print('PASS: dołączanie źródła i blokada niezgodnego kodu')
