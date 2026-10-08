"""Puntúa una corrida de EZ contra el gold set, después de terminada.

    python gold_set_benchmark/puntuar.py --run <carpeta de la corrida> --mision M2 [--salida puntaje.md]

Solo lo ejecuta quien evalúa: el agente que opera EZ no abre el gold set. La salida
contiene identificadores, conteos y DOIs, nunca textos de afirmaciones ni pasajes, así
que puede commitearse. Las coincidencias por palabras son aproximaciones: las marcadas
«revisar» las confirma una persona.
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'packages'), str(ROOT / 'packages' / 'paper_search')]

from ez.acquisition import normalize_doi, plain_words  # noqa: E402
from ez.state import Store, read_json  # noqa: E402

GOLD = Path(__file__).resolve().parent


def rows(name, mission):
    with (GOLD / name).open(encoding='utf-8-sig', newline='') as handle:
        return [r for r in csv.DictReader(handle) if r.get('mision') == mission]


def grams(text, size=6):
    words = plain_words(text)
    return {' '.join(words[i:i + size]) for i in range(len(words) - size + 1)}


def overlap(a, b):
    a, b = set(plain_words(a)), set(plain_words(b))
    return len(a & b) / len(a | b) if a and b else 0.0


def score(folder, mission):
    folder = Path(folder)
    sources = read_json(folder / 'sources.json') if (folder / 'sources.json').exists() else []
    answer = read_json(folder / 'answer.json') if (folder / 'answer.json').exists() else {}
    claims = answer.get('claims', [])
    by_doi = {normalize_doi(s.get('doi')): s for s in sources if s.get('doi')}
    cited = {normalize_doi((r.get('source') or {}).get('doi')) for c in claims for r in c['references']}

    articles = []
    for row in rows('articulos_clave.csv', mission):
        doi = normalize_doi(row['doi'])
        source = by_doi.get(doi)
        if not source:
            stage = 'no encontrado en la búsqueda'
        elif source.get('screening', 'include') != 'include':
            stage = 'excluido en el cribado'
        elif source.get('notebook_status') != 'ready':
            stage = 'incluido sin PDF en el corpus (' + str(source.get('failure_code') or source.get('identity_status')) + ')'
        else:
            stage = 'citado' if doi in cited else 'en el corpus, no citado'
        articles.append((row['doi'], row.get('acceso_abierto', ''), stage))

    references = []
    for row in rows('afirmaciones_referencia.csv', mission):
        gold = grams(row['pasaje_literal'])
        doi = normalize_doi(row['doi_fuente'])
        same_source = [c for c in claims if any(normalize_doi((r.get('source') or {}).get('doi')) == doi for r in c['references'])]
        hit = [c['id'] for c in same_source if any(gold & grams(r.get('cited_text') or '') for r in c['references'])]
        close = sorted(same_source, key=lambda c: -overlap(c['text'], row['afirmacion']))[:1]
        state = 'cubierta (mismo pasaje)' if hit else 'revisar (misma fuente)' if same_source else 'no cubierta'
        references.append((row['id'], state, ', '.join(hit[:3] or [c['id'] for c in close])))

    forbidden = []
    for row in rows('afirmaciones_prohibidas.csv', mission):
        suspects = [c['id'] for c in claims if overlap(c['text'], row['afirmacion_incorrecta']) >= 0.5]
        forbidden.append((row['id'], 'revisar: ' + ', '.join(suspects[:5]) if suspects else 'sin coincidencias'))

    statements = [n['text'] for n in answer.get('uncited_statements', [])]
    gaps = []
    for index, row in enumerate(rows('lagunas_esperadas.csv', mission), 1):
        best = max((overlap(text, row['que_no_se_puede_responder']) for text in statements), default=0.0)
        declared = any(g for g in answer.get('gaps', []))
        gaps.append((index, row['causa'], 'revisar: posible mención' if best >= 0.2 else
                     'subpreguntas sin respaldo declaradas' if declared else 'no declarada'))

    events = Store(folder).events()
    times = [datetime.fromisoformat(e['at']) for e in events if e.get('at')]
    included = [s for s in sources if s.get('screening', 'include') == 'include']
    downloaded = [s for s in included if s.get('validation_status') == 'valid']
    operation = {
        'minutos de reloj': round((max(times) - min(times)).total_seconds() / 60, 1) if times else None,
        'consultas a NotebookLM': sum(e['kind'] == 'external_result' and e['payload'].get('command') == 'ask' for e in events),
        'fuentes incluidas': len(included),
        'PDFs válidos': f'{len(downloaded)} de {len(included)}',
        'afirmaciones entregadas': len(claims),
        'oraciones sin cita': len(statements),
        'afirmaciones con página': sum(any(r.get('page') for r in c['references']) for c in claims),
        'estado': (answer.get('answer') or {}).get('status'),
    }
    return {'articles': articles, 'references': references, 'forbidden': forbidden, 'gaps': gaps, 'operation': operation}


def markdown(result, mission, run):
    lines = [f'# Puntaje de {mission} — corrida `{run}`', '', '## Artículos clave', '', '| DOI | Acceso abierto | Resultado |',
             '|---|---|---|']
    lines += [f'| {doi} | {oa} | {stage} |' for doi, oa, stage in result['articles']]
    found = sum(stage in ('citado', 'en el corpus, no citado') for _, _, stage in result['articles'])
    lines += ['', f'En el corpus: {found} de {len(result["articles"])}.', '', '## Afirmaciones de referencia', '',
              '| Id | Resultado | Afirmaciones de EZ |', '|---|---|---|']
    lines += [f'| {i} | {state} | {ids} |' for i, state, ids in result['references']]
    lines += ['', '## Afirmaciones prohibidas', '', '| Id | Resultado |', '|---|---|']
    lines += [f'| {i} | {state} |' for i, state in result['forbidden']]
    lines += ['', '## Lagunas esperadas', '', '| # | Causa | Resultado |', '|---|---|---|']
    lines += [f'| {i} | {cause} | {state} |' for i, cause, state in result['gaps']]
    lines += ['', '## Operación', '', '| Medida | Valor |', '|---|---|']
    lines += [f'| {k} | {v} |' for k, v in result['operation'].items()]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--mision', required=True, choices=['M1', 'M2', 'M3'])
    parser.add_argument('--salida', type=Path)
    args = parser.parse_args()
    run = Path(args.run)
    text = markdown(score(run, args.mision), args.mision, Store(run).state().get('run_id'))
    if args.salida:
        args.salida.write_text(text, encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
