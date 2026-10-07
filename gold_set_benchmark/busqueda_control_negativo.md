# Búsqueda documentada del control negativo (M3)

**Pregunta M3:** ¿Qué proteínas cambian significativamente de abundancia en *Corynebacterium glutamicum* expuesto a concentraciones subinhibitorias de etambutol, medidas por proteómica cuantitativa?

**Fecha y hora de ejecución:** 2026-10-07 11:07 (hora local). **Herramientas:** NCBI E-utilities (esearch/esummary, base `pubmed`) y la API REST de Europe PMC (`/search`, que por defecto incluye texto completo y preprints). No se usó ningún buscador con IA.

## PubMed

### Consulta P1

`ethambutol[tiab] AND glutamicum[tiab]`

**Resultados:** 19

**Por qué no responde la pregunta:** Los 19 resultados son trabajos sobre envoltura, arabinano, producción de aminoácidos o fenotipos. Ninguno mide el proteoma: las respuestas globales que aparecen son transcriptómicas (PMID 15870446) o fenotípicas.

<details><summary>Resultados (PMID · año · título)</summary>

- 38044953 · 2023 · Effects of benzothiazinone and ethambutol on the integrity of the corynebacterial cell envelope.
- 31437147 · 2019 · Identification of new components of the RipC-FtsEX cell separation pathway of Corynebacterineae.
- 31011369 · 2019 · Engineering Corynebacterium glutamicum triggers glutamic acid accumulation in biotin-rich corn stover hydrolysate.
- 30046665 · 2018 · The singular Corynebacterium glutamicum Emb arabinofuranosyltransferase polymerises the α(1 → 5) arabinan backbone in the early stages of cell wall arabinan biosynthesis.
- 28174310 · 2017 · The Antituberculosis Drug Ethambutol Selectively Blocks Apical Growth in CMN Group Bacteria.
- 23737264 · 2013 · Production of non-proteinogenic amino acids from α-keto acid precursors with recombinant Corynebacterium glutamicum.
- 21909677 · 2012 · Ethambutol-mediated cell wall modification in recombinant Corynebacterium glutamicum increases the biotransformation rates of cyclohexanone derivatives.
- 21796382 · 2011 · Amino acid production from rice straw and wheat bran hydrolysates by recombinant pentose-utilizing Corynebacterium glutamicum.
- 20699568 · 2010 · A role of the cspA gene encoding a mycolyltransferase in the growth under alkaline conditions of Corynebacterium glutamicum.
- 18627460 · 2008 · Biosynthesis of mycobacterial arabinogalactan: identification of a novel alpha(1-->3) arabinofuranosyltransferase.
- 17437098 · 2007 · Glutamate production by Corynebacterium glutamicum: dependence on the oxoglutarate dehydrogenase inhibitor protein OdhI and protein kinase PknG.
- 17387176 · 2007 · Identification of a novel arabinofuranosyltransferase AftB involved in a terminal step of cell wall arabinan biosynthesis in Corynebacterianeae, such as Corynebacterium glutamicum and Mycobacterium tuberculosis.
- 17088267 · 2007 · Topology and mutational analysis of the single Emb arabinofuranosyltransferase of Corynebacterium glutamicum as a model of Emb proteins of Mycobacterium tuberculosis.
- 16891347 · 2006 · Arabinan-deficient mutants of Corynebacterium glutamicum and the consequent flux in decaprenylmonophosphoryl-D-arabinose metabolism.
- 16595677 · 2006 · Identification of a novel arabinofuranosyltransferase (AftA) involved in cell wall arabinan biosynthesis in Mycobacterium tuberculosis.
- 16306684 · 2005 · Fluorescent phospholipid analogs as microscopic probes for detection of the mycolic acid-containing layer in Corynebacterium glutamicum: detecting alterations in the mycolic acid-containing layer following ethambutol treatment.
- 16040600 · 2005 · Deletion of Cg-emb in corynebacterianeae leads to a novel truncated cell wall arabinogalactan, whereas inactivation of Cg-ubiA results in an arabinan-deficient mutant with a cell wall galactan core.
- 15870446 · 2005 · Ethambutol, a cell wall inhibitor of Mycobacterium tuberculosis, elicits L-glutamate efflux of Corynebacterium glutamicum.
- 15469514 · 2004 · Deletion of the genes encoding the MtrA-MtrB two-component system of Corynebacterium glutamicum has a strong influence on cell morphology, antibiotics susceptibility and expression of genes involved in osmoprotection.

