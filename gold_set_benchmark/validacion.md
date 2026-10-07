# Validación humana del gold set

> **Versión 2.** Cambios respecto de la versión 1 en `CAMBIOS.md`: M3 tiene una pregunta nueva (sección B), M2-R07 precisa que se midió la fusión DivIVA-mCherry, Devlin 2025 dejó de ser artículo clave y dos lagunas pasaron a `notas_corpus.md`. La verificación mecánica se reejecuta con `python verificar_pasajes.py`.

Revisá cada ítem contra el PDF original y marcá la casilla solo si el pasaje sostiene **exactamente** la afirmación: misma especie, cepa, medio, condición y fuerza causal.

**Convenciones:**
- *Página* es el número de página dentro del archivo PDF (1 = primera página del archivo), que puede no coincidir con la numeración de la revista.
- *Pasaje literal* es el texto tal como lo extrae pypdf 6.19, con ligaduras (ﬁ, ﬂ) y espacios espurios incluidos. `[...]` separa fragmentos no contiguos de la misma página.
- *Verificación mecánica*: cada fragmento aparece en el texto de esa página después de eliminar solo espacios y saltos de línea. Probé el verificador con un pasaje alterado y con una página equivocada, y en los dos casos falló como debía.

El orden va de mayor a menor riesgo: referencias de M2, prohibidas de M2 y M3, dudosas, y por último M1.

## A. Afirmaciones de referencia de M2 (mayor riesgo)

### 1. M2-R01 (SQ1)

**Afirmación:** Las especies de Corynebacterium tienen un único gen emb, mientras que M. tuberculosis y M. avium tienen tres; en estas micobacterias se sugiere que al menos uno de ellos (embB) es el blanco del etambutol.

**Pasaje:** «Mycobacterium avium and M. tuberculosis have three emb genes, and at least one of these ( embB) is suggested to be the target of EMB (Escuyer et al ., 2001). However, Coryne- bacterium species have only one emb gene.»

Fuente: `Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf`, p. 4 · DOI 10.1099/mic.0.27804-0 · verificación mecánica: **ok**

- [ ] el pasaje sostiene exactamente esto

### 2. M2-R02 (SQ3)

**Afirmación:** En C. glutamicum, sobreexpresar su único gen emb (más parecido a embC micobacteriano que a embA o embB) fue suficiente para conferir resistencia al etambutol.

**Pasaje:** «overexpression of the single emb gene of C. glutamicum, which is more related to the mycobacterial embC than to embA or embB,w a s sufﬁcient to confer EMB resistance.»

Fuente: `Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf`, p. 4 · DOI 10.1099/mic.0.27804-0 · verificación mecánica: **ok**

- [ ] el pasaje sostiene exactamente esto

### 3. M2-R03 (SQ2)

**Afirmación:** En C. glutamicum, el etambutol redujo el depósito de arabinano en el arabinogalactano de la pared y el contenido de ácidos micólicos unidos a la pared.

**Pasaje:** «(iii) EMB caused less arabinan deposition in cell wall arabinogalactan, and (iv) EMB caused a reduced content of cell-wall-bound mycolic acids.»

Fuente: `Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf`, p. 1 · DOI 10.1099/mic.0.27804-0 · verificación mecánica: **ok**

Nota: el trabajo usa medio mínimo CGXII con glucosa (Radmacher p. 2). Las concentraciones del experimento bioquímico tienen unidades ilegibles en la extracción; ver dudosas.

- [ ] el pasaje sostiene exactamente esto

### 4. M2-R04 (SQ2)

**Afirmación:** En C. glutamicum, tanto el tratamiento con etambutol como la deleción de pks (síntesis de ácidos micólicos) indujeron fuertemente un reportero de la vía de estrés de envoltura σD (19,1 y 10,8 veces, respectivamente).

**Pasaje:** «Both ethambutol (EMB) treatment to disrupt AG synthesis and deletion ofpks, a homolog ofMtbpks13 that encodes an enzyme required for mycolic acid syn- thesis, resulted in strong induction of the reporter (19.1-fold and 10.8-fold increases, respec- tively for EMB and Δpks)»

Fuente: `Obsidian Vault/Research/Papers/hart_2024_the_conserved_d_envelope_stress_response_monitors_multiple.pdf`, p. 8 · DOI 10.1371/journal.pgen.1011127 · verificación mecánica: **ok**

