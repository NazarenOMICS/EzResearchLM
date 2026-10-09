import csv, json, os, urllib.request, urllib.parse, importlib.util, io, contextlib
S = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("c", os.path.join(S, "construir.py")); c = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(c)
OUT = c.OUT
UA = {"User-Agent": "tesis-goldset/1.0 (mailto:" + os.environ.get("GOLDSET_CONTACT_EMAIL", "you@example.com") + ")"}
def epmc(doi):
    u = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&query=" + urllib.parse.quote(f'DOI:"{doi}"')
    r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))["resultList"]["result"]
    return r[0] if r else {}

# ---------------------------------------------------------------- articulos clave
clave = [
 ("M1", "10.1038/sdata.2016.18", "The FAIR Guiding Principles for scientific data management and stewardship", 2016, "Primera publicación formal de los principios FAIR; es la fuente única de M1.", "confirmada"),
 ("M2", "10.1099/mic.0.27804-0", "Ethambutol, a cell wall inhibitor of Mycobacterium tuberculosis, elicits L-glutamate efflux of Corynebacterium glutamicum", 2005, "Único trabajo del corpus con una respuesta global (transcriptómica) de C. glutamicum al etambutol; además: un único gen emb, arabinano, ácidos micólicos y eflujo de glutamato en CGXII.", "confirmada"),
 ("M2", "10.1128/mbio.02213-16", "The Antituberculosis Drug Ethambutol Selectively Blocks Apical Growth in CMN Group Bacteria", 2017, "Fenotipo celular del etambutol en C. glutamicum (bloqueo del crecimiento apical, acumulación de DivIVA, RodA mal localizada); en BHI.", "confirmada"),
 ("M2", "10.1016/j.tcsw.2023.100116", "Effects of benzothiazinone and ethambutol on the integrity of the corynebacterial cell envelope", 2023, "Integridad de la micomembrana y del peptidoglicano bajo etambutol; muestra que el AG y la micomembrana no son esenciales en C. glutamicum. Mismo grupo que Schubert 2017.", "confirmada"),
 ("M2", "10.1371/journal.pgen.1008284", "Identification of new components of the RipC-FtsEX cell separation pathway of Corynebacterineae", 2019, "Tn-seq con etambutol subletal en C. glutamicum: genes que modulan la sensibilidad (ripC, ftsEX, steAB).", "confirmada"),
 ("M2", "10.1371/journal.pone.0240497", "Genome-wide identification of novel genes involved in Corynebacteriales cell envelope biogenesis using Corynebacterium glutamicum as a model", 2020, "Cribado genómico de genes de envoltura en C. glutamicum desde otro grupo de investigación; sitúa el cribado de Lim et al.", "confirmada"),
 ("M2", "10.1371/journal.pgen.1011127", "The conserved σD envelope stress response monitors multiple aspects of envelope integrity in corynebacteria", 2024, "El etambutol activa la respuesta de estrés σD en C. glutamicum: es una vía regulatoria concreta afectada por el fármaco.", "confirmada"),
 ("M2", "10.1016/j.tcsw.2018.06.003", "The singular Corynebacterium glutamicum Emb arabinofuranosyltransferase polymerises the α(1 → 5) arabinan backbone in the early stages of cell wall arabinan biosynthesis", 2018, "Caracteriza la función de la Emb única de C. glutamicum, el blanco del fármaco. NO está en la carpeta.", "confirmada"),
 ("M2", "10.1007/s13238-020-00726-6", "Cryo-EM snapshots of mycobacterial arabinosyltransferase complex EmbB2-AcpM2", 2020, "Base estructural del blanco en micobacterias (EmbB de M. smegmatis) y mapeo de mutaciones de resistencia.", "confirmada"),
 ("M2", "10.1128/msystems.01530-24", "Proteomic characterization of Mycobacterium tuberculosis subjected to carbon starvation", 2025, "Proteómica DIA de M. tuberculosis en la que cambian EmbA y EmbC, pero en ayuno de carbono y no con etambutol: sirve de control contra extrapolaciones. El archivo está mal nombrado (liang_2025).", "confirmada"),
 ("M2", "10.1021/pr0703066", "The proteomic response of Mycobacterium smegmatis to anti-tuberculosis drugs suggests targeted pathways.", 2008, "Proteómica shotgun de M. smegmatis con etambutol entre otros fármacos: es el antecedente proteómico más cercano. NO está en la carpeta.", "confirmada"),
 ("M2", "10.1007/s00284-010-9711-5", "The novel responses of ethambutol against Mycobacterium smegmatis mc²155 Revealed by proteomics analysis.", 2011, "Proteómica 2D-DIGE de M. smegmatis con etambutol. NO está en la carpeta.", "confirmada"),
]
filas = []
for m, doi, tit, an, porque, idn in clave:
    r = epmc(doi)
    oa = {"Y": "si", "N": "no"}.get(r.get("isOpenAccess", ""), "desconocido")
    filas.append({"mision": m, "doi": doi, "pmid": r.get("pmid", ""), "titulo": tit, "anio": an,
                  "por_que_es_clave": porque, "acceso_abierto": oa, "identidad": idn})