</details>

### Consulta P2

`ethambutol[tiab] AND glutamicum[tiab] AND (proteom*[tiab] OR "mass spectrometry"[tiab])`

**Resultados:** 0

**Por qué no responde la pregunta:** 0 resultados: no hay ningún artículo indexado con etambutol, C. glutamicum y proteómica o espectrometría de masas en título o resumen.

### Consulta P3

`ethambutol AND corynebacterium AND (proteomics OR proteome OR "mass spectrometry")`

**Resultados:** 2

**Por qué no responde la pregunta:** PMID 42226830 es un caso clínico de M. szulgai. PMID 16040600 trata de la deleción de Cg-emb y analiza el arabinogalactano, no el proteoma bajo el fármaco.

<details><summary>Resultados (PMID · año · título)</summary>

- 42226830 · 2026 · Diagnostic Challenges in Disseminated Mycobacterium szulgai Infection: A Case Report in the Setting of Advanced HIV Infection.
- 16040600 · 2005 · Deletion of Cg-emb in corynebacterianeae leads to a novel truncated cell wall arabinogalactan, whereas inactivation of Cg-ubiA results in an arabinan-deficient mutant with a cell wall galactan core.

</details>

### Consulta P4

`ethambutol[tiab] AND proteom*[tiab] AND (mycobacter*[tiab] OR corynebacter*[tiab])`

**Resultados:** 17

**Por qué no responde la pregunta:** Hay estudios proteómicos con etambutol, pero en micobacterias (M. smegmatis: PMID 18275136 y 20686769; M. tuberculosis: PMID 29366429, 33210572, 40791120 y otros). Ninguno usa C. glutamicum.

<details><summary>Resultados (PMID · año · título)</summary>

- 41572760 · 2026 · Targeting InhA for Tuberculosis Therapy: A Review of Recent Advances in Enzyme Inhibition and Drug Development.
- 40791120 · 2025 · Dynamic Proteomic and PTMomic Characterization of Mycobacteria after Clinical Pharmaceutical Intervention.
- 36118032 · 2022 · mbtD and celA1 association with ethambutol resistance in Mycobacterium tuberculosis: A multiomics analysis.
- 35158297 · 2022 · Rv1258c acts as a drug efflux pump and growth controlling factor in Mycobacterium tuberculosis.
- 33274277 · 2020 · Bioorthogonal Correlative Light-Electron Microscopy of Mycobacterium tuberculosis in Macrophages Reveals the Effect of Antituberculosis Drugs on Subcellular Bacterial Distribution.
- 33210572 · 2021 · Mycobacterial ethambutol responsive genes and implications in antibiotics resistance.
- 30029919 · 2018 · Proteomic analysis reveals that sulfamethoxazole induces oxidative stress in M. tuberculosis.
- 30023583 · 2017 · S-Enantiomer of the Antitubercular Compound S006-830 Complements Activity of Frontline TB Drugs and Targets Biogenesis of Mycobacterium tuberculosis Cell Envelope.
- 29366429 · 2019 · New insights on Ethambutol Targets in Mycobacterium tuberculosis.
- 29119205 · 2018 · Secretome profile analysis of multidrug-resistant, monodrug-resistant and drug-susceptible Mycobacterium tuberculosis.
- 28882482 · 2017 · Ester-prodrugs of ethambutol control its antibacterial activity and provide rapid screening for mycobacterial hydrolase activity.
- 28627738 · 2017 · Systematic review on the proteomic profile of Mycobacterium tuberculosis exposed to drugs.
- 26149995 · 2015 · In silico-based high-throughput screen for discovery of novel combinations for tuberculosis treatment.
- 26786220 · 2014 · Deciphering the sequential events during in vivo acquisition of drug resistance in Mycobacterium tuberculosis.
- 20686769 · 2011 · The novel responses of ethambutol against Mycobacterium smegmatis mc²155 Revealed by proteomics analysis.
- 20023729 · 2009 · Direct measurement of Mycobacterium-fibronectin interactions.
- 18275136 · 2008 · The proteomic response of Mycobacterium smegmatis to anti-tuberculosis drugs suggests targeted pathways.