Nota: es la inducción de un reportero transcripcional (Pcgp_2320::lacZ), no un nivel proteico. En la misma página, otro experimento con la cepa silvestre da 15 veces. El pasaje no nombra la especie: que el reportero está en C. glutamicum surge del resumen (Hart p. 1).

- [ ] el pasaje sostiene exactamente esto

### 5. M2-R05 (SQ4)

**Afirmación:** Radmacher et al. midieron la respuesta global de C. glutamicum al etambutol a nivel transcriptómico, con microarreglos de ADN y no por proteómica: 76 genes con expresión diferencial, 18 inducidos más de ocho veces (entre ellos ftsE y mepA), y casi ningún gen del metabolismo central.

**Pasaje:** «genome-wide expression proﬁling was performed using DNA microarrays. This identiﬁed 76 differentially expressed genes, with 18 of them upregulated more than eightfold. Among these were the cell-wall-related genes ftsE and mepA (encoding a secreted metalloprotease); however, genes of central metabolism were largely absent.»

Fuente: `Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf`, p. 1 · DOI 10.1099/mic.0.27804-0 · verificación mecánica: **ok**

Nota: microarreglos en CGXII (Radmacher p. 3). Es ARNm, no proteína.

- [ ] el pasaje sostiene exactamente esto

### 6. M2-R06 (SQ2)

**Afirmación:** En C. glutamicum y M. phlei, el etambutol bloquea específicamente la síntesis apical (polar) de pared celular, pero no la división celular, lo que explica su efecto bacteriostático.

**Pasaje:** «Here, we used Corynebacterium glutamicum and Mycobacterium phlei as model organisms to study the effects of EMB at the single-cell level. Our results demonstrate that EMB speciﬁcally blocks apical cell wall synthesis, but not cell divi- sion, explaining the bacteriostatic effect of EMB.»

Fuente: `Obsidian Vault/Research/Papers/schubert_2017_the_antituberculosis_drug_ethambutol_selectively_blocks_apical_growth.pdf`, p. 1 · DOI 10.1128/mbio.02213-16 · verificación mecánica: **ok**

Nota: Schubert usa medio BHI.

- [ ] el pasaje sostiene exactamente esto

### 7. M2-R07 (SQ2)

**Afirmación:** En C. glutamicum tratado con etambutol aumenta el nivel de la fusión DivIVA-mCherry expresada desde el locus nativo (confirmado por inmunoblot contra mCherry), mientras que el ARNm de divIVA no cambia (dato no mostrado por los autores).

**Pasaje:** «DivIVA mRNA levels, and thus transcription rates, were not altered upon the addition of EMB (data not shown). [...] Immunoblotting with antibodies directed against the mCherry protein conﬁrmed the increase in DivIVA levels»

Fuente: `Obsidian Vault/Research/Papers/schubert_2017_the_antituberculosis_drug_ethambutol_selectively_blocks_apical_growth.pdf`, p. 5 · DOI 10.1128/mbio.02213-16 · verificación mecánica: **ok**

Nota: el ARNm sin cambios es un dato no mostrado por los autores. Medio BHI. En v2 se agregó que la medición es de la fusión DivIVA-mCherry (Schubert p. 5: "Allelic replacement of divIVA at the native locus with an mCherry fusion gene").

- [ ] el pasaje sostiene exactamente esto

### 8. M2-R08 (SQ2)

**Afirmación:** Las células de C. glutamicum tratadas con una concentración subletal de etambutol pierden la integridad de la micomembrana (hallazgo previo del mismo grupo, que Meyer et al. resumen) y, según Meyer et al., presentan un peptidoglicano más grueso y menos electrodenso.

**Pasaje:** «We previously showed that C. glutamicum cells treated with a sublethal concentration of EMB lose the integrity of the MM. [...] In addition, we observed that EMB treated cells have a thicker and less electron dense peptidoglycan (PG).»

Fuente: `Obsidian Vault/Research/Papers/meyer_2023_effects_of_benzothiazinone_and_ethambutol_on_the_integrity.pdf`, p. 1 · DOI 10.1016/j.tcsw.2023.100116 · verificación mecánica: **ok**

Nota: medio BHI con 10 µg/ml de etambutol (Meyer p. 3). La primera mitad de la afirmación es un hallazgo previo del grupo que Meyer cita.

- [ ] el pasaje sostiene exactamente esto

### 9. M2-R09 (SQ3)

**Afirmación:** Un cribado por Tn-seq en C. glutamicum identificó loci cuya inactivación causa hipersensibilidad al etambutol, entre ellos ripC, el complejo FtsEX y los genes conservados steAB.

