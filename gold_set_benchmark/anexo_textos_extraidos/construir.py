# Construye el gold set y verifica mecanicamente cada pasaje.
# Verificacion: el pasaje (o cada fragmento separado por " [...] ") debe aparecer en el texto
# extraido con pypdf de la pagina declarada, tras eliminar solo espacios y saltos de linea.
import csv, json, os, re, urllib.request, urllib.parse

S = os.path.dirname(os.path.abspath(__file__))
TXT = os.path.join(S, "txt")
OUT = os.path.join(os.path.expanduser("~"), "Downloads", "gold_set_benchmark")
os.makedirs(OUT, exist_ok=True)
VAULT_PAPERS = "Obsidian Vault/Research/Papers/"
FECHA = "2026-10-07"
MODELO = "Claude Opus 5.5 (claude-opus-5-5)"

FAIR = "wilkinson_2016_fair_guiding_principles_sdata.2016.18"
RAD = "radmacher_2005_ethambutol_cglutamicum"
SCH = "schubert_2017_the_antituberculosis_drug_ethambutol_selectively_blocks_apical_growth"
MEY = "meyer_2023_effects_of_benzothiazinone_and_ethambutol_on_the_integrity"
LIM = "lim_2019_identification_of_new_components_of_the_ripc_ftsex"
DEV = "liang_2025_proteomic_characterization_mycobacterium_tuberculosis_drug_treatment"
ZHA = "zhang_2020_cryo_em_snapshots_mycobacterial_arabinosyltransferase_embb2_complex"
DOI = {FAIR: "10.1038/sdata.2016.18", RAD: "10.1099/mic.0.27804-0", SCH: "10.1128/mbio.02213-16",
       MEY: "10.1016/j.tcsw.2023.100116", LIM: "10.1371/journal.pgen.1008284",
       DEV: "10.1128/msystems.01530-24", ZHA: "10.1007/s13238-020-00726-6",
       "hart_2024_the_conserved_d_envelope_stress_response_monitors_multiple": "10.1371/journal.pgen.1011127"}
def ruta(b):
    return ("Downloads/gold_set_benchmark/" if b == FAIR else VAULT_PAPERS) + b + ".pdf"

_cache = {}
def paginas(b):
    if b not in _cache:
        _cache[b] = json.load(open(os.path.join(TXT, b + ".json"), encoding="utf-8"))
    return _cache[b]
def sinesp(s):
    return re.sub(r"\s+", "", s)
def verificar(b, pag, pasaje):
    pp = paginas(b)
    frags = [f for f in pasaje.split(" [...] ")]
    ok = all(sinesp(f) in sinesp(pp[pag - 1]) for f in frags)
    if ok:
        return "ok", ""
    otras = [i + 1 for i, p in enumerate(pp) if all(sinesp(f) in sinesp(p) for f in frags)]
    return "fallo", f"no aparece en p{pag}; aparece en {otras or 'ninguna pagina'}"

# ---------------------------------------------------------------- misiones
misiones = [
 {"id": "M1", "pregunta": "¿Qué establecen los principios FAIR para la gestión de datos científicos?",
  "subpreguntas": "", "fecha_corte_literatura": "2016-03-15 (fuente única: Wilkinson et al. 2016)",
  "armado_por": f"{MODELO}, {FECHA}", "archivos_usados": ruta(FAIR)},
 {"id": "M2", "pregunta": "¿Qué proteínas y procesos de Corynebacterium glutamicum se sabe que son afectados por el etambutol, y qué se desconoce sobre su efecto proteómico global?",
  "subpreguntas": "SQ1: ¿Cuál es el blanco molecular del etambutol en C. glutamicum y en qué difiere del de M. tuberculosis? | "
                  "SQ2: ¿Qué fenotipos y procesos celulares se describieron en C. glutamicum tratado con etambutol, y bajo qué condiciones? | "
                  "SQ3: ¿Qué genes o proteínas modulan la sensibilidad de C. glutamicum al etambutol? | "
                  "SQ4: ¿Qué se desconoce del efecto global del etambutol sobre el proteoma, y hasta dónde es trasladable a M. tuberculosis?",
  "fecha_corte_literatura": f"{FECHA} (PDFs de la carpeta, publicados entre 2005 y 2026)",
  "armado_por": f"{MODELO}, {FECHA}",
  "archivos_usados": "; ".join(ruta(b) for b in [RAD, SCH, MEY, LIM, DEV, ZHA, "hart_2024_the_conserved_d_envelope_stress_response_monitors_multiple"])},
 {"id": "M3", "pregunta": "¿Qué proteínas cambian significativamente de abundancia en Corynebacterium glutamicum expuesto a concentraciones subinhibitorias de etambutol, medidas por proteómica cuantitativa?",
  "subpreguntas": "", "fecha_corte_literatura": f"{FECHA} (búsqueda en PubMed y Europe PMC)",
  "armado_por": f"{MODELO}, {FECHA}", "archivos_usados": "busqueda_control_negativo.md"},
]

