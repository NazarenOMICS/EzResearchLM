"""Plain-language views of saved facts; never infer evidence or change state."""
import json


ANSWER_LABELS = {
    'unavailable': 'Aún no hay una respuesta con respaldo revisado.',
    'partial': 'Respuesta parcial: hay partes respaldadas y otras pendientes.',
    'complete': 'Respuesta completa para el alcance acordado, con sus límites.',
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
            lines.append(f'  [{claim["question_id"]}:{reference["citation_number"]}] Fuente NotebookLM: {reference["source_id"]}')
            lines.append('  Pasaje: ' + reference['cited_text'])
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
        lines.append('Siguiente paso: ' + action)
    if value.get('login_command') and not value.get('can_notebook_qa'):
        lines.append('Acceso (tu agente puede abrirlo): ' + ' '.join('"' + x + '"' if ' ' in x else x for x in value['login_command']))
    return '\n'.join(lines) if lines else json.dumps(value, ensure_ascii=False, indent=2)