**Pasaje:** «we generated the first high-density library of transposon inser- tion mutants in the model organism C. glutamicum. Transposon-sequencing was then used to define its essential gene set and identify loci that, when inactivated, confer hypersensitiv- ity to ethambutol (EMB), a drug that targets AG biogenesis. Among the EMBs loci were genes encoding RipC and the FtsEX complex [...] Inactivation of the conserved steAB genes (cgp_1603–1604) was also found to confer EMB hypersensitivity and cell division defects.»

Fuente: `Obsidian Vault/Research/Papers/lim_2019_identification_of_new_components_of_the_ripc_ftsex.pdf`, p. 1 · DOI 10.1371/journal.pgen.1008284 · verificación mecánica: **ok**

Nota: el cribado se hizo con 0,3 μg/ml de etambutol (Lim p. 5).

- [ ] el pasaje sostiene exactamente esto

### 10. M2-R10 (SQ4)

**Afirmación:** A diferencia de las micobacterias, en C. glutamicum las capas de arabinogalactano y micomembrana no son esenciales para la viabilidad; por eso su pérdida tras el tratamiento con etambutol no es el mecanismo directo de muerte en este organismo.

**Pasaje:** «In C. glutamicum the AG/ MM layers are not essential for viability, which is in stark contrast to Mycobacteria. This implies that loss of AG/MM integrity in C. glutamicum upon EMB or BTZ treatment is not the direct mechanism for killing.»

Fuente: `Obsidian Vault/Research/Papers/meyer_2023_effects_of_benzothiazinone_and_ethambutol_on_the_integrity.pdf`, p. 2 · DOI 10.1016/j.tcsw.2023.100116 · verificación mecánica: **ok**

Nota: es una inferencia de los autores a partir de que el AG y la micomembrana no son esenciales en C. glutamicum; no es una medición de mortalidad.

- [ ] el pasaje sostiene exactamente esto

## B. Afirmaciones prohibidas de M2 y M3

### 11. M2-P01 (PROHIBIDA)

**Afirmación incorrecta:** Un estudio proteómico de 2025 (archivo liang_2025, Devlin et al.) mostró que el tratamiento con etambutol aumenta más de dos veces la abundancia de EmbA y EmbC en M. tuberculosis.

**Pasaje que la contradice:** «The A and C subunits were both >2-fold more abundant in CS. (p. 13, Obsidian Vault/Research/Papers/liang_2025_proteomic_characterization_mycobacterium_tuberculosis_drug_treatment.pdf; verificación mecánica: ok)»

**Por qué:** Ese estudio no trata a M. tuberculosis con etambutol: la condición es ayuno de carbono. Los autores dicen que hacen falta más estudios para saber si ese aumento contribuye a la resistencia. El nombre del archivo induce al error.

- [ ] el pasaje contradice o limita exactamente esto

### 12. M2-P02 (PROHIBIDA)

**Afirmación incorrecta:** En C. glutamicum, el etambutol reprime los genes del metabolismo central.

**Pasaje que la contradice:** «With respect to the consequences of EMB addition on the mRNA levels of cytosolic enzymes, it is striking that no genes for enzymes of central metabolism are affected. (p. 9, Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf; verificación mecánica: ok)»

**Por qué:** Convierte en efecto una ausencia. Radmacher et al. destacan que ningún gen de enzimas del metabolismo central se ve afectado a nivel de ARNm; solo bajan levemente odhA y lpd. Además, el dato es transcriptómico, no proteómico.

- [ ] el pasaje contradice o limita exactamente esto

### 13. M2-P03 (PROHIBIDA)

**Afirmación incorrecta:** El etambutol induce la transcripción de divIVA en C. glutamicum, y por eso aumenta la proteína DivIVA.

**Pasaje que la contradice:** «DivIVA mRNA levels, and thus transcription rates, were not altered upon the addition of EMB (data not shown). (p. 5, Obsidian Vault/Research/Papers/schubert_2017_the_antituberculosis_drug_ethambutol_selectively_blocks_apical_growth.pdf; verificación mecánica: ok)»

**Por qué:** Le atribuye al efecto un mecanismo transcripcional. Schubert et al. informan que el ARNm de divIVA no cambia y proponen que la proteína se acumula por falta de crecimiento polar.

- [ ] el pasaje contradice o limita exactamente esto

### 14. M2-P04 (PROHIBIDA)

