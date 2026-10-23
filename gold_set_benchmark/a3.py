"""Comparación A3: EZ, ChatGPT con búsqueda y NotebookLM manual sobre M1 a M3.

    python gold_set_benchmark/a3.py preparar [--ez M1=<corrida> ...] [--ez-sin-pdf M2=<corrida>] [--maximo N] [--comprobar-dois]
    python gold_set_benchmark/a3.py repuntaje
    python gold_set_benchmark/a3.py resultados [--salida gold_set_benchmark/resultado_a3.md]

Trabaja en `gold_set_benchmark/a3/`, fuera de git: `respuestas/<sistema>_<mision>.md` (lo que
cada sistema contestó, copiado entero), `registro.csv` (minutos y lagunas por respuesta),
`planilla_ciega.csv` (afirmaciones anonimizadas y en orden al azar, para puntuar) y `clave.csv`
(qué sistema dio cada afirmación; quien puntúa no la abre). El protocolo está en
`a3_protocolo.md`. El informe de `resultados` lleva solo conteos, nunca textos.
"""
import argparse
import csv
import math
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'packages'), str(ROOT / 'packages' / 'paper_search')]

from ez.acquisition import normalize_doi  # noqa: E402
from ez.presenter import short_citation  # noqa: E402
from ez.state import read_json  # noqa: E402

GOLD = Path(__file__).resolve().parent
WORK = GOLD / 'a3'
SYSTEMS = ('ez', 'ez-sin-pdf', 'chatgpt', 'notebooklm')
MISSIONS = ('M1', 'M2', 'M3')
SEED = 20261023
SHEET = ('codigo', 'mision', 'afirmacion', 'fuente_citada', 'doi_existe', 'fuente_existe', 'puntaje', 'prohibida', 'notas')
LOG = ('sistema', 'mision', 'minutos', 'lagunas_declaradas', 'lagunas_esperadas', 'corrida_ez', 'notas')

DOI = re.compile(r'\b(10\.\d{4,9}/[^\s\])>,;"]+)', re.I)
URL = re.compile(r'https?://[^\s)\]>]+')
NUMBER = re.compile(r'\[(\d{1,3})\]')
REFERENCES = re.compile(r'^\W*(referencias|fuentes|bibliograf[ií]a|references|sources|works cited)\W*$', re.I)


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_rows(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plain(text):
    """The sentence without citation marks, links or markdown, so it does not say which system wrote it."""
    text = re.sub(r'\[EZ:[^\]]*\]', '', text)
    text = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', '', text)
    text = URL.sub('', NUMBER.sub('', text))
    text = re.sub(r'[*_`#>]+', '', text)
    text = re.sub(r'\(\s*\)', '', text)
    return re.sub(r'\s+', ' ', text).strip(' -•·')


def sources_of(text, numbered):
    found = [numbered[n] for n in NUMBER.findall(text) if n in numbered]
    found += ['doi:' + normalize_doi(d.rstrip('.')) for d in DOI.findall(text)]
    found += [u.rstrip('.') for u in URL.findall(text) if 'doi.org/' not in u]
    return list(dict.fromkeys(found))


def split_answer(text):
    """Claims of a copied answer: one per sentence, with the sources cited in it or in its numbered list."""
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines) if REFERENCES.match(line.strip())), len(lines))
    numbered = {}
    for line in lines[end + 1:]:
        match = re.match(r'^\W*\[?(\d{1,3})[\].)]\s*(.+)', line.strip())
        if match:
            body = match[2].strip()
            doi = DOI.search(body)
            numbered[match[1]] = 'doi:' + normalize_doi(doi[1].rstrip('.')) if doi else body
    claims = []
    for line in lines[:end]:
        if line.lstrip().startswith('#'):
            continue
        first = len(claims)
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿(])', line.strip()):
            words, cited = plain(sentence), sources_of(sentence, numbered)
            if len(words) >= 30:
                claims.append({'afirmacion': words, 'fuente_citada': cited})
            elif cited and len(claims) > first:
                # A link left alone at the end of a paragraph («… ([site](url))») cites the sentence before it.
                claims[-1]['fuente_citada'] = list(dict.fromkeys(claims[-1]['fuente_citada'] + cited))
    for claim in claims:
        claim['fuente_citada'] = ' | '.join(claim['fuente_citada'])
    return claims


def ez_claims(folder):
    answer = read_json(Path(folder) / 'answer.json')
    claims = []
    for claim in answer.get('claims', []):
        cited = []
        for ref in claim.get('references', []):
            source = ref.get('source') or {}
            doi = normalize_doi(source.get('doi'))
            cited.append('doi:' + doi if doi else ' — '.join(x for x in (short_citation(source), source.get('title')) if x))
        claims.append({'afirmacion': plain(claim['text']), 'fuente_citada': ' | '.join(dict.fromkeys(c for c in cited if c))})
    return claims