# ---------------------------------------------------------------- afirmaciones de referencia
ref = [
 # M1
 ("M1", "", "FAIR define cuatro principios fundacionales: Findability, Accessibility, Interoperability y Reusability (encontrabilidad, accesibilidad, interoperabilidad y reutilización), pensados para guiar a productores y publicadores de datos.",
  FAIR, 1, "This article describes four foundational principles — Findability, Accessibility, Interoperability, and Reusability— that serve to guide data producers and publishers"),
 ("M1", "", "A diferencia de iniciativas centradas en el investigador humano, FAIR pone énfasis específico en que las máquinas puedan encontrar y usar los datos automáticamente, además de apoyar su reutilización por personas.",
  FAIR, 1, "the FAIR Principles put speci ﬁc emphasis on enhancing the ability of machines to automatically ﬁnd and use the data, in addition to supporting its reuse by individuals."),
 ("M1", "", "Los principios se aplican no solo a los datos en sentido convencional, sino también a los algoritmos, herramientas y flujos de trabajo que los generaron.",
  FAIR, 1, "it is our intent that the principles apply not only to ‘data’ in the conventional sense, but also to the algorithms, tools, and work ﬂows that led to that data."),
 ("M1", "", "Para ser encontrables (F1), los datos y metadatos deben tener asignado un identificador global único y persistente.",
  FAIR, 4, "F1. (meta)data are assigned a globally unique and persistent identi ﬁer"),
 ("M1", "", "Los principios FAIR preceden a las decisiones de implementación: no prescriben ninguna tecnología, estándar ni solución concreta, y no son en sí mismos un estándar ni una especificación.",
  FAIR, 5, "These high-level FAIR Guiding Principles precede implementation choices, and do not suggest any speciﬁc technology, standard, or implementation-solution; moreover, the Principles are not, themselves, a standard or a speci ﬁcation."),
 # M2
 ("M2", "SQ1", "Las especies de Corynebacterium tienen un único gen emb, mientras que M. tuberculosis y M. avium tienen tres; en estas micobacterias se sugiere que al menos uno de ellos (embB) es el blanco del etambutol.",
  RAD, 4, "Mycobacterium avium and M. tuberculosis have three emb genes, and at least one of these ( embB) is suggested to be the target of EMB (Escuyer et al ., 2001). However, Coryne- bacterium species have only one emb gene."),
 ("M2", "SQ3", "En C. glutamicum, sobreexpresar su único gen emb (más parecido a embC micobacteriano que a embA o embB) fue suficiente para conferir resistencia al etambutol.",
  RAD, 4, "overexpression of the single emb gene of C. glutamicum, which is more related to the mycobacterial embC than to embA or embB,w a s sufﬁcient to confer EMB resistance."),
 ("M2", "SQ2", "En C. glutamicum, el etambutol redujo el depósito de arabinano en el arabinogalactano de la pared y el contenido de ácidos micólicos unidos a la pared.",
  RAD, 1, "(iii) EMB caused less arabinan deposition in cell wall arabinogalactan, and (iv) EMB caused a reduced content of cell-wall-bound mycolic acids."),
 ("M2", "SQ2", "En C. glutamicum, tanto el tratamiento con etambutol como la deleción de pks (síntesis de ácidos micólicos) indujeron fuertemente un reportero de la vía de estrés de envoltura σD (19,1 y 10,8 veces, respectivamente).",
  "hart_2024_the_conserved_d_envelope_stress_response_monitors_multiple", 8,
  "Both ethambutol (EMB) treatment to disrupt AG synthesis and deletion ofpks, a homolog ofMtbpks13 that encodes an enzyme required for mycolic acid syn- thesis, resulted in strong induction of the reporter (19.1-fold and 10.8-fold increases, respec- tively for EMB and Δpks)"),
 ("M2", "SQ4", "Radmacher et al. midieron la respuesta global de C. glutamicum al etambutol a nivel transcriptómico, con microarreglos de ADN y no por proteómica: 76 genes con expresión diferencial, 18 inducidos más de ocho veces (entre ellos ftsE y mepA), y casi ningún gen del metabolismo central.",
  RAD, 1, "genome-wide expression proﬁling was performed using DNA microarrays. This identiﬁed 76 differentially expressed genes, with 18 of them upregulated more than eightfold. Among these were the cell-wall-related genes ftsE and mepA (encoding a secreted metalloprotease); however, genes of central metabolism were largely absent."),
 ("M2", "SQ2", "En C. glutamicum y M. phlei, el etambutol bloquea específicamente la síntesis apical (polar) de pared celular, pero no la división celular, lo que explica su efecto bacteriostático.",
  SCH, 1, "Here, we used Corynebacterium glutamicum and Mycobacterium phlei as model organisms to study the effects of EMB at the single-cell level. Our results demonstrate that EMB speciﬁcally blocks apical cell wall synthesis, but not cell divi- sion, explaining the bacteriostatic effect of EMB."),
 ("M2", "SQ2", "En C. glutamicum tratado con etambutol aumenta el nivel de la proteína DivIVA (confirmado por inmunoblot), mientras que su ARNm no cambia (dato no mostrado por los autores).",
  SCH, 5, "DivIVA mRNA levels, and thus transcription rates, were not altered upon the addition of EMB (data not shown). [...] Immunoblotting with antibodies directed against the mCherry protein conﬁrmed the increase in DivIVA levels"),
 ("M2", "SQ2", "Las células de C. glutamicum tratadas con una concentración subletal de etambutol pierden la integridad de la micomembrana (hallazgo previo del mismo grupo, que Meyer et al. resumen) y, según Meyer et al., presentan un peptidoglicano más grueso y menos electrodenso.",
  MEY, 1, "We previously showed that C. glutamicum cells treated with a sublethal concentration of EMB lose the integrity of the MM. [...] In addition, we observed that EMB treated cells have a thicker and less electron dense peptidoglycan (PG)."),
 ("M2", "SQ3", "Un cribado por Tn-seq en C. glutamicum identificó loci cuya inactivación causa hipersensibilidad al etambutol, entre ellos ripC, el complejo FtsEX y los genes conservados steAB.",
  LIM, 1, "we generated the first high-density library of transposon inser- tion mutants in the model organism C. glutamicum. Transposon-sequencing was then used to define its essential gene set and identify loci that, when inactivated, confer hypersensitiv- ity to ethambutol (EMB), a drug that targets AG biogenesis. Among the EMBs loci were genes encoding RipC and the FtsEX complex [...] Inactivation of the conserved steAB genes (cgp_1603–1604) was also found to confer EMB hypersensitivity and cell division defects."),
 ("M2", "SQ4", "A diferencia de las micobacterias, en C. glutamicum las capas de arabinogalactano y micomembrana no son esenciales para la viabilidad; por eso su pérdida tras el tratamiento con etambutol no es el mecanismo directo de muerte en este organismo.",
  MEY, 2, "In C. glutamicum the AG/ MM layers are not essential for viability, which is in stark contrast to Mycobacteria. This implies that loss of AG/MM integrity in C. glutamicum upon EMB or BTZ treatment is not the direct mechanism for killing."),
]