**Afirmación incorrecta:** La pérdida de integridad de la micomembrana y el engrosamiento del peptidoglicano por etambutol (Meyer et al. 2023) se observaron en C. glutamicum cultivado en medio mínimo CGXII.

**Pasaje que la contradice:** «rodA::rodA-eYFP were cultivated in BHI medium (Oxoid) [...] EMB added in the same way was used at 10 µg/ml. (p. 3, Obsidian Vault/Research/Papers/meyer_2023_effects_of_benzothiazinone_and_ethambutol_on_the_integrity.pdf; verificación mecánica: ok)»

**Por qué:** Confunde el medio. Meyer et al. cultivaron en BHI (complejo) con 10 µg/ml de etambutol. Es justamente el error que hay que evitar al compararlos con experimentos propios en CGXII.

- [ ] el pasaje contradice o limita exactamente esto

### 15. M3-P01 (PROHIBIDA, v2)

**Afirmación incorrecta:** La estructura por crio-EM de la Emb de C. glutamicum muestra el etambutol unido en el sitio del donador de arabinosa.

**Pasaje que la contradice:** «Herein, we report the cryo-EM struc- tures of Mycobacterium smegmatis EmbB in its “resting state” and DPA-bound “active state ”.» (p. 1) y «The recently reported structure of the ethambutol bound EmbA-EmbB complex enables us to analyze the structural features of the potential drug binding pockets of EmbB2 in this study.» (p. 11), `Obsidian Vault/Research/Papers/zhang_2020_cryo_em_snapshots_mycobacterial_arabinosyltransferase_embb2_complex.pdf` · verificación mecánica: **ok**

**Por qué:** Atribuye a C. glutamicum estructuras de micobacterias. Las estructuras del corpus son de EmbB de M. smegmatis, y la estructura con etambutol unido que citan es la del complejo EmbA-EmbB.

- [ ] el pasaje contradice o limita exactamente esto

### 15b. M3-P02 (PROHIBIDA, v2)

**Afirmación incorrecta:** No se sabe nada de la Emb de C. glutamicum más allá de su secuencia.

**Evidencia que la contradice:** sin pasaje en PDF de la carpeta. Títulos de PMID 17088267 (topología y mutagénesis de la Emb de C. glutamicum) y PMID 30046665 (Jankute 2018, actividad bioquímica) en `busqueda_m2_proteomica_etambutol.md`, consulta P1.

**Por qué:** Generaliza la ausencia. Lo que falta es la estructura experimental, no todo conocimiento sobre la enzima.

- [ ] la evidencia contradice o limita exactamente esto

**Atención:** M3 solo puede usarse cuando `busqueda_control_negativo.md` esté ejecutada y documentada.

## C. Afirmaciones dudosas (no incluidas como referencia)

### 16. DUDOSA (M2)

**Afirmación candidata:** La CIM (Etest) del etambutol para C. glutamicum silvestre es 0,75 µg/ml, y 1,5 µg/ml en la cepa que sobreexpresa emb.

**Pasaje:** «The MIC (Etest) of EMB for the wild-type was 0?75 mgm l 21, and for the overexpressing strain it was 1?5 mgm l 21.» (`Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf`, p. 4; verificación: ok)

**Motivo de la duda:** La unidad se perdió en la extracción ('mgm l 21'); no se puede asegurar si es µg/ml sin ver el PDF original.

- [ ] incluir como referencia tras revisar el PDF original

### 17. DUDOSA (M2)

**Afirmación candidata:** En C. glutamicum tratado con etambutol aparecen en el sobrenadante las micoliltransferasas CmytA y CmytC.

**Pasaje:** «we detected proteins in supernatants analysed at the end of cultivations that were absent in untreated cultures. These were, in addition to the mycolyltransferases CmytA and CmytC» (`Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf`, p. 3; verificación: ok)

**Motivo de la duda:** Los mismos autores dicen que otras proteínas del sobrenadante indican lisis parcial; no queda claro si es liberación específica o lisis.

- [ ] incluir como referencia tras revisar el PDF original

### 18. DUDOSA (M2)

**Afirmación candidata:** El etambutol aumenta el nivel de la proteína RodA en C. glutamicum.

**Pasaje:** «RodA is mislocalized, and the protein level seems to increase upon the addition of EMB.» (`Obsidian Vault/Research/Papers/schubert_2017_the_antituberculosis_drug_ethambutol_selectively_blocks_apical_growth.pdf`, p. 4; verificación: ok)

