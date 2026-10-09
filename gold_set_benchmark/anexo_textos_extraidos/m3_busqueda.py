"""Búsqueda documentada del control negativo M3 (versión 2 del gold set).

Pregunta: estructura experimental de la Emb de Corynebacterium glutamicum y modo de unión del etambutol.
Consulta PubMed (E-utilities), Europe PMC (REST) y RCSB PDB (Search API v2). No usa buscadores con IA.
Uso: python m3_busqueda.py  ->  escribe m3_resultados.json e imprime un resumen para busqueda_control_negativo.md
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

D = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "tesis-goldset/1.0"}


def get(url, data=None):
    headers = dict(UA)
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=60) as h:
                body = h.read()
                return json.loads(body) if body else None  # RCSB responde 204 sin cuerpo cuando no hay resultados
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                return None
            time.sleep(3)
        except Exception:
            time.sleep(3)
    raise SystemExit("No se pudo consultar " + url + ". Repetí la búsqueda: un fallo no es un resultado vacío.")


PUBMED = [
    'glutamicum[tiab] AND (emb[tiab] OR arabinofuranosyltransferase[tiab] OR arabinosyltransferase[tiab])',
    'glutamicum[tiab] AND (emb[tiab] OR arabinofuranosyltransferase[tiab] OR arabinosyltransferase[tiab]) AND '
    '(structure[tiab] OR "cryo-EM"[tiab] OR "cryo-electron"[tiab] OR crystal*[tiab])',
    'corynebacter*[tiab] AND ethambutol[tiab] AND (structure[tiab] OR "cryo-EM"[tiab] OR crystal*[tiab] OR binding[tiab])',
]
EUROPE = [
    'glutamicum AND (Emb OR arabinofuranosyltransferase OR arabinosyltransferase) AND ("cryo-EM" OR "crystal structure" OR crystallography)',
    'TITLE_ABS:(glutamicum AND (emb OR arabinofuranosyltransferase OR arabinosyltransferase))',
]
RCSB = {
    "Corynebacterium glutamicum + arabinosyltransferase": {
        "query": {"type": "group", "logical_operator": "and", "nodes": [
            {"type": "terminal", "service": "text", "parameters": {
                "attribute": "rcsb_entity_source_organism.taxonomy_lineage.name", "operator": "exact_match",
                "value": "Corynebacterium glutamicum"}},
            {"type": "terminal", "service": "full_text", "parameters": {"value": "arabinosyltransferase"}}]},
        "return_type": "entry", "request_options": {"paginate": {"start": 0, "rows": 100}}},
    "Emb arabinosyltransferase (cualquier organismo)": {
        "query": {"type": "terminal", "service": "full_text", "parameters": {"value": "Emb arabinosyltransferase ethambutol"}},
        "return_type": "entry", "request_options": {"paginate": {"start": 0, "rows": 100}}},
}

res = {"fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "pubmed": [], "europepmc": [], "rcsb_pdb": []}
for q in PUBMED:
    r = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=200&term=" + urllib.parse.quote(q))
    ids = r["esearchresult"]["idlist"]
    items = []
    if ids:
        s = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id=" + ",".join(ids))
        items = [{"pmid": i, "anio": s["result"][i].get("pubdate", "")[:4], "titulo": s["result"][i].get("title", "")} for i in ids]
    res["pubmed"].append({"consulta": q, "n": int(r["esearchresult"]["count"]), "items": items})
    time.sleep(1)
for q in EUROPE:
    r = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&pageSize=200&resultType=lite&query=" + urllib.parse.quote(q))
    items = [{"id": x.get("id"), "pmid": x.get("pmid", ""), "doi": x.get("doi", ""), "anio": x.get("pubYear", ""), "titulo": x.get("title", "")}
             for x in r["resultList"]["result"]]
    res["europepmc"].append({"consulta": q, "n": r["hitCount"], "items": items})
for label, body in RCSB.items():
    r = get("https://search.rcsb.org/rcsbsearch/v2/query", body)
    ids = [x["identifier"] for x in (r or {}).get("result_set", [])]
    items = []
    for pdb_id in ids[:100]:
        e = get("https://data.rcsb.org/rest/v1/core/entry/" + pdb_id)
        organismos = set()
        for ent in e.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", []):
            p = get(f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{ent}") or {}
            organismos.update(o.get("scientific_name", "") for o in p.get("rcsb_entity_source_organism", []))
        items.append({"pdb": pdb_id, "titulo": e.get("struct", {}).get("title", ""),
                      "metodo": ",".join(x.get("method", "") for x in e.get("exptl", [])),
                      "organismos": sorted(o for o in organismos if o)})
    res["rcsb_pdb"].append({"consulta": label, "cuerpo": body, "n": (r or {}).get("total_count", 0), "items": items})

json.dump(res, open(os.path.join(D, "m3_resultados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # la consola cp1252 no muestra "α"
print("Fecha:", res["fecha"])
for key in ("pubmed", "europepmc", "rcsb_pdb"):
    for block in res[key]:
        print(f"\n### {key.upper()} | {block['consulta']} -> {block['n']}")
        for it in block["items"][:80]:
            print("  ", it.get("pmid") or it.get("pdb") or it.get("id"), it.get("anio", it.get("metodo", "")), "; ".join(it.get("organismos", [])), it["titulo"][:150])