</details>

## Europe PMC

### Consulta E1

`ethambutol AND glutamicum AND (proteome OR proteomic OR proteomics)`

**Resultados:** 47

**Por qué no responde la pregunta:** Búsqueda en texto completo: los 47 resultados mencionan los tres términos en algún lugar del cuerpo del artículo, sin relación entre sí. Ningún título ni resumen trata del proteoma de C. glutamicum bajo etambutol. Revisé el resumen de los casos dudosos: PMID 35265054 compara el proteoma de mutantes de romboides con la cepa silvestre, no bajo etambutol (no revisé el texto completo); PMID 41772423 es proteómica de C. kroppenstedtii con tetrahidrolipstatina; PMID 21909677 usa etambutol para biotransformación, sin proteómica en el resumen; PMID 37679597 es división celular (Glp/GlpR).

<details><summary>Resultados (ID · año · título)</summary>

- 41772423 · 2026 · Effects of lipid-lowering drug on vancomycin-sensitive Corynebacterium kroppenstedtii.
- 37679597 · 2023 · Eukaryotic-like gephyrin and cognate membrane receptor coordinate corynebacterial cell division and polar elongation.
- 41920993 · 2026 · A periplasmic protein complex mediates arabinofuranosyltransferase activity and intrinsic drug resistance in &lt;i&gt;Mycobacterium tuberculosis&lt;/i&gt;.
- 35265054 · 2022 · Functional Genomics Uncovers Pleiotropic Role of Rhomboids in <i>Corynebacterium glutamicum</i>.
- 39960848 · 2025 · Maintenance of cell wall remodeling and vesicle production are connected in &lt;i&gt;Mycobacterium tuberculosis&lt;/i&gt;.
- 39066417 · 2024 · Unveiling the Significance of LysE in Survival and Virulence of <i>Mycobacterium tuberculosis</i>: A Review Reveals It as a Potential Drug Target, Diagnostic Marker, and a Vaccine Candidate.
- 37076525 · 2023 · Identification of D-arabinan-degrading enzymes in mycobacteria.
- 39891166 · 2025 · Metabolic engineering approaches for the biosynthesis of antibiotics.
- 37501888 · 2023 · <i>Mycobacterium tuberculosis</i> Rv0494 Protein Contributes to Mycobacterial Persistence.
- PPR523191 · 2022 · Mining the human gut microbiome identifies mycobacterial d-arabinan degrading enzymes
- 36145357 · 2022 · Molecular Insight into <i>Mycobacterium tuberculosis</i> Resistance to Nitrofuranyl Amides Gained through Metagenomics-like Analysis of Spontaneous Mutants.
- 34905344 · 2022 · Chemical Reporters for Bacterial Glycans: Development and Applications.
- 35718063 · 2022 · Expression of a novel mycobacterial phosphodiesterase successfully lowers cAMP levels resulting in reduced tolerance to cell wall-targeting antimicrobials.
- 29018126 · 2017 · Systematic Identification of <i>Mycobacterium tuberculosis</i> Effectors Reveals that BfrB Suppresses Innate Immunity.
- 36346214 · 2022 · An essential periplasmic protein coordinates lipid trafficking and is required for asymmetric polar growth in mycobacteria.
- 33954837 · 2021 · Recent Insights into the Structure and Function of Mycobacterial Membrane Proteins Facilitated by Cryo-EM.
- 26136255 · 2015 · The external PASTA domain of the essential serine/threonine protein kinase PknB regulates mycobacterial growth.
- 26363557 · 2015 · Efflux systems in bacteria and their metabolic engineering applications.
- 33879617 · 2021 · An ABC transporter Wzm-Wzt catalyzes translocation of lipid-linked galactan across the plasma membrane in mycobacteria.
- 20843371 · 2010 · The characterization of conserved binding motifs and potential target genes for M. tuberculosis MtrAB reveals a link between the two-component system and the drug resistance of M. smegmatis.
- 28878275 · 2017 · A fluorescence-based reporter for monitoring expression of mycobacterial cytochrome bd in response to antibacterials and during infection.
- 22539022 · 2012 · Two-component signal transduction in Corynebacterium glutamicum and other corynebacteria: on the way towards stimuli and targets.
- 36809064 · 2023 · Molecular Mechanisms of MmpL3 Function and Inhibition.
- 34726489 · 2021 · Structure-Aware Mycobacterium tuberculosis Functional Annotation Uncloaks Resistance, Metabolic, and Virulence Genes.
- 36439231 · 2022 · Clinically encountered growth phenotypes of tuberculosis-causing bacilli and their &lt;i&gt;in vitro&lt;/i&gt; study: A review.
- 16204505 · 2005 · Characterization of a Corynebacterium glutamicum lactate utilization operon induced during temperature-triggered glutamate production.
- 34726813 · 2022 · New Trends and Future Opportunities in the Enzymatic Formation of C-C, C-N, and C-O bonds.
- 33142884 · 2020 · In Vivo Imaging with Genetically Encoded Redox Biosensors.
- 18556798 · 2008 · Transfer of the first arabinofuranose residue to galactan is essential for Mycobacterium smegmatis viability.
- 21261849 · 2008 · Metabolic regulation and overproduction of primary metabolites.
- 21383969 · 2011 · The C-terminal domain of the Arabinosyltransferase Mycobacterium tuberculosis EmbC is a lectin-like carbohydrate binding module.
- 30487163 · 2018 · LipG a bifunctional phospholipase/thioesterase involved in mycobacterial envelope remodeling.
- PMC9260650 · 2022 · Posters
- 28220152 · 2016 · Lack of mycothiol and ergothioneine induces different protective mechanisms in Mycobacterium smegmatis.
- 19635450 · 2010 · The Mycobacterium tuberculosis cytochrome P450 system.
- 21595486 · 2011 · Reconstitution of functional mycobacterial arabinosyltransferase AftC proteoliposome and assessment of decaprenylphosphorylarabinose analogues as arabinofuranosyl donors.
- 26261090 · 2015 · A glycomic approach reveals a new mycobacterial polysaccharide.
- 17804795 · 2007 · The missing piece of the type II fatty acid synthase system from Mycobacterium tuberculosis.
- 32850740 · 2020 · Overview on Multienzymatic Cascades for the Production of Non-canonical α-Amino Acids.
- 30474981 · 2019 · Iron Acquisition in Mycobacterium tuberculosis.
- 26300875 · 2015 · The application of tetracyclineregulated gene expression systems in the validation of novel drug targets in Mycobacterium tuberculosis.
- 11532219 · 2001 · The genome of Mycobacterium leprae: a minimal mycobacterial gene set.
- 19220750 · 2009 · Menaquinone synthesis is critical for maintaining mycobacterial viability during exponential growth and recovery from non-replicating persistence.
- 22745722 · 2012 · Wild-type phosphoribosylpyrophosphate synthase (PRS) from Mycobacterium tuberculosis: a bacterial class II PRS?
- 17521419 · 2007 · GSMN-TB: a web-based genome-scale network model of Mycobacterium tuberculosis metabolism.
- 22172201 · 2011 · Redox homeostasis in mycobacteria: the key to tuberculosis control?
- 23808874 · 2013 · New targets and inhibitors of mycobacterial sulfur metabolism.

