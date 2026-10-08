"""Plain-language views of saved facts; never infer evidence or change state."""
import json


ANSWER_LABELS = {
    'unavailable': 'Aún no hay una respuesta con respaldo revisado.',
    'partial': 'Respuesta parcial: hay partes respaldadas y otras pendientes.',
    'complete': 'Respuesta completa para el alcance acordado, con sus límites.',
}
REASON_LABELS = {
    'verdict_partial': 'la verificación encontró respaldo solo parcial',
    'verdict_unsupported': 'la verificación no encontró respaldo en los pasajes',
    'verification_unparsed': 'la verificación no devolvió un dictamen legible',
    'verification_ambiguous': 'la verificación devolvió citas ambiguas',
    'verification_without_citations': 'la verificación no citó ningún pasaje',
    'verification_citation_without_passage': 'la verificación citó sin pasaje verificable',
    'verification_foreign_source': 'la verificación citó una fuente que no está en el corpus verificado',
    'verification_passage_mismatch': 'el respaldo aparece en otro pasaje; requiere una nueva revisión',
    'verification_question_too_long': 'la afirmación es demasiado larga para verificarla; divídela',
    'scope_withheld_by_policy': 'su alcance espera una fuente obligatoria',
    'scope_not_sufficient': 'otra afirmación del mismo alcance no pasó la verificación; revisa ese alcance',
    'human_rejected': 'una persona la revisó y el pasaje no la respalda',
    'required_source_missing': 'falta una fuente obligatoria para ese alcance',
    'policy_review_pending': 'hay una decisión pendiente sobre una fuente',
    'not_asked': 'no se consultó',
    'identity_unconfirmed': 'falta confirmar qué artículo y versión contiene el PDF',
    'paywall': 'sin acceso abierto',
    'access_denied': 'el sitio negó el acceso',
    'routes_exhausted': 'ninguna ruta de acceso abierto funcionó',
    'source_budget_exhausted': 'se agotó el tiempo asignado a la fuente',
    'not_acquired': 'todavía no se intentó descargar',
    'excluded_by_screening': 'excluida en el cribado',
    'screening_uncertain': 'dudosa en el cribado; falta decidir',
    'not_screened': 'todavía no se decidió si incluirla',
    'duplicate_content': 'el PDF es idéntico al de otra fuente; revisar cuál corresponde',
    'processing_stuck': 'NotebookLM no terminó de procesar el PDF; se reintenta en la próxima continuación',
}
GAP_LABELS = {
    'no_access': 'falta una fuente obligatoria sin acceso abierto; puedes importar tu PDF',
    'acquisition_failed': 'falta una fuente obligatoria sin PDF descargable; importa tu PDF o reintenta la descarga',
    'identity_unconfirmed': 'una fuente obligatoria espera confirmar su identidad',
    'excluded_by_screening': 'una fuente obligatoria fue excluida en el cribado',
    'required_source_not_found': 'una fuente obligatoria no se encontró',
    'policy_review_pending': 'hay una decisión pendiente sobre una fuente',
    'claims_not_verified': 'las afirmaciones propuestas no pasaron la verificación',
    'insufficient_evidence_in_corpus': 'el corpus no tiene evidencia suficiente para responderlo',
}
PHASE_LABELS = {
    'plan': 'Preparando la investigación', 'discover': 'Buscando fuentes',
    'acquire': 'Recuperando documentos', 'upload': 'Enviando fuentes a NotebookLM',
    'readiness': 'Esperando que se procesen las fuentes', 'qa': 'Consultando la evidencia',
    'audit': 'Revisando citas y cobertura', 'done': 'Respuesta revisada',
}


def welcome(root, guide):
    return {
        'kind': 'welcome', 'operator': 'EZ', 'runs_root': str(root), 'guide_path': str(guide),
        'message': 'Soy EZ. Te ayudo a investigar con fuentes y citas de NotebookLM.',
        'steps': [
            'Abre este proyecto con tu agente y dile: «EZ, ayúdame a empezar».',
            'EZ prepara el entorno; tú completas el acceso a NotebookLM en el navegador.',
            'Cuenta qué quieres investigar y para qué. EZ guarda el contexto y prepara la búsqueda.',
        ],
        'next_action': 'Para empezar: «EZ, prepara mi entorno. Quiero investigar…».',
    }