# ---------------------------------------------------------------- prohibidas
proh = [
 ("M1", "FAIR significa Findable, Accessible, Interoperable y Reproducible.",
  "La R corresponde a Reusable (reutilizable), no a Reproducible; la confusión es frecuente porque el texto habla de reproducibilidad.",
  FAIR, 2, "FAIR— Findable, Accessible, Interoperable, Reusable."),
 ("M1", "Para cumplir con FAIR, los datos deben publicarse en acceso abierto y gratuito, sin restricciones de acceso.",
  "FAIR no exige acceso abierto: el protocolo de acceso puede incluir autenticación y autorización, y en datos sensibles basta con publicar metadatos ricos y reglas claras de acceso. Lo que debe ser abierto y gratuito (A1.1) es el protocolo, no los datos.",
  FAIR, 4, "A1.2 the protocol allows for an authentication and authorization procedure, where necessary [...] One such example is highly sensitive or personally-identi ﬁable data, where publication of rich metadata to facilitate discovery, including clear rules regarding the process for accessing the data, provides a high degree of ‘FAIRness’ even in the absence of FAIR publication of the data itself."),
 ("M2", "Un estudio proteómico de 2025 (archivo liang_2025, Devlin et al.) mostró que el tratamiento con etambutol aumenta más de dos veces la abundancia de EmbA y EmbC en M. tuberculosis.",
  "Ese estudio no trata a M. tuberculosis con etambutol: la condición es ayuno de carbono. Los autores dicen que hacen falta más estudios para saber si ese aumento contribuye a la resistencia. El nombre del archivo induce al error.",
  DEV, 13, "The A and C subunits were both >2-fold more abundant in CS."),
 ("M2", "En C. glutamicum, el etambutol reprime los genes del metabolismo central.",
  "Convierte en efecto una ausencia. Radmacher et al. destacan que ningún gen de enzimas del metabolismo central se ve afectado a nivel de ARNm; solo bajan levemente odhA y lpd. Además, el dato es transcriptómico, no proteómico.",
  RAD, 9, "With respect to the consequences of EMB addition on the mRNA levels of cytosolic enzymes, it is striking that no genes for enzymes of central metabolism are affected."),
 ("M2", "El etambutol induce la transcripción de divIVA en C. glutamicum, y por eso aumenta la proteína DivIVA.",
  "Le atribuye al efecto un mecanismo transcripcional. Schubert et al. informan que el ARNm de divIVA no cambia y proponen que la proteína se acumula por falta de crecimiento polar.",
  SCH, 5, "DivIVA mRNA levels, and thus transcription rates, were not altered upon the addition of EMB (data not shown)."),
 ("M2", "La pérdida de integridad de la micomembrana y el engrosamiento del peptidoglicano por etambutol (Meyer et al. 2023) se observaron en C. glutamicum cultivado en medio mínimo CGXII.",
  "Confunde el medio. Meyer et al. cultivaron en BHI (complejo) con 10 µg/ml de etambutol. Es justamente el error que hay que evitar al compararlos con experimentos propios en CGXII.",
  MEY, 3, "rodA::rodA-eYFP were cultivated in BHI medium (Oxoid) [...] EMB added in the same way was used at 10 µg/ml."),
 ("M3", "No existe ningún estudio proteómico del efecto del etambutol en micobacterias ni en organismos relacionados.",
  "Generaliza la ausencia. Lo que falta es el estudio en C. glutamicum. En M. smegmatis hay al menos dos estudios proteómicos con etambutol (PMID 18275136, proteómica shotgun de 2008; PMID 20686769, 2D-DIGE de 2011), que están fuera de la carpeta.",
  None, None, "Sin pasaje en PDF de la carpeta. Evidencia: resúmenes de PMID 18275136 y 20686769 en Europe PMC (ver busqueda_control_negativo.md)."),
]

