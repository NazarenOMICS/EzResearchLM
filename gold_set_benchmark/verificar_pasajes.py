"""Verificación mecánica del gold set sin redistribuir los textos completos.

Para cada pasaje de afirmaciones_referencia.csv y afirmaciones_prohibidas.csv:
1. comprueba que el texto extraído localmente coincide con la huella de anexo_hashes_paginas.json;
2. comprueba que cada fragmento del pasaje (separados por [...]) aparece en la página indicada,
   ignorando solo espacios y saltos de línea.

Uso: python verificar_pasajes.py [--textos anexo_textos_extraidos]
Los textos son listas JSON de páginas extraídas con pypdf 6.19.0 (ver anexo_textos_extraidos/inventario.py).
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEGMENT = re.compile(r'(.+?)\s*\(p\. (\d+), ([^;)]+\.pdf)(?:;[^)]*)?\)', re.S)


def compact(text):
    return re.sub(r'\s+', '', text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--textos', type=Path, default=ROOT / 'anexo_textos_extraidos')
    args = parser.parse_args()
    hashes = json.loads((ROOT / 'anexo_hashes_paginas.json').read_text(encoding='utf-8'))['archivos']
    cache = {}

    def pages(pdf):
        name = Path(pdf).name
        if name not in cache:
            path = args.textos / (name[:-4] + '.json')
            if not path.exists():
                cache[name] = 'sin_texto_local'
            else:
                value = json.loads(path.read_text(encoding='utf-8'))
                expected = hashes.get(name, {}).get('sha256_texto_pagina')
                actual = [hashlib.sha256(t.encode('utf-8')).hexdigest() for t in value]
                cache[name] = value if expected is None or actual == expected else 'texto_distinto_de_la_huella'
        return cache[name]

    def check(pdf, page, passage):
        value = pages(pdf)
        if isinstance(value, str):
            return value
        fragments = [f.strip() for f in passage.split('[...]') if f.strip()]
        if all(compact(f) in compact(value[int(page) - 1]) for f in fragments):
            return 'ok'
        found = [i + 1 for i, t in enumerate(value) if all(compact(f) in compact(t) for f in fragments)]
        return f'FALLA (aparece en p. {found})' if found else 'FALLA (no aparece)'

    results = []
    for row in csv.DictReader(open(ROOT / 'afirmaciones_referencia.csv', encoding='utf-8-sig')):
        results.append((row['id'], check(row['archivo_pdf'], row['pagina'], row['pasaje_literal'])))
    for row in csv.DictReader(open(ROOT / 'afirmaciones_prohibidas.csv', encoding='utf-8-sig')):
        segments = SEGMENT.findall(row['pasaje_que_la_contradice_o_limita'])
        if not segments:
            results.append((row['id'], 'sin_pasaje_en_pdf'))
            continue
        states = [check(pdf, page, text.strip().lstrip('[...]').strip()) for text, page, pdf in segments]
        results.append((row['id'], 'ok' if all(s == 'ok' for s in states) else '; '.join(states)))
    for item, state in results:
        print(f'{item}\t{state}')
    failed = [i for i, s in results if s.startswith(('FALLA', 'texto_distinto'))]
    print(f'\n{sum(s == "ok" for _, s in results)} ok, {len(failed)} fallas, '
          f'{sum(s == "sin_texto_local" for _, s in results)} sin texto local, '
          f'{sum(s == "sin_pasaje_en_pdf" for _, s in results)} sin pasaje en PDF')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