def cite(reference):
    """Bibliographic identity of a cited source; the remote ID only when nothing else is known."""
    source = reference.get('source') or {}
    if not source.get('title') and not source.get('doi'):
        return 'Fuente NotebookLM: ' + reference['source_id']
    parts = [source.get('title') or source.get('source_id')]
    if source.get('year'):
        parts[0] += f' ({source["year"]})'
    for key, label in (('doi', 'DOI'), ('pmid', 'PMID'), ('pmcid', 'PMCID')):
        if source.get(key):
            parts.append(f'{label} {source[key]}')
    return '. '.join(parts)


def render(value):
    lines = []
    if value.get('kind') == 'welcome':
        return '\n'.join([value['message'], '', 'Cómo empezar:',
                          *[f'{i}. {step}' for i, step in enumerate(value['steps'], 1)], '',
                          'La conversación ocurre en tu agente. El comando ez no abre un chat independiente.',
                          'Puedes pedir: «¿Cómo va?», «Continuemos» o «Tengo este PDF».',
                          'Carpeta de investigaciones: ' + value['runs_root'],
                          'Guía completa: ez --guide', 'Comprobar el entorno: ez setup --check'])
    if value.get('kind') == 'user_guide':
        return value['text']
    if value.get('kind') == 'verify_sample':
        lines = [f'Revisión humana: {value["checked"]} afirmaciones ya revisadas. Para revisar ahora:']
        for claim in value['claims']:
            lines.append(f'\n{claim["id"]}: {claim["text"]}')
            for reference in claim.get('references', []):
                source = reference.get('source', {})
                lines.append('  ' + cite(reference) + (f' — {source["pdf_path"]}' if source.get('pdf_path') else ''))
                lines.append('  Pasaje: ' + reference['cited_text'])
        return '\n'.join(lines + ['Siguiente paso: ' + value['next_action']])
    if value.get('kind') == 'draft_material':
        return '\n'.join(['Afirmaciones verificadas para redactar (informe: ' + value['report_path'] + '):',
                          *[f'- {c["marker"]} {c["text"]}' for c in value['claims']], 'Siguiente paso: ' + value['next_action']])
    if value.get('kind') == 'draft_check':
        lines = ['Borrador ' + ('aceptado.' if value['valid'] else 'con errores.')]
        if value['unknown_markers']:
            lines.append('Marcadores que no corresponden a afirmaciones verificadas: ' + ', '.join(value['unknown_markers']))
        if value['withheld_markers']:
            lines.append('Marcadores de afirmaciones retenidas (no se pueden citar): ' + ', '.join(value['withheld_markers']))
        if value['unmarked_count']:
            lines.append(f'Oraciones sin marcador para revisar: {value["unmarked_count"]}')
            lines += ['- ' + s for s in value['unmarked_sentences'][:10]]
        return '\n'.join(lines + ['Siguiente paso: ' + value['next_action']])
    if value.get('kind') == 'check':
        return ('Comprobación sin cambios: ' + {'contract': 'la propuesta es válida', 'review': 'la revisión es válida',
                                                'screening': 'el cribado es válido'}[value['target']] + '.\n'
                'Siguiente paso: ' + value['next_action'])
    if 'can_notebook_qa' in value:
        lines.append('Preparación de EZ')
        lines.append('Configuración: ' + ('guardada.' if value['configuration_exists'] else 'pendiente; usa ez setup para guardarla.'))
        lines.append('NotebookLM: ' + ('acceso comprobado.' if value['can_notebook_qa'] else
                     ('requiere atención.' if value.get('notebooklm_installed') else 'pendiente de instalar.')))
        lines.append('Búsqueda local opcional: ' + ('disponible.' if value.get('can_recall') else 'no disponible; puedes investigar con fuentes nuevas.'))
        lines.append('Carpeta de investigaciones: ' + value['runs_root'])
    if 'project' in value and 'research_history' in value:
        lines.append('Proyecto: ' + value['project'])
        labels = {'language': 'Idioma', 'discipline': 'Disciplina', 'goal': 'Objetivo',
                  'preferences': 'Preferencias', 'inclusions': 'Incluir', 'exclusions': 'Excluir',
                  'date_range': 'Período', 'budget': 'Presupuesto'}
        lines.extend(f'{label}: {value[key]}' for key, label in labels.items() if value.get(key))
        if not value.get('revision'):
            lines.append('Todavía no guardaste preferencias. Cuéntale a EZ tu tema y objetivo.')
        if value['research_history']:
            lines.append('Investigaciones guardadas (su evidencia debe revisarse al reutilizarla):')
            for row in value['research_history']:
                lines.append(f'- {row["question"]} — {row["run_id"]}')
        else:
            lines.append('Todavía no hay investigaciones en este proyecto.')
    if value.get('report_path'):
        lines.append('Informe de evidencia: ' + value['report_path'])
    if value.get('run_id'):
        lines.append('Investigación: ' + value['run_id'])
    if value.get('path'):
        lines.append('Guardada en: ' + value['path'])
    if 'phase' in value:
        lines.append('Etapa: ' + PHASE_LABELS.get(value['phase'], value['phase']))
    execution = value.get('execution', {}).get('status')
    if execution in ('waiting_user', 'waiting_service', 'cancelled', 'failed'):
        lines.append({'waiting_user': 'En espera de una acción del agente o del usuario.',
                      'waiting_service': 'En espera del servicio; el trabajo quedó guardado.',
                      'cancelled': 'Investigación detenida; puedes retomarla.',
                      'failed': 'La investigación encontró un problema.'}[execution])
    integrity = value.get('integrity', {}).get('status')
    if integrity in ('fail', 'unknown'):
        lines.append('Hay referencias o archivos que no se pudieron verificar. Revisa el diagnóstico antes de usar la respuesta.')
    if value.get('answer'):
        status = value['answer']['status']
        lines.append(ANSWER_LABELS.get(status, status))
    for blocker in value.get('blockers', []):
        source = blocker.get('source_id', 'fuente pendiente')
        scopes = ', '.join(blocker.get('scope_ids', []))
        reason = 'Falta una fuente' if blocker.get('reason') == 'missing_source' else 'Hay una decisión pendiente sobre la fuente'
        effect = 'Esa parte queda pendiente.' if blocker.get('policy') == 'hard_block' or blocker.get('reason') == 'policy_review' else 'Su ausencia debe explicarse; no bloquea por sí sola todas las conclusiones.'
        lines.append(f'{reason}: {source}. Alcance: {scopes}. {effect}')
    if 'sources' in value and 'unresolved_requirements' in value:
        pending = [s for s in value['sources'] if s.get('validation_status') != 'valid'
                   or s.get('identity_status') != 'verified' or s.get('notebook_status') != 'ready']
        lines.append(f'Fuentes con tareas pendientes: {len(pending) + len(value["unresolved_requirements"])}')
        for source in pending:
            action = ('conseguir o importar el PDF' if source.get('validation_status') != 'valid' else
                      'confirmar qué artículo y versión contiene' if source.get('identity_status') != 'verified' else
                      'continuar para comprobar su incorporación a NotebookLM')
            lines.append(f'- {source.get("title") or source["source_id"]} ({source["source_id"]}): {action}.')
        for source in value['unresolved_requirements']:
            lines.append(f'- {source.get("title") or source["source_id"]} ({source["source_id"]}): localizar la fuente solicitada.')
    for finding in value.get('findings', []):
        lines.append('Revisar: ' + finding['message'])
    if value.get('snapshot_only'):
        lines.append('Este es el último estado guardado; no se consultó el servicio ahora.')
    for claim in value.get('claims', []):
        markers = ' '.join(f'[{claim["question_id"]}:{n}]' for n in claim['citation_numbers'])
        lines.append('\n' + claim['text'] + ' ' + markers)
        for reference in claim.get('references', []):
            label = (f'{claim["question_id"]}:{reference["citation_number"]}' if reference.get('role', 'qa') == 'qa'
                     else 'verificación')
            lines.append(f'  [{label}] ' + cite(reference))
            source = reference.get('source', {})
            if source.get('pdf_path'):
                lines.append(f'  Archivo: {source["pdf_path"]} (SHA-256 {source.get("content_sha256", "")[:12]})')
            lines.append('  Pasaje: ' + reference['cited_text'])
            if reference.get('found_in_fulltext') is False:
                lines.append('  Aviso: el pasaje no se encontró literal en el texto indexado de la fuente; revísalo en el PDF.')
        for warning in claim.get('warnings', []):
            if warning['code'] == 'numbers_not_in_passages':
                lines.append('  Aviso: estos números no aparecen en los pasajes citados: ' + ', '.join(warning['values'])
                             + '. Verifícalos en el PDF.')
        if claim.get('human_check'):
            lines.append('  Revisión humana: ' + {'supported': 'respaldada', 'partial': 'respaldo parcial'}.get(
                claim['human_check']['judgement'], claim['human_check']['judgement']))
    if value.get('changes'):
        changes = value['changes']
        lines.append(f'\nCambios respecto de {changes.get("previous_run")}: {len(changes["new"])} afirmaciones nuevas, '
                     f'{len(changes["kept"])} se mantienen, {len(changes["dropped"])} ya no se sostienen.')
        lines += ['- Ya no se sostiene: ' + c['text'] for c in changes['dropped']]
        if changes.get('new_sources'):
            lines.append('Fuentes nuevas: ' + '; '.join(changes['new_sources'][:10]))
    if value.get('withheld_claims'):
        lines.append('\nNo se pudo afirmar:')
        for claim in value['withheld_claims']:
            lines.append(f'- {claim["text"]} ({REASON_LABELS.get(claim["reason"], claim["reason"])})')
    if value.get('gaps'):
        lines.append('Qué falta y por qué:')
        for gap in value['gaps']:
            causes = '; '.join(GAP_LABELS.get(c['cause'], c['cause']) + (f' ({c["title"]})' if c.get('title') else '')
                               for c in gap['causes'])
            lines.append(f'- {gap["question"]}: {causes}')
    if value.get('skipped_questions'):
        lines.append('Preguntas no consultadas:')
        for question in value['skipped_questions']:
            lines.append(f'- {question["question_id"]} ({", ".join(question["scope_ids"])}): {REASON_LABELS.get(question["reason"], question["reason"])}')
    if value.get('discovery_failures'):
        providers = ', '.join(sorted({f.get('provider') or '?' for f in value['discovery_failures']}))
        lines.append(f'Búsquedas que no se completaron: {len(value["discovery_failures"])} ({providers}). La investigación siguió con los demás proveedores.')
    if value.get('corpus_exclusions'):
        lines.append(f'Fuentes fuera del corpus: {len(value["corpus_exclusions"])}.')
        for source in value['corpus_exclusions'][:20]:
            detail = f' ({source["detail"]})' if source.get('detail') else ''
            lines.append(f'- {source.get("title") or source["source_id"]}: {REASON_LABELS.get(source["reason"], source["reason"])}{detail}')
    for row in value.get('coverage', []):
        if row['status'] != 'sufficient':
            lines.append('Pendiente (' + row['scope_id'] + '): ' + row['rationale'])
        lines.extend('Límite: ' + text for text in row.get('limitations', []))
    if value.get('next_action'):
        action = value['next_action']
        if action.startswith('El agente anfitrión debe completar'):
            action = 'Pídele a EZ que prepare el plan de esta investigación y continúe.'
        elif 'review-request.json' in action:
            action = 'EZ debe revisar las respuestas y citas de NotebookLM antes de entregarte el resultado.'
        elif 'screening-request.json' in action:
            action = 'EZ debe decidir qué candidatos son relevantes antes de descargarlos.'
        lines.append('Siguiente paso: ' + action)
    if value.get('login_command') and not value.get('can_notebook_qa'):
        lines.append('Acceso (tu agente puede abrirlo): ' + ' '.join('"' + x + '"' if ' ' in x else x for x in value['login_command']))
    return '\n'.join(lines) if lines else json.dumps(value, ensure_ascii=False, indent=2)
