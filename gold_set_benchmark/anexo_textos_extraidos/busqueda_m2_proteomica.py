import json, os, time, urllib.request, urllib.parse, datetime
D = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "tesis-goldset/1.0 (mailto:" + os.environ.get("GOLDSET_CONTACT_EMAIL", "you@example.com") + ")"}
def get(u):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as h:
                return json.load(h)
        except Exception:
            time.sleep(3)
pubmed = [
 'ethambutol[tiab] AND glutamicum[tiab]',
 'ethambutol[tiab] AND glutamicum[tiab] AND (proteom*[tiab] OR "mass spectrometry"[tiab])',
 'ethambutol AND corynebacterium AND (proteomics OR proteome OR "mass spectrometry")',
 'ethambutol[tiab] AND proteom*[tiab] AND (mycobacter*[tiab] OR corynebacter*[tiab])',
]
europe = [
 'ethambutol AND glutamicum AND (proteome OR proteomic OR proteomics)',
 'TITLE_ABS:(ethambutol AND glutamicum)',
 'TITLE_ABS:(ethambutol AND (proteome OR proteomic OR proteomics) AND (corynebacterium OR mycobacterium OR mycobacteria))',
]
res = {"fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "pubmed": [], "europepmc": []}
for q in pubmed:
    r = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=200&term=" + urllib.parse.quote(q))
    ids = r["esearchresult"]["idlist"]
    items = []
    if ids:
        s = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id=" + ",".join(ids))
        for i in ids:
            d = s["result"][i]
            items.append({"pmid": i, "anio": d.get("pubdate", "")[:4], "titulo": d.get("title", "")})
    res["pubmed"].append({"consulta": q, "n": int(r["esearchresult"]["count"]), "items": items})
    time.sleep(1)
for q in europe:
    r = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&pageSize=200&resultType=lite&query=" + urllib.parse.quote(q))
    items = [{"id": x.get("id"), "fuente": x.get("source"), "pmid": x.get("pmid", ""), "doi": x.get("doi", ""), "anio": x.get("pubYear", ""), "titulo": x.get("title", ""), "tipo": ",".join(x.get("pubTypeList", {}).get("pubType", []))} for x in r["resultList"]["result"]]
    res["europepmc"].append({"consulta": q, "n": r["hitCount"], "items": items})
json.dump(res, open(os.path.join(D, "m2_proteomica_resultados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k in ("pubmed", "europepmc"):
    for b in res[k]:
        print(f"\n### {k.upper()} | {b['consulta']} -> {b['n']}")
        for it in b["items"][:60]:
            print("  ", it.get("pmid") or it.get("id"), it["anio"], it["titulo"][:150])