</details>

### Consulta E2

`TITLE_ABS:(ethambutol AND glutamicum)`

**Resultados:** 21

**Por qué no responde la pregunta:** Los mismos trabajos que en PubMed más el preprint de Meyer 2023 (PPR736821). Ninguno es proteómico.

<details><summary>Resultados (ID · año · título)</summary>

- 38044953 · 2023 · Effects of benzothiazinone and ethambutol on the integrity of the corynebacterial cell envelope.
- PPR736821 · 2023 · Effects of benzothiazinone and ethambutol on the integrity of the corynebacterial cell envelope
- 31011369 · 2019 · Engineering <i>Corynebacterium glutamicum</i> triggers glutamic acid accumulation in biotin-rich corn stover hydrolysate.
- 30046665 · 2018 · The singular &lt;i&gt;Corynebacterium glutamicum&lt;/i&gt; Emb arabinofuranosyltransferase polymerises the α(1 → 5) arabinan backbone in the early stages of cell wall arabinan biosynthesis.
- 28174310 · 2017 · The Antituberculosis Drug Ethambutol Selectively Blocks Apical Growth in CMN Group Bacteria.
- 31437147 · 2019 · Identification of new components of the RipC-FtsEX cell separation pathway of Corynebacterineae.
- 21909677 · 2012 · Ethambutol-mediated cell wall modification in recombinant Corynebacterium glutamicum increases the biotransformation rates of cyclohexanone derivatives.
- 23737264 · 2013 · Production of non-proteinogenic amino acids from α-keto acid precursors with recombinant Corynebacterium glutamicum.
- 16306684 · 2005 · Fluorescent phospholipid analogs as microscopic probes for detection of the mycolic acid-containing layer in Corynebacterium glutamicum: detecting alterations in the mycolic acid-containing layer following ethambutol treatment.
- 20699568 · 2010 · A role of the cspA gene encoding a mycolyltransferase in the growth under alkaline conditions of Corynebacterium glutamicum.
- 21796382 · 2011 · Amino acid production from rice straw and wheat bran hydrolysates by recombinant pentose-utilizing Corynebacterium glutamicum.
- 534525 · 2011 · Molecular and biochemical characterisation of novel glycosyltransferases in Mycobacterium tuberculosis
- 16040600 · 2005 · Deletion of Cg-emb in corynebacterianeae leads to a novel truncated cell wall arabinogalactan, whereas inactivation of Cg-ubiA results in an arabinan-deficient mutant with a cell wall galactan core.
- 17437098 · 2007 · Glutamate production by Corynebacterium glutamicum: dependence on the oxoglutarate dehydrogenase inhibitor protein OdhI and protein kinase PknG.
- 15870446 · 2005 · Ethambutol, a cell wall inhibitor of Mycobacterium tuberculosis, elicits L-glutamate efflux of Corynebacterium glutamicum.
- 16891347 · 2006 · Arabinan-deficient mutants of Corynebacterium glutamicum and the consequent flux in decaprenylmonophosphoryl-D-arabinose metabolism.
- 17387176 · 2007 · Identification of a novel arabinofuranosyltransferase AftB involved in a terminal step of cell wall arabinan biosynthesis in Corynebacterianeae, such as Corynebacterium glutamicum and Mycobacterium tuberculosis.
- 16595677 · 2006 · Identification of a novel arabinofuranosyltransferase (AftA) involved in cell wall arabinan biosynthesis in Mycobacterium tuberculosis.
- 17088267 · 2007 · Topology and mutational analysis of the single Emb arabinofuranosyltransferase of Corynebacterium glutamicum as a model of Emb proteins of Mycobacterium tuberculosis.
- 15469514 · 2004 · Deletion of the genes encoding the MtrA-MtrB two-component system of Corynebacterium glutamicum has a strong influence on cell morphology, antibiotics susceptibility and expression of genes involved in osmoprotection.
- 18627460 · 2008 · Biosynthesis of mycobacterial arabinogalactan: identification of a novel alpha(1--&gt;3) arabinofuranosyltransferase.

