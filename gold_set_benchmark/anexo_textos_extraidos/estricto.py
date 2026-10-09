import json, os, re, sys, time, unicodedata, urllib.request, urllib.parse, html
D = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(D, "inventario_final.json"), encoding="utf-8"))
UA = {"User-Agent": "tesis-goldset/1.0 (mailto:" + os.environ.get("GOLDSET_CONTACT_EMAIL", "you@example.com") + ")"}
def get(u):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as h:
                return json.load(h)
        except Exception:
            time.sleep(2)
def norm(s):
    s = re.sub(r"<[^>]+>", "", html.unescape(s or ""))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)  # sin espacios: tolera palabras pegadas
def score(title, region):
    t = norm(title); x = norm(region)
    if not t: return 0
    if t in x: return 1.0
    # proporcion de bloques de 12 caracteres del titulo presentes en la region
    chunks = [t[i:i+12] for i in range(0, max(1, len(t)-11), 6)]
    return sum(c in x for c in chunks) / len(chunks)
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>,;]+", re.I)
out = []
for r in rows:
    if not r["paginas"]: out.append(r); continue
    pages = json.load(open(os.path.join(D, "txt", r["archivo"][:-4] + ".json"), encoding="utf-8"))
    # region de titulo: primeros 3000 caracteres de las paginas 1 y 2 (portadas de preprint/manuscrito)
    region = (pages[0][:3000] + " " + (pages[1][:3000] if len(pages) > 1 else ""))
    ok = False
    if r["doi"]:
        msg = get("https://api.crossref.org/works/" + urllib.parse.quote(r["doi"]))
        t = (msg["message"].get("title") or [""])[0] if msg else ""
        sc = score(t, region)
        ok = sc >= 0.85
        r["chk"] = f"{sc:.2f}"
    if r["doi"] and not ok:
        # buscar DOI correcto: candidatos en region de titulo (sin saltos de linea) y en pagina 1 completa
        cands = []
        for m in DOI_RE.finditer((pages[0] + " " + (pages[1] if len(pages) > 1 else "")).replace("\n", "")):
            d = re.sub(r"(doi:|\.|\)|\])+$", "", m.group(0), flags=re.I)
            if d not in cands: cands.append(d)
        found = None
        for d in cands[:10]:
            msg = get("https://api.crossref.org/works/" + urllib.parse.quote(d))
            if not msg: continue
            t = (msg["message"].get("title") or [""])[0]
            if score(t, region) >= 0.85:
                y = (msg["message"].get("issued", {}).get("date-parts") or [[None]])[0][0]
                found = (msg["message"]["DOI"], re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(t))).strip(), y); break
        if found:
            r["nota"] = f"corregido (antes {r['doi']}, era una referencia citada)"
            r["doi"], r["titulo"], r["anio"] = found; r["pmid"] = ""
            ep = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&query=" + urllib.parse.quote(f'DOI:"{found[0]}"'))
            if ep and ep["resultList"]["result"]: r["pmid"] = ep["resultList"]["result"][0].get("pmid", "") or ""
            r["identidad"] = "confirmada"
        else:
            r["nota"] = f"DOI asignado {r['doi']} no corresponde al titulo del PDF; sin DOI propio legible"
            r["doi"] = ""; r["pmid"] = ""; r["identidad"] = "sin_confirmar"
            r["titulo"] = "(titulo PDF) " + re.sub(r"\s+", " ", pages[0][:160])
        print("REVISADO", r["archivo"][:60], "->", r["doi"], file=sys.stderr)
    out.append(r)
json.dump(out, open(os.path.join(D, "inventario_final.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"Done: {sum(r['identidad']=='confirmada' for r in out)} confirmadas de {len(out)}")