**Motivo de la duda:** La leyenda de la figura dice 'seems' y no hay cuantificación; la mala localización es firme, el aumento no.

- [ ] incluir como referencia tras revisar el PDF original

### 19. DUDOSA (M2)

**Afirmación candidata:** Agregar etambutol a cultivos de C. glutamicum en crecimiento provoca eflujo de L-glutamato, que no ocurre sin el fármaco.

**Pasaje:** «addition of ethambutol (EMB) to growing cultures of C. glutamicum causes L-glutamate efﬂux [...] whereas in the absence of EMB, no efﬂux occurs.» (`Obsidian Vault/Research/Papers/radmacher_2005_ethambutol_cglutamicum.pdf`, p. 1; verificación: ok)

**Motivo de la duda:** No hay duda sobre el pasaje: se sacó de las referencias para que Radmacher 2005 no aporte la mitad de M2. Puede volver si se prefiere este dato a Hart 2024.

- [ ] incluir como referencia tras revisar el PDF original

## D. Misión M1 (FAIR)

### 20. M1-R01

**Afirmación:** FAIR define cuatro principios fundacionales: Findability, Accessibility, Interoperability y Reusability (encontrabilidad, accesibilidad, interoperabilidad y reutilización), pensados para guiar a productores y publicadores de datos.

**Pasaje:** «This article describes four foundational principles — Findability, Accessibility, Interoperability, and Reusability— that serve to guide data producers and publishers»

Fuente: `Downloads/gold_set_benchmark/wilkinson_2016_fair_guiding_principles_sdata.2016.18.pdf`, p. 1 · verificación mecánica: **ok**

- [ ] el pasaje sostiene exactamente esto

### 21. M1-R02

**Afirmación:** A diferencia de iniciativas centradas en el investigador humano, FAIR pone énfasis específico en que las máquinas puedan encontrar y usar los datos automáticamente, además de apoyar su reutilización por personas.

**Pasaje:** «the FAIR Principles put speci ﬁc emphasis on enhancing the ability of machines to automatically ﬁnd and use the data, in addition to supporting its reuse by individuals.»

Fuente: `Downloads/gold_set_benchmark/wilkinson_2016_fair_guiding_principles_sdata.2016.18.pdf`, p. 1 · verificación mecánica: **ok**

- [ ] el pasaje sostiene exactamente esto

### 22. M1-R03

**Afirmación:** Los principios se aplican no solo a los datos en sentido convencional, sino también a los algoritmos, herramientas y flujos de trabajo que los generaron.

**Pasaje:** «it is our intent that the principles apply not only to ‘data’ in the conventional sense, but also to the algorithms, tools, and work ﬂows that led to that data.»

Fuente: `Downloads/gold_set_benchmark/wilkinson_2016_fair_guiding_principles_sdata.2016.18.pdf`, p. 1 · verificación mecánica: **ok**

- [ ] el pasaje sostiene exactamente esto

### 23. M1-R04

**Afirmación:** Para ser encontrables (F1), los datos y metadatos deben tener asignado un identificador global único y persistente.

**Pasaje:** «F1. (meta)data are assigned a globally unique and persistent identi ﬁer»

Fuente: `Downloads/gold_set_benchmark/wilkinson_2016_fair_guiding_principles_sdata.2016.18.pdf`, p. 4 · verificación mecánica: **ok**

- [ ] el pasaje sostiene exactamente esto

### 24. M1-R05

**Afirmación:** Los principios FAIR preceden a las decisiones de implementación: no prescriben ninguna tecnología, estándar ni solución concreta, y no son en sí mismos un estándar ni una especificación.

**Pasaje:** «These high-level FAIR Guiding Principles precede implementation choices, and do not suggest any speciﬁc technology, standard, or implementation-solution; moreover, the Principles are not, themselves, a standard or a speci ﬁcation.»

Fuente: `Downloads/gold_set_benchmark/wilkinson_2016_fair_guiding_principles_sdata.2016.18.pdf`, p. 5 · verificación mecánica: **ok**

- [ ] el pasaje sostiene exactamente esto

### 25. M1-P01 (PROHIBIDA)

**Afirmación incorrecta:** FAIR significa Findable, Accessible, Interoperable y Reproducible.

**Pasaje que la contradice:** «FAIR— Findable, Accessible, Interoperable, Reusable. (p. 2, Downloads/gold_set_benchmark/wilkinson_2016_fair_guiding_principles_sdata.2016.18.pdf; verificación mecánica: ok)»