with open(os.path.join(OUT, "articulos_clave.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)

# ---------------------------------------------------------------- lagunas
lag = [
 ("M1", "Cómo medir o certificar cuantitativamente el grado de FAIRness de un recurso (métricas, indicadores de madurez).", "fuera_de_la_bibliografia",
  "El artículo dice que los principios no son un estándar ni prescriben tecnología (p. 5) y remite las guías de implementación a un documento aparte, en construcción (p. 4)."),
 ("M2", "Qué proteínas cambian de abundancia en C. glutamicum tratado con etambutol, a escala de proteoma.", "sin_estudios",
  "PubMed: 0 resultados para ethambutol + glutamicum + proteom*/mass spectrometry. Europe PMC: ningún título o resumen relevante (busqueda_control_negativo.md). La única medición global en C. glutamicum es transcriptómica (Radmacher 2005, p. 1)."),
 ("M2", "Respuesta proteómica al etambutol en micobacterias modelo (M. smegmatis) para comparar con C. glutamicum.", "fuera_de_la_bibliografia",
  "Existen PMID 18275136 (2008) y PMID 20686769 (2011), pero no están en la carpeta del proyecto. Ninguno de los dos aparece como de acceso abierto en Europe PMC."),
 ("M2", "Estructura de EmbA-EmbB de M. tuberculosis con etambutol unido y modo de unión del fármaco.", "fuera_de_la_bibliografia",
  "Zhang 2020 (Protein Cell) solo superpone su EmbB2 de M. smegmatis sobre una estructura publicada aparte; esa estructura no está en la carpeta (p. 11)."),
 ("M2", "Función bioquímica de la Emb única de C. glutamicum (qué enlaces de arabinano polimeriza).", "fuera_de_la_bibliografia",
  "Jankute et al. 2018 (10.1016/j.tcsw.2018.06.003) aparece en la búsqueda pero no está en la carpeta."),
 ("M2", "Contenido de cinco PDFs de la carpeta: solo contienen material suplementario o checklists, sin el artículo (Blevins 2024, Greaves 2023, Garaeva 2026, Tan/Zhao 2020 EmbB y FtsB-PerM 2025).", "fuera_de_la_bibliografia",
  "Primera página de cada PDF: 'Supplementary Figures', 'Supplementary Materials' o 'MDAR Checklist' (ver inventario)."),
 ("M2", "Concentraciones exactas de etambutol en Radmacher 2005 y en partes de Schubert 2017: la extracción de texto pierde el símbolo µ y las unidades son ambiguas.", "datos_contradictorios",
  "Radmacher p. 3 dice '500 mg EMB ml 21' y p. 6 dice '500 mg EMB l 21' para el mismo experimento; Schubert p. 3 alterna '1 mg · ml' y '1 /H9262g·m l'. Hay que leerlas en el PDF original."),
 ("M3", "Toda la pregunta: perfil proteómico cuantitativo de C. glutamicum bajo etambutol subinhibitorio.", "sin_estudios",
  "Ver busqueda_control_negativo.md: 7 consultas en PubMed y Europe PMC, sin estudios que respondan la pregunta."),
]
with open(os.path.join(OUT, "lagunas_esperadas.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh); w.writerow(["mision", "que_no_se_puede_responder", "causa", "evidencia_de_la_causa"]); w.writerows(lag)

# ---------------------------------------------------------------- dudosas
dud = [
 ("M2", "La CIM (Etest) del etambutol para C. glutamicum silvestre es 0,75 µg/ml, y 1,5 µg/ml en la cepa que sobreexpresa emb.", c.RAD, 4,
  "The MIC (Etest) of EMB for the wild-type was 0?75 mgm l 21, and for the overexpressing strain it was 1?5 mgm l 21.",
  "La unidad se perdió en la extracción ('mgm l 21'); no se puede asegurar si es µg/ml sin ver el PDF original."),
 ("M2", "En C. glutamicum tratado con etambutol aparecen en el sobrenadante las micoliltransferasas CmytA y CmytC.", c.RAD, 3,
  "we detected proteins in supernatants analysed at the end of cultivations that were absent in untreated cultures. These were, in addition to the mycolyltransferases CmytA and CmytC",
  "Los mismos autores dicen que otras proteínas del sobrenadante indican lisis parcial; no queda claro si es liberación específica o lisis."),
 ("M2", "El etambutol aumenta el nivel de la proteína RodA en C. glutamicum.", c.SCH, 4,
  "RodA is mislocalized, and the protein level seems to increase upon the addition of EMB.",
  "La leyenda de la figura dice 'seems' y no hay cuantificación; la mala localización es firme, el aumento no."),
 ("M2", "Agregar etambutol a cultivos de C. glutamicum en crecimiento provoca eflujo de L-glutamato, que no ocurre sin el fármaco.", c.RAD, 1,
  "addition of ethambutol (EMB) to growing cultures of C. glutamicum causes L-glutamate efﬂux [...] whereas in the absence of EMB, no efﬂux occurs.",
  "No hay duda sobre el pasaje: se sacó de las referencias para que Radmacher 2005 no aporte la mitad de M2. Puede volver si se prefiere este dato a Hart 2024."),
]
filas = []
for m, af, b, p, pas, mot in dud:
    v, _ = c.verificar(b, p, pas)
    filas.append({"mision": m, "afirmacion": af, "archivo_pdf": c.ruta(b), "pagina": p, "pasaje_literal": pas, "verificacion_mecanica": v, "motivo_de_duda": mot})
with open(os.path.join(OUT, "dudosas.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
print("Done: articulos/lagunas/dudosas;", [f["verificacion_mecanica"] for f in filas])