</details>

### Consulta E3

`TITLE_ABS:(ethambutol AND (proteome OR proteomic OR proteomics) AND (corynebacterium OR mycobacterium OR mycobacteria))`

**Resultados:** 15

**Por qué no responde la pregunta:** Coincide con la consulta 4 de PubMed: todos los estudios proteómicos con etambutol son en Mycobacterium (o revisiones), ninguno en Corynebacterium.

<details><summary>Resultados (ID · año · título)</summary>

- 40791120 · 2025 · Dynamic Proteomic and PTMomic Characterization of Mycobacteria after Clinical Pharmaceutical Intervention.
- 36118032 · 2022 · <i>mbtD</i> and <i>celA1</i> association with ethambutol resistance in <i>Mycobacterium tuberculosis</i>: A multiomics analysis.
- 35158297 · 2022 · Rv1258c acts as a drug efflux pump and growth controlling factor in Mycobacterium tuberculosis.
- 33210572 · 2021 · Mycobacterial ethambutol responsive genes and implications in antibiotics resistance.
- 28627738 · 2017 · Systematic review on the proteomic profile of Mycobacterium tuberculosis exposed to drugs.
- 29366429 · 2019 · New insights on Ethambutol Targets in Mycobacterium tuberculosis.
- 30029919 · 2018 · Proteomic analysis reveals that sulfamethoxazole induces oxidative stress in M. tuberculosis.
- 29119205 · 2018 · Secretome profile analysis of multidrug-resistant, monodrug-resistant and drug-susceptible Mycobacterium tuberculosis.
- 33274277 · 2020 · Bioorthogonal Correlative Light-Electron Microscopy of <i>Mycobacterium tuberculosis</i> in Macrophages Reveals the Effect of Antituberculosis Drugs on Subcellular Bacterial Distribution.
- 18275136 · 2008 · The proteomic response of Mycobacterium smegmatis to anti-tuberculosis drugs suggests targeted pathways.
- 30023583 · 2017 · S-Enantiomer of the Antitubercular Compound S006-830 Complements Activity of Frontline TB Drugs and Targets Biogenesis of <i>Mycobacterium tuberculosis</i> Cell Envelope.
- 20686769 · 2011 · The novel responses of ethambutol against Mycobacterium smegmatis mc²155 Revealed by proteomics analysis.
- 26149995 · 2015 · In silico-based high-throughput screen for discovery of novel combinations for tuberculosis treatment.
- 26786220 · 2014 · Deciphering the sequential events during in vivo acquisition of drug resistance in Mycobacterium tuberculosis.
- 20023729 · 2009 · Direct measurement of Mycobacterium-fibronectin interactions.