def doi_exists(doi, session):
    try:
        response = session.get('https://doi.org/api/handles/' + doi, timeout=20)
    except Exception:
        return 'error'
    return 'si' if response.status_code == 200 else 'no' if response.status_code == 404 else 'error'


def prepare(ez_runs, limit=0, check_dois=False, ez_without_pdf=None):
    """`ez_without_pdf`: runs without the PDF the person imported (rule 2.3 reports M2 both ways)."""
    collected, runs = [], {'ez': ez_runs, 'ez-sin-pdf': ez_without_pdf or {}}
    for system in SYSTEMS:
        for mission in MISSIONS:
            if system in runs:
                if mission not in runs[system]:
                    continue
                claims = ez_claims(runs[system][mission])
            else:
                path = WORK / 'respuestas' / f'{system}_{mission}.md'
                if not path.exists():
                    continue
                claims = split_answer(path.read_text(encoding='utf-8'))
            if limit and len(claims) > limit:
                claims = random.Random(f'{SEED}-{system}-{mission}').sample(claims, limit)
            collected += [dict(c, sistema=system, mision=mission) for c in claims]
    random.Random(SEED).shuffle(collected)
    checked = {}
    if check_dois:
        import requests
        session = requests.Session()
        for doi in {s[4:] for c in collected for s in c['fuente_citada'].split(' | ') if s.startswith('doi:')}:
            checked[doi] = doi_exists(doi, session)
    sheet, key = [], []
    for number, claim in enumerate(collected, 1):
        code = f'A{number:03d}'
        dois = [s[4:] for s in claim['fuente_citada'].split(' | ') if s.startswith('doi:')]
        exists = 'sin_doi' if not dois else 'no' if any(checked.get(d) == 'no' for d in dois) else \
            'si' if dois and all(checked.get(d) == 'si' for d in dois) else 'sin_comprobar'
        sheet.append({'codigo': code, 'mision': claim['mision'], 'afirmacion': claim['afirmacion'],
                      'fuente_citada': claim['fuente_citada'] or 'sin fuente', 'doi_existe': exists})
        key.append({'codigo': code, 'sistema': claim['sistema'], 'mision': claim['mision']})
    write_rows(WORK / 'planilla_ciega.csv', SHEET, sheet)
    write_rows(WORK / 'clave.csv', ('codigo', 'sistema', 'mision'), key)
    return sheet, key


def rescore_sample():
    sheet = read_rows(WORK / 'planilla_ciega.csv')
    chosen = random.Random(SEED + 7).sample(sheet, max(1, round(len(sheet) * 0.2)))
    rows = [{k: (row[k] if k in ('codigo', 'mision', 'afirmacion', 'fuente_citada', 'doi_existe') else '') for k in SHEET}
            for row in sorted(chosen, key=lambda r: r['codigo'])]
    write_rows(WORK / 'planilla_repuntaje.csv', SHEET, rows)
    return rows


def wilson(hits, total, z=1.96):
    if not total:
        return None
    p = hits / total
    center, half = p + z * z / (2 * total), z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (center - half) / (1 + z * z / total), (center + half) / (1 + z * z / total)


def key_articles(mission):
    with (GOLD / 'articulos_clave.csv').open(encoding='utf-8-sig', newline='') as handle:
        return {normalize_doi(r['doi']) for r in csv.DictReader(handle) if r['mision'] == mission}


def summarize(rows, log):
    scores = [int(r['puntaje']) for r in rows]
    cited = {}
    for row in rows:
        for source in row['fuente_citada'].split(' | '):
            if source and source != 'sin fuente':
                invented = row['doi_existe'] == 'no' or row['fuente_existe'].strip().lower() == 'no'
                cited[source] = cited.get(source, False) or invented
    full = sum(s == 3 for s in scores)
    interval = wilson(full, len(scores))
    keys = set().union(*(key_articles(m) for m in {r['mision'] for r in rows})) if rows else set()
    found = {s[4:] for s in cited if s.startswith('doi:')} & keys
    minutes = [float(e['minutos'].replace(',', '.')) for e in log if e.get('minutos')]
    declared = [(int(e['lagunas_declaradas']), int(e['lagunas_esperadas'])) for e in log
                if e.get('lagunas_declaradas') and e.get('lagunas_esperadas')]
    return {
        'afirmaciones': len(scores),
        'sin fuente': sum(r['fuente_citada'] == 'sin fuente' for r in rows),
        'referencias inventadas': f'{sum(cited.values())} de {len(cited)}',
        'respaldo completo (3)': f'{full / len(scores):.0%}' if scores else '—',
        'IC 95 % del respaldo completo': f'{interval[0]:.0%}–{interval[1]:.0%}' if interval else '—',
        'respaldo al menos parcial (≥2)': f'{sum(s >= 2 for s in scores) / len(scores):.0%}' if scores else '—',
        'puntaje medio': f'{sum(scores) / len(scores):.2f}' if scores else '—',
        'prohibidas afirmadas': ', '.join(sorted({r['prohibida'].strip() for r in rows if r['prohibida'].strip()})) or 'ninguna',
        'artículos clave citados': f'{len(found)} de {len(keys)}',
        'lagunas declaradas': f'{sum(d for d, _ in declared)} de {sum(e for _, e in declared)}' if declared else '—',
        'minutos': f'{sum(minutes):.1f}' if minutes else '—',
        '_invented_rate': sum(cited.values()) / len(cited) if cited else 0.0,
        '_full_rate': full / len(scores) if scores else 0.0,
    }


