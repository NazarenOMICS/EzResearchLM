import os, re, json, sys, time, urllib.request, urllib.parse, difflib, unicodedata
from pypdf import PdfReader

VAULT = r"C:\Users\Administrator\Documents\Obsidian Vault"
PAPERS = os.path.join(VAULT, "Research", "Papers")
NB = os.path.join(VAULT, "Notes", "NotebookLM")
OUT = os.path.dirname(os.path.abspath(__file__))
TXT = os.path.join(OUT, "txt")
os.makedirs(TXT, exist_ok=True)

blocks = ["tb-intro-bloque-1-1", "tb-bloque-1-2", "tb-bloque-1-3", "tb-bloque-1-4", "tb-bloque-1-5"]
names = {}
for b in blocks:
    for f in os.listdir(os.path.join(NB, b, "Sources")):
        base = re.sub(r"(\.(pdf|md))+$", "", f)
        names.setdefault(base, []).append(b.replace("tb-intro-bloque-", "").replace("tb-bloque-", ""))
extras = ["radmacher_2005_ethambutol_cglutamicum", "kwon_2018_MIC_ethambutol_MAC", "sharma_2021_NTM_REMA",
          "Frey2025_DIA evaluation with CQEs or LFQ", "mohamoud_2026_tuberculosis_in_somalia_a_narrative_review_of_epidemiology",
          "steffanie_2020_confronting_antimicrobial_resistance_beyond_the_covid_19_pandemic", "europepmc_PMID_36002805",
          "scidb_10.1177_01945998211029527",
          "2023 - Koch et al - Growth-rate dependency of ribosome abundance and translation elongation rate in Corynebacterium glutamicum differs from that in Escherichia coli"]
for e in extras:
    names.setdefault(e, ["fuera_de_bloque"])

UA = {"User-Agent": "tesis-goldset/1.0 (mailto:nazarenocabrerati@gmail.com)"}
def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as ex:
            err = ex; time.sleep(2)
    return None

def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def title_in_text(title, text):
    t, x = norm(title), norm(text)
    if not t: return 0.0
    if t in x: return 1.0
    words = t.split()
    hits = sum(1 for w in words if w in x.split())
    return hits / len(words)

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>,;]+)", re.I)
rows = []
for base, blks in sorted(names.items()):
    pdf = os.path.join(PAPERS, base + ".pdf")
    r = {"archivo": base + ".pdf", "bloques": ",".join(blks), "paginas": "", "doi": "", "pmid": "", "titulo": "",
         "anio": "", "identidad": "sin_confirmar", "metodo": "", "nota": ""}
    if not os.path.exists(pdf):
        r["nota"] = "PDF no encontrado en Research/Papers"; rows.append(r); continue
    try:
        rd = PdfReader(pdf)
        pages = [(p.extract_text() or "") for p in rd.pages]
    except Exception as ex:
        r["nota"] = f"error extraccion: {ex}"; rows.append(r); continue
    r["paginas"] = len(pages)
    with open(os.path.join(TXT, base + ".json"), "w", encoding="utf-8") as fh:
        json.dump(pages, fh, ensure_ascii=False)
    full = "\n".join(pages)
    if len(full.strip()) < 500:
        r["nota"] = "sin capa de texto (posible escaneo)"
    head = "\n".join(pages[:2])
    if not DOI_RE.search(head.replace("\n", " ")):
        head = "\n".join(pages[:2] + pages[-2:])
    cands = []
    for m in DOI_RE.finditer(head.replace("\n", " ")):
        d = m.group(1).rstrip(".)]")
        if d.lower() not in [c.lower() for c in cands]: cands.append(d)
    # filename-encoded DOI
    m = re.match(r"scidb_(10\.\d+)_(.+)", base)
    if m: cands.insert(0, m.group(1) + "/" + m.group(2))
    best = None
    for d in cands[:6]:
        cr = get("https://api.crossref.org/works/" + urllib.parse.quote(d))
        if not cr: continue
        msg = cr["message"]; title = (msg.get("title") or [""])[0]
        score = title_in_text(title, head)
        if best is None or score > best[0]:
            best = (score, d, title, msg)
        if score == 1.0: break
    if best and best[0] >= 0.9:
        sc, d, title, msg = best
        r.update(doi=msg["DOI"], titulo=title, identidad="confirmada",
                 metodo=f"DOI en PDF + Crossref (coincidencia titulo {sc:.2f})")
        yr = (msg.get("issued", {}).get("date-parts") or [[None]])[0][0]
        r["anio"] = yr or ""
    else:
        if best: r["nota"] += f" DOI candidato {best[1]} con baja coincidencia de titulo ({best[0]:.2f});"
        else: r["nota"] += " sin DOI legible en p1-2;"
    # PMID via Europe PMC
    if r["doi"]:
        ep = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&query=" +
                 urllib.parse.quote(f'DOI:"{r["doi"]}"'))
        if ep and ep.get("resultList", {}).get("result"):
            r["pmid"] = ep["resultList"]["result"][0].get("pmid", "") or ""
    elif base.startswith("europepmc_PMID_"):
        pm = base.split("_")[-1]
        ep = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&query=" + urllib.parse.quote(f"EXT_ID:{pm} AND SRC:MED"))
        if ep and ep["resultList"]["result"]:
            res = ep["resultList"]["result"][0]
            sc = title_in_text(res.get("title", ""), head)
            if sc >= 0.9:
                r.update(pmid=pm, doi=res.get("doi", ""), titulo=res.get("title", ""), anio=res.get("pubYear", ""),
                         identidad="confirmada", metodo=f"PMID en nombre + Europe PMC (titulo {sc:.2f})")
    rows.append(r)
    print(base[:60], r["identidad"], r["doi"], file=sys.stderr)

with open(os.path.join(OUT, "inventario.json"), "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)
print(f"Done: {len(rows)} filas, {sum(r['identidad']=='confirmada' for r in rows)} confirmadas")