</details>

## Conclusión

Ninguna de las 7 consultas encontró un estudio que mida el proteoma de *C. glutamicum* expuesto a etambutol. Lo más cercano es:
- en *C. glutamicum*, el perfil **transcriptómico** de Radmacher et al. 2005 (PMID 15870446);
- en otra especie, perfiles **proteómicos** de *M. smegmatis* con etambutol (PMID 18275136 y 20686769).

Una respuesta correcta a M3 tiene que decir que no hay respuesta publicada y puede mencionar estos antecedentes como lo más cercano, sin presentarlos como respuesta.

## Límites de esta búsqueda

- No se buscó en Web of Science, Scopus, Google Scholar, bioRxiv directo, repositorios de tesis ni actas de congresos.
- Tampoco en repositorios de datos (PRIDE/ProteomeXchange), donde podría haber un dataset depositado sin artículo.
- Las consultas de PubMed se limitan a título y resumen. Un estudio que mencione el etambutol solo en el texto completo (por ejemplo, como una de varias condiciones de estrés) solo lo captaría la consulta E1 de Europe PMC. Esa consulta se evaluó por título y resumen, salvo los casos dudosos mencionados.
- Los datos preliminares de UBYPA (Institut Pasteur de Montevideo) no están publicados y, por definición, no aparecen.
- Literatura en otros idiomas (chino, japonés) no indexada en estas bases quedaría fuera.