def results():
    sheet = {r['codigo']: r for r in read_rows(WORK / 'planilla_ciega.csv')}
    key = read_rows(WORK / 'clave.csv')
    log = read_rows(WORK / 'registro.csv') if (WORK / 'registro.csv').exists() else []
    # «-» marks a row that is not a claim (a greeting, a heading the split kept); deleted rows count the same.
    missing = [c for c, r in sheet.items() if r['puntaje'].strip() not in ('0', '1', '2', '3', '-')]
    if missing:
        raise SystemExit(f'Faltan puntajes (0 a 3, o «-») en {len(missing)} filas (primera: {missing[0]}).')
    rows = [dict(sheet[k['codigo']], sistema=k['sistema']) for k in key
            if k['codigo'] in sheet and sheet[k['codigo']]['puntaje'].strip() != '-']
    lines = ['# Resultado de A3', '', 'Puntaje según `reglas_benchmark.md`. Solo conteos; los textos quedan en `a3/`, fuera de git.', '']
    totals = {}
    for mission in MISSIONS + ('Total',):
        part = [r for r in rows if mission == 'Total' or r['mision'] == mission]
        if not part:
            continue
        present = [s for s in SYSTEMS if any(r['sistema'] == s for r in part)]
        stats = {s: summarize([r for r in part if r['sistema'] == s],
                              [e for e in log if e['sistema'] == s and (mission == 'Total' or e['mision'] == mission)])
                 for s in present}
        if mission == 'Total':
            totals = stats
        lines += [f'## {mission}', '', '| Medida | ' + ' | '.join(present) + ' |', '|---|' + '---|' * len(present)]
        lines += [f'| {name} | ' + ' | '.join(str(stats[s][name]) for s in present) + ' |'
                  for name in stats[present[0]] if not name.startswith('_')]
        lines.append('')
    again = WORK / 'planilla_repuntaje.csv'
    if again.exists():
        pairs = [(sheet[r['codigo']]['puntaje'].strip(), r['puntaje'].strip()) for r in read_rows(again)
                 if r['puntaje'].strip() and r['codigo'] in sheet]
        if pairs:
            agreement = sum(a == b for a, b in pairs) / len(pairs)
            lines += ['## Repuntaje', '', f'Coincidencia: {agreement:.0%} en {len(pairs)} afirmaciones' +
                      (' (menor al 80 %: precisar la rúbrica antes de seguir).' if agreement < 0.8 else '.'), '']
    others = [s for s in totals if not s.startswith('ez')]
    if 'ez' in totals and others:
        ez = totals['ez']
        wins = all(ez['_invented_rate'] <= totals[s]['_invented_rate'] and ez['_full_rate'] >= totals[s]['_full_rate'] for s in others)
        lines += ['## Regla de decisión', '', 'EZ ' + ('supera o iguala' if wins else 'no supera') +
                  ' a las alternativas en referencias inventadas y respaldo completo.' +
                  ('' if wins else ' Según la hoja de ruta, se revisa el producto antes de distribuirlo.'), '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('preparar')
    prepare_parser.add_argument('--ez', action='append', default=[], metavar='MISION=CORRIDA')
    prepare_parser.add_argument('--ez-sin-pdf', action='append', default=[], metavar='MISION=CORRIDA')
    prepare_parser.add_argument('--maximo', type=int, default=0, help='afirmaciones al azar por respuesta; 0 = todas')
    prepare_parser.add_argument('--comprobar-dois', action='store_true')
    commands.add_parser('repuntaje')
    results_parser = commands.add_parser('resultados')
    results_parser.add_argument('--salida', type=Path)
    args = parser.parse_args()
    if args.command == 'preparar':
        runs = dict(item.split('=', 1) for item in args.ez)
        sheet, key = prepare(runs, args.maximo, args.comprobar_dois, dict(item.split('=', 1) for item in args.ez_sin_pdf))
        counts = {}
        for row in key:
            counts[(row['sistema'], row['mision'])] = counts.get((row['sistema'], row['mision']), 0) + 1
        for (system, mission), count in sorted(counts.items()):
            print(f'{system} {mission}: {count} afirmaciones')
        print(f'Planilla ciega: {WORK / "planilla_ciega.csv"} ({len(sheet)} filas)')
    elif args.command == 'repuntaje':
        print(f'Repuntaje: {len(rescore_sample())} afirmaciones en {WORK / "planilla_repuntaje.csv"}')
    else:
        text = results()
        if args.salida:
            args.salida.write_text(text, encoding='utf-8')
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