**Por qué:** La R corresponde a Reusable (reutilizable), no a Reproducible; la confusión es frecuente porque el texto habla de reproducibilidad.

- [ ] el pasaje contradice o limita exactamente esto

### 26. M1-P02 (PROHIBIDA)

**Afirmación incorrecta:** Para cumplir con FAIR, los datos deben publicarse en acceso abierto y gratuito, sin restricciones de acceso.

**Pasaje que la contradice:** «A1.2 the protocol allows for an authentication and authorization procedure, where necessary [...] One such example is highly sensitive or personally-identi ﬁable data, where publication of rich metadata to facilitate discovery, including clear rules regarding the process for accessing the data, provides a high degree of ‘FAIRness’ even in the absence of FAIR publication of the data itself. (p. 4, Downloads/gold_set_benchmark/wilkinson_2016_fair_guiding_principles_sdata.2016.18.pdf; verificación mecánica: ok)»

**Por qué:** FAIR no exige acceso abierto: el protocolo de acceso puede incluir autenticación y autorización, y en datos sensibles basta con publicar metadatos ricos y reglas claras de acceso. Lo que debe ser abierto y gratuito (A1.1) es el protocolo, no los datos.

- [ ] el pasaje contradice o limita exactamente esto

## E. Autoauditoría (evaluador hostil)

**a) ¿Alguna afirmación es más fuerte, más general o de otra condición que su pasaje?** Encontré tres casos y los corregí:
- La afirmación transcriptómica decía "la única respuesta global". Era inferencia mía, así que la reformulé como "Radmacher et al. midieron...".
- Al pasaje de Lim le faltaba la mención de *C. glutamicum*; lo extendí para que la incluya.
- En la afirmación de Meyer marqué que la pérdida de micomembrana es un hallazgo previo del grupo.

Lo que queda por revisar: varias afirmaciones de M2 no nombran el medio porque el pasaje no lo dice; el medio figura en las notas del punto A. En M1, F1 parafrasea "(meta)data" como "datos y metadatos", tal como lo define el propio artículo en la p. 4.

**b) ¿Hay afirmaciones redundantes?** M2-R03 (arabinano y ácidos micólicos, medición bioquímica, Radmacher) y M2-R07 (integridad de la micomembrana y grosor del peptidoglicano, microscopía, Meyer) tratan de la envoltura, pero con mediciones y grupos distintos; las dejé. Las prohibidas sobre DivIVA y metabolismo central son, a propósito, el espejo de afirmaciones de referencia.

**c) ¿Dependencia de un solo grupo o de una sola revisión?**
- Referencias de M2: Radmacher 2005 aporta 4 de 10 (bajé de 5: cambié el eflujo de glutamato por Hart 2024). Schubert 2017 y Meyer 2023 son del mismo grupo (Bramkamp) y suman 4. Lim 2019 y Hart 2024 suman 2. Dos grupos aportan 8 de 10 afirmaciones.
- Artículos clave: en v2 quedan 11 (salió Devlin 2025, que es un distractor). La versión 1 contaba al menos 9 grupos con Devlin incluido; falta recontar sin él. No dependen de ninguna revisión.
- El riesgo real es otro: la evidencia en *C. glutamicum* es escasa y está concentrada en dos grupos (Eggeling/Besra y Bramkamp).

**d) ¿Las prohibidas son errores realistas?** Sí, y son específicas del corpus:
- Devlin 2025: el nombre del archivo (`..._drug_treatment`) induce a leerlo como un estudio con fármacos.
- BHI frente a CGXII: es la confusión de medio más probable para esta tesis.
- Las otras dos convierten una ausencia o una acumulación en un mecanismo.
- En v2, las prohibidas de M3 detectan dos errores opuestos: atribuirle a *C. glutamicum* estructuras de micobacterias (P01) y negar todo lo que se sabe de su Emb (P02).
- "Reproducible" en lugar de "Reusable" en M1 es un error frecuente.

**e) ¿Podría M3 (versión 1) tener respuesta en literatura que no busqué?** Sí, en tres lugares: repositorios de datos (PRIDE), tesis o actas de congresos, y literatura no indexada. Detalle en `busqueda_m2_proteomica_etambutol.md`, sección Límites. Para la M3 de la versión 2, ver los límites previstos en `busqueda_control_negativo.md`. El riesgo más concreto es un dataset en PRIDE sin artículo asociado.