# ---------------------------------------------------------------- escribir
def wcsv(nombre, campos, filas):
    with open(os.path.join(OUT, nombre), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=campos); w.writeheader(); w.writerows(filas)

wcsv("misiones.csv", ["id", "pregunta", "subpreguntas", "fecha_corte_literatura", "armado_por", "archivos_usados"], misiones)

filas_ref, fallos = [], []
cont = {"M1": 0, "M2": 0}
for m, sq, af, b, p, pas in ref:
    cont[m] += 1
    v, det = verificar(b, p, pas)
    if v != "ok": fallos.append((m, af, det))
    filas_ref.append({"id": f"{m}-R{cont[m]:02d}", "mision": m, "subpregunta": sq, "afirmacion": af, "doi_fuente": DOI[b],
                      "archivo_pdf": ruta(b), "pagina": p, "pasaje_literal": pas, "verificacion_mecanica": v})
wcsv("afirmaciones_referencia.csv", ["id", "mision", "subpregunta", "afirmacion", "doi_fuente", "archivo_pdf", "pagina", "pasaje_literal", "verificacion_mecanica"], filas_ref)

filas_p, cont = [], {}
for m, af, por, b, p, pas in proh:
    cont[m] = cont.get(m, 0) + 1
    if b:
        v, det = verificar(b, p, pas)
        if v != "ok": fallos.append((m, af, det))
        pasaje = f"{pas} (p. {p}, {ruta(b)}; verificación mecánica: {v})"
    else:
        pasaje = pas
    filas_p.append({"id": f"{m}-P{cont[m]:02d}", "mision": m, "afirmacion_incorrecta": af, "por_que_es_incorrecta": por,
                    "pasaje_que_la_contradice_o_limita": pasaje})
wcsv("afirmaciones_prohibidas.csv", ["id", "mision", "afirmacion_incorrecta", "por_que_es_incorrecta", "pasaje_que_la_contradice_o_limita"], filas_p)

json.dump({"ref": filas_ref, "proh": filas_p, "fallos": fallos}, open(os.path.join(S, "goldset_estado.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"Done: {len(filas_ref)} referencia, {len(filas_p)} prohibidas, {len(fallos)} fallos")
for f in fallos: print("FALLO", f)
