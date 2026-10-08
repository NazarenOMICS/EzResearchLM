"""The user's side of the EZ folder: one folder per project with an inbox, the reports and an index.

    <EZ>/proyectos/<proyecto>/
        LEEME.md      índice de investigaciones, con enlaces a cada informe
        bandeja/      el usuario deja aquí sus PDFs; EZ los toma cuando faltan
        informes/     copia de cada informe y su bibliografía (.bib)

The runs themselves stay in <EZ>/runs/ez-…: they are the verifiable record, and the
copies here are derived from them and regenerated on every delivery.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil

INBOX_NOTE = ('# Bandeja de PDFs\n\nDeja en esta carpeta los PDFs de artículos que EZ te pida o que quieras sumar a este '
              'proyecto. Cuando falta un artículo, EZ busca aquí primero: reconoce cada PDF por su título y su DOI. '
              'Tus archivos no se mueven ni se borran; EZ guarda una copia en la investigación.\n')


def slug(text, limit=60):
    import unicodedata
    plain = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', plain).strip('-')[:limit].strip('-') or 'general'


def home(runs_root):
    """The EZ folder: the parent of the standard runs/ folder, or the given folder itself for any other layout."""
    runs_root = Path(runs_root).resolve()
    return runs_root.parent if runs_root.name == 'runs' else runs_root


def project_dir(runs_root, project):
    return home(runs_root) / 'proyectos' / slug(project)


def link(path):
    """A file:// link the user can click to open the folder or file on their computer."""
    return Path(path).resolve().as_uri()


def ensure(runs_root, project):
    """Create the project's folders if missing and return their paths and links."""
    folder = project_dir(runs_root, project)
    inbox, reports = folder / 'bandeja', folder / 'informes'
    inbox.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    note = inbox / 'LEEME.md'
    if not note.exists():
        note.write_text(INBOX_NOTE, encoding='utf-8')
    if not (folder / 'LEEME.md').exists():
        write_index(runs_root, project)
    return {'project': str(folder), 'inbox': str(inbox), 'reports': str(reports),
            'project_link': link(folder), 'inbox_link': link(inbox), 'reports_link': link(reports)}


def report_name(contract, state):
    created = str(contract.get('created_at') or datetime.now(timezone.utc).isoformat())[:10]
    return f'{created}-{slug(contract["question"]["original"], 50)}-{state["run_id"][3:9]}'


def publish(runs_root, run_folder, contract, state, answer):
    """Copy the report and its bibliography to the project's informes/ and refresh the index."""
    from .deliver import bibliography, export_bibliography
    project = contract.get('context', {}).get('project') or 'general'
    paths = ensure(runs_root, project)
    name = report_name(contract, state)
    target = Path(paths['reports']) / (name + '.md')
    shutil.copyfile(Path(run_folder) / 'report.md', target)
    cited = [source for _, (_, source, _) in sorted(bibliography(answer).items(), key=lambda item: item[1][0]) if source]
    if cited:
        (Path(paths['reports']) / (name + '.bib')).write_text(export_bibliography(cited), encoding='utf-8')
    write_index(runs_root, project)
    return dict(paths, report=str(target), report_link=link(target))


def write_index(runs_root, project):
    """LEEME.md of a project: every research with its date, state and links."""
    from .context import history
    folder = project_dir(runs_root, project)
    folder.mkdir(parents=True, exist_ok=True)
    labels = {'complete': 'completa', 'partial': 'parcial', 'unavailable': 'en curso o sin respuesta'}
    lines = [f'# Proyecto: {project}', '',
             f'- Bandeja para tus PDFs: [bandeja/]({link(folder / "bandeja")})',
             f'- Informes: [informes/]({link(folder / "informes")})', '',
             '## Investigaciones', '', '| Fecha | Pregunta | Respuesta | Informe | Carpeta de trabajo |', '|---|---|---|---|---|']
    for row in history(Path(runs_root), project, limit=200):
        report = next(iter(sorted((folder / 'informes').glob(f'*-{row["run_id"][3:9]}.md'))), None)
        question = row['question'].replace('|', '/')
        lines.append(f'| {row["updated_at"][:10]} | {question} | {labels.get(row["saved_answer_status"], row["saved_answer_status"])} | '
                     + (f'[abrir]({link(report)})' if report else '—') + f' | [{row["run_id"]}]({link(row["path"])}) |')
    lines += ['', 'Este índice lo regenera EZ en cada entrega. Las carpetas de trabajo (`runs/ez-…`) son el registro '
              'verificable de cada investigación; no las edites a mano.', '']
    (folder / 'LEEME.md').write_text('\n'.join(lines), encoding='utf-8')
