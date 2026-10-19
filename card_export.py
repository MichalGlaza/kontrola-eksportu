"""Self-contained printable card; all user/source content is escaped."""
from html import escape
import json


def report_html(report):
    def esc(value):
        return escape(str(value if value is not None else ''))
    def table(rows):
        return '<table>' + ''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v)+'</td></tr>' for k,v in rows) + '</table>'
    p, e = report['product'], report['export']
    body = '<h1>Karta analizy eksportu</h1><p class="status">ROBOCZA — NIEZWERYFIKOWANE</p>'
    body += table([('Numer karty',report['id']),('Utworzono (UTC)',report['created_at']),('Przygotował',report['author'])])
    body += '<h2>1. Towar i klasyfikacja robocza</h2>' + table([
        ('Nazwa',p['name']),('Materiały',p['materials']),('Funkcja i wyposażenie',p['purpose']),
        ('Medium',p['medium']),('Własna sprężarka',p['compressor']),('Kod roboczy',p['user_code']),
        ('Uzasadnienie / brakujące dane',report['classification_rationale'])])
    body += '<h2>2. Odbiorca i trasa</h2>'+table([('Kraj wywozu',e['origin']),('Kraj docelowy',e['destination']),('Trasa',e['route']),('Odbiorca i zastosowanie końcowe',e['enduse'])])
    body += '<h2>3. Odrębne wysyłki i odprawy</h2><p>Kod urządzenia nie jest automatycznie kodem każdej partii. Odczyt ISZTAR załączony do karty dotyczy wyłącznie wskazanego w nim kodu i daty.</p>'
    for s in report['shipments']:
        body += '<h3>Partia '+esc(s['number'])+'</h3>'+table([('Data odprawy',s['date']),('Zawartość',s['contents']),('Kod roboczy partii',s['code']),('Klasyfikacja',s['classification'])])
    body += '<h2>4. Zakres weryfikacji</h2>'+table(report['verification'].items())
    body += '<p>Odczyt ISZTAR nie oznacza przeprowadzenia analizy prawnej. Karta nie potwierdza dopuszczalności eksportu ani tranzytu. Dane należy ponownie sprawdzić dla daty każdej odprawy.</p>'
    body += '<h2>5. Uwagi i dokumenty do uzyskania</h2><p>'+esc(report['notes'])+'</p>'
    source = report.get('isztar_snapshot')
    body += '<h2>6. Dane źródłowe ISZTAR</h2>'
    if source:
        body += table([('Kod odczytu',source['code']),('Stan na dzień',source['date']),('Pobrano (UTC)',source['fetched_at']),('Adres źródła',source['source'])])
        for i, m in enumerate(source['data']['nonTariffMeasures'],1):
            country=m.get('country',{})
            body += '<h3>'+esc(f"{i}. {country.get('code','')} — {m.get('description','')}")+'</h3>'
            body += '<pre>'+esc(json.dumps(m,ensure_ascii=False,indent=2))+'</pre>'
        body += '<h3>Pełna odpowiedź źródłowa (w tym cła i podatki)</h3><pre>'+esc(json.dumps(source['data'],ensure_ascii=False,indent=2))+'</pre>'
    else:
        body += '<p>Nie załączono odczytu ISZTAR.</p>'
    return '<!doctype html><html lang="pl"><meta charset="utf-8"><title>Karta analizy eksportu</title><style>body{font:14px Arial,sans-serif;max-width:1000px;margin:35px auto;color:#172838;padding:20px}h1,h2{color:#174b69}h2{margin-top:28px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd5dc;padding:9px;text-align:left;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}th{width:28%;background:#f0f5f7}p{white-space:pre-wrap}.status{padding:12px;background:#fff0c2;font-weight:bold}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:11px monospace;border:1px solid #ccd5dc;padding:12px}@media print{body{margin:0;padding:0;font-size:10pt}h2,h3{break-after:avoid}tr{break-inside:avoid}@page{size:A4;margin:16mm}}</style><body>'+body+'</body></html>'
