#!/usr/bin/env python3
"""Compile NotebookLM source guides into a research brief and question template."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VAULT = Path.cwd()
EZRESEARCH_ROOT = Path(os.environ.get("EZRESEARCH_ROOT", Path(__file__).resolve().parents[2]))
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"
DEFAULT_HAIKU_MODEL = "claude-haiku-4-5-20251001"
GEMINI_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language.retriever",
]

QUESTION_THEMES = [
    ("methodology", "Metodologia y protocolos experimentales", 3),
    ("mic_ranges", "Rangos de MIC reportados por especie", 3),
    ("method_comparison", "Comparacion entre metodos (REMA, BMD, MGIT)", 3),
    ("breakpoints", "Puntos de corte y criterios de resistencia", 2),
    ("clinical_outcomes", "Resultados clinicos y correlacion con MIC", 3),
    ("limitations", "Limitaciones de los estudios", 2),
    ("gaps", "Lagunas de evidencia e investigacion futura", 2),
    ("mechanisms", "Mecanismo de accion y resistencia", 2),
]


def parse_source_file(content: str) -> tuple[str, str, str]:
    title_m = re.search(r"^# (.+)$", content, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else "Unknown"

    date_m = re.search(r"^date:\s*(\S+)", content, re.MULTILINE)
    doc_date = date_m.group(1) if date_m else ""

    guide_m = re.search(r"## Source Guide\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    guide = guide_m.group(1).strip() if guide_m else ""

    return title, doc_date, guide


def candidate_env_files() -> list[Path]:
    candidates: list[Path] = []
    for env_var in ("QUESTION_GEN_ENV_FILE", "PAPER_SEARCH_MCP_ENV_FILE", "EZRESEARCH_ENV_FILE"):
        raw = os.environ.get(env_var, "").strip()
        if raw:
            candidates.append(Path(raw).expanduser())

    candidates.extend(
        [
            Path.cwd() / ".env",
            EZRESEARCH_ROOT / ".env",
        ]
    )

    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def load_env_file() -> None:
    for env_file in candidate_env_files():
        if not env_file.exists() or not env_file.is_file():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)
        return


def build_brief_lines(slug: str, goal: str, n_questions: int, sources: list[dict[str, str]]) -> list[str]:
    lines = [
        f"# Research Brief - {slug}",
        "",
        f"**Fecha:** {date.today().isoformat()}  ",
        f"**Fuentes:** {len(sources)} papers  ",
        f"**Objetivo:** {goal}",
        "",
        "---",
        "",
        "## Papers en el Notebook",
        "",
    ]

    for idx, source in enumerate(sources, 1):
        lines.append(f"### {idx}. {source['title']}")
        if source["date"]:
            lines.append(f"*{source['date']}*")
        lines.append("")
        if source["guide"]:
            preview = source["guide"][:500].rstrip()
            if len(source["guide"]) > 500:
                preview += "..."
            lines.append(preview)
        lines.append("")

    lines += [
        "---",
        "",
        "## Instrucciones para el Agente",
        "",
        "El objetivo de investigacion es:",
        f"> {goal}",
        "",
        f"Genera **{n_questions} preguntas profundas y trazables** que sirvan directamente a ese objetivo.",
        "Las preguntas deben derivar del objetivo, no de temas genericos.",
        "",
        "Proceso sugerido:",
        "1. Identificar que necesita saber el usuario para cumplir el objetivo",
        "2. Priorizar preguntas comparativas, integradoras o causales, no solo descriptivas",
        "3. Verificar que los papers del notebook contienen evidencia suficiente para sostener respuestas densas en citas",
        "4. Distribuir las preguntas usando los temas como guia estructural (no como fin)",
        "",
        "Criterios por pregunta:",
        "- Debe exigir sintesis o comparacion entre multiples fuentes cuando sea posible",
        "- Evitar preguntas triviales o demasiado literales",
        "- Formulada para obtener respuestas densas en citas y utiles para escritura academica",
        "- En espanol tecnico",
        "- Directamente util para el objetivo de investigacion",
        "",
        "Temas como guia estructural (no cubrir por obligacion, sino si el objetivo lo requiere):",
    ]
    for theme_id, theme_label, _count in QUESTION_THEMES:
        lines.append(f"  - {theme_label} (`{theme_id}`)")

    lines += [
        "",
        f"Escribe las preguntas en `/tmp/questions-{slug}.json`.",
        "Formato: campo `question` de cada objeto, `status` queda `pending`.",
        "",
        "Luego ejecutar:",
        "```",
        f"python batch_ask.py --questions /tmp/questions-{slug}.json --sources /tmp/notebooklm-sources.json",
        "```",
    ]
    return lines


def build_question_template(slug: str, goal: str, n_questions: int) -> dict[str, Any]:
    question_list: list[dict[str, Any]] = []
    theme_cycle: list[str] = []
    for theme_id, _theme_label, count in QUESTION_THEMES:
        theme_cycle.extend([theme_id] * count)
    while len(theme_cycle) < n_questions:
        for theme_id, _theme_label, _count in QUESTION_THEMES:
            theme_cycle.append(theme_id)
            if len(theme_cycle) >= n_questions:
                break

    for idx in range(1, n_questions + 1):
        question_list.append(
            {
                "id": idx,
                "theme": theme_cycle[idx - 1] if idx - 1 < len(theme_cycle) else "methodology",
                "question": None,
                "status": "pending",
            }
        )

    return {
        "slug": slug,
        "goal": goal,
        "dashboard": slug.replace("-", " ").title(),
        "questions": question_list,
    }


def build_prompt(brief: str, n_questions: int) -> str:
    return (
        "Lee el brief y genera preguntas de investigacion profundas, comparativas y trazables.\n\n"
        "Reglas:\n"
        "- Devuelve UNICAMENTE un array JSON valido.\n"
        f"- Debe tener exactamente {n_questions} elementos.\n"
        "- Cada elemento debe ser un string con una sola pregunta.\n"
        "- No devuelvas markdown, explicaciones ni texto extra.\n"
        "- Las preguntas deben estar en espanol tecnico.\n"
        "- Cada pregunta debe servir directamente al objetivo de investigacion.\n"
        "- PriorizÃ¡ preguntas que fuercen comparacion, sintesis entre fuentes, explicacion causal o identificacion de vacios.\n"
        "- EvitÃ¡ preguntas demasiado obvias, superficiales o respondibles con una sola frase.\n\n"
        "Brief:\n"
        f"{brief}\n"
    )


def parse_json_array(output: str) -> list[Any]:
    cleaned = output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON array found in model output")
    return json.loads(cleaned[start : end + 1])


def normalize_generated_questions(payload: list[Any], n_questions: int) -> list[str]:
    normalized: list[str] = []
    for item in payload:
        if isinstance(item, str):
            question = item.strip()
        elif isinstance(item, dict):
            question = str(item.get("question") or "").strip()
        else:
            question = ""
        if not question:
            raise ValueError("Model returned an empty question")
        normalized.append(question)

    if len(normalized) != n_questions:
        raise ValueError(f"Expected {n_questions} questions, got {len(normalized)}")
    return normalized


def fill_template_questions(template: dict[str, Any], generated: list[str]) -> dict[str, Any]:
    updated = json.loads(json.dumps(template))
    for item, question in zip(updated["questions"], generated, strict=True):
        item["question"] = question
    return updated


def oauth_client_secret_candidates() -> list[Path]:
    env_candidates = [
        os.environ.get("GEMINI_OAUTH_CLIENT_SECRET_FILE", "").strip(),
        os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_FILE", "").strip(),
    ]
    path_candidates = [Path(raw).expanduser() for raw in env_candidates if raw]
    path_candidates.extend(
        [
            Path.cwd() / "client_secret.json",
            Path.cwd().parent / "client_secret.json",
            EZRESEARCH_ROOT / "client_secret.json",
            Path.home() / ".gemini-oauth" / "client_secret.json",
        ]
    )

    wildcard_roots = [
        Path.cwd(),
        Path.cwd().parent,
        EZRESEARCH_ROOT,
    ]
    for root in wildcard_roots:
        if root.exists() and root.is_dir():
            for candidate in sorted(root.glob("client_secret*.json")):
                path_candidates.append(candidate)
    return path_candidates


def find_oauth_client_secret_file() -> Path | None:
    for candidate in oauth_client_secret_candidates():
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def resolve_project_id(client_secret_path: Path) -> str:
    for env_var in ("GEMINI_OAUTH_PROJECT_ID", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"):
        value = os.environ.get(env_var, "").strip()
        if value:
            return value

    try:
        payload = json.loads(client_secret_path.read_text(encoding="utf-8"))
        for top_key in ("installed", "web"):
            project_id = str(payload.get(top_key, {}).get("project_id") or "").strip()
            if project_id:
                return project_id
    except Exception:
        pass
    return ""


def resolve_token_file(client_secret_path: Path) -> Path:
    env_path = os.environ.get("GEMINI_OAUTH_TOKEN_FILE", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return client_secret_path.with_name("token.json")


def load_oauth_credentials(interactive: bool = True) -> tuple[Any, str, Path, Path]:
    client_secret_path = find_oauth_client_secret_file()
    if not client_secret_path:
        raise RuntimeError(
            "No client_secret.json found. Place it in the current directory, "
            "in EZRESEARCH_ROOT, or set GEMINI_OAUTH_CLIENT_SECRET_FILE."
            "or set GEMINI_OAUTH_CLIENT_SECRET_FILE."
        )

    try:
        from google.auth.transport.requests import Request  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError as exc:
        raise RuntimeError("google-auth-oauthlib is not installed in the selected Python environment") from exc

    token_path = resolve_token_file(client_secret_path)
    project_id = resolve_project_id(client_secret_path)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GEMINI_OAUTH_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not interactive:
                raise RuntimeError("OAuth credentials are missing and interactive login is disabled")
            print(
                "Gemini OAuth: abriendo el navegador para autorizar acceso. "
                "Si no se abre, segui la URL que muestre Google.",
                file=sys.stderr,
            )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), GEMINI_OAUTH_SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    if not project_id:
        raise RuntimeError(
            "No pude resolver el project_id para Gemini OAuth. "
            "Defini GEMINI_OAUTH_PROJECT_ID o GOOGLE_CLOUD_PROJECT."
        )

    return creds, project_id, client_secret_path, token_path


def extract_text_from_gemini_response(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def run_ollama(prompt: str, model: str) -> str:
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Ollama failed with exit code {result.returncode}")
    return result.stdout


def run_gemini_with_api_key(prompt: str, model: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed in the selected Python environment") from exc

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", "") or ""
    if not text:
        raise RuntimeError(f"Gemini returned an empty response for model {model}")
    return text


def run_gemini_with_oauth(prompt: str, model: str) -> str:
    creds, project_id, client_secret_path, token_path = load_oauth_credentials(interactive=True)
    if not getattr(creds, "token", None):
        raise RuntimeError("OAuth credentials did not return an access token")

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
            "x-goog-user-project": project_id,
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        },
        timeout=120,
    )

    if response.status_code >= 400:
        snippet = response.text[:600]
        raise RuntimeError(
            "Gemini OAuth request failed "
            f"(project={project_id}, client_secret={client_secret_path}, token={token_path}): {snippet}"
        )

    text = extract_text_from_gemini_response(response.json())
    if not text:
        raise RuntimeError(f"Gemini OAuth returned an empty response for model {model}")
    return text


def run_haiku(prompt: str, model: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as exc:
        raise RuntimeError("anthropic is not installed in the selected Python environment") from exc

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", "")
        if text:
            parts.append(text)
    if not parts:
        raise RuntimeError(f"Haiku returned an empty response for model {model}")
    return "\n".join(parts)


def run_gemini_backend(prompt: str, model: str, use_oauth: bool) -> str:
    if use_oauth:
        return run_gemini_with_oauth(prompt, model)
    return run_gemini_with_api_key(prompt, model)


def can_use_gemini_oauth() -> bool:
    return find_oauth_client_secret_file() is not None


def generate_questions_with_ai(brief: str, n_questions: int, ai_model: str) -> list[str]:
    prompt = build_prompt(brief, n_questions)
    backend, _, model_suffix = ai_model.partition(":")
    backend = backend.strip().lower()
    model_suffix = model_suffix.strip()

    if backend in {"gemini", "gemini-oauth"}:
        primary_model = model_suffix or DEFAULT_GEMINI_MODEL
        models_to_try = [primary_model]
        if primary_model == DEFAULT_GEMINI_MODEL:
            models_to_try.append(GEMINI_FALLBACK_MODEL)

        use_oauth = backend == "gemini-oauth" or (
            not os.environ.get("GEMINI_API_KEY", "").strip() and can_use_gemini_oauth()
        )

        errors: list[str] = []
        for model_name in models_to_try:
            try:
                output = run_gemini_backend(prompt, model_name, use_oauth=use_oauth)
                return normalize_generated_questions(parse_json_array(output), n_questions)
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")
        raise RuntimeError(" | ".join(errors))

    if backend == "ollama":
        model_name = model_suffix or "gemma4:12b"
        output = run_ollama(prompt, model_name)
        return normalize_generated_questions(parse_json_array(output), n_questions)

    if backend == "haiku":
        model_name = model_suffix or DEFAULT_HAIKU_MODEL
        output = run_haiku(prompt, model_name)
        return normalize_generated_questions(parse_json_array(output), n_questions)

    raise RuntimeError(f"Unsupported --ai-model backend: {ai_model}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate research brief and question template")
    parser.add_argument("--slug", required=True, help="Notebook slug (kebab-case)")
    parser.add_argument("--goal", required=True, help="Research objective for the questions")
    parser.add_argument("--n", type=int, default=20, help="Target number of questions (default 20)")
    parser.add_argument("--out-dir", default="/tmp", help="Output directory (default /tmp)")
    parser.add_argument(
        "--ai-model",
        default=None,
        help=(
            "Optional backend: gemini, gemini:<model>, gemini-oauth, gemini-oauth:<model>, "
            "haiku, haiku:<model>, ollama:<model>"
        ),
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the generated questions as a compact JSON array on stdout",
    )
    args = parser.parse_args()

    load_env_file()

    sources_dir = VAULT / "Notes" / "NotebookLM" / args.slug / "Sources"
    if not sources_dir.exists():
        print(f"ERROR: {sources_dir} not found. Run import_sources.py first.", file=sys.stderr)
        sys.exit(1)

    source_files = sorted(sources_dir.glob("*.md"))
    if not source_files:
        print(f"ERROR: No .md files in {sources_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {len(source_files)} sources...", file=sys.stderr)

    sources: list[dict[str, str]] = []
    for file_path in source_files:
        content = file_path.read_text(encoding="utf-8")
        title, doc_date, guide = parse_source_file(content)
        sources.append({"title": title, "date": doc_date, "guide": guide})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    brief_lines = build_brief_lines(args.slug, args.goal, args.n, sources)
    brief_path = out_dir / f"brief-{args.slug}.md"
    brief_path.write_text("\n".join(brief_lines), encoding="utf-8")
    print(f"Brief -> {brief_path}", file=sys.stderr)

    template = build_question_template(args.slug, args.goal, args.n)
    questions_path = out_dir / f"questions-{args.slug}.json"
    questions_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Template -> {questions_path}", file=sys.stderr)

    if not args.ai_model:
        print(f"\nListo. Leer brief y completar questions-{args.slug}.json, luego correr batch_ask.py")
        return

    brief_text = brief_path.read_text(encoding="utf-8")
    try:
        generated = generate_questions_with_ai(brief_text, args.n, args.ai_model)
        filled = fill_template_questions(template, generated)
        questions_path.write_text(json.dumps(filled, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"AI questions -> {questions_path}", file=sys.stderr)
        if args.stdout_json:
            print(json.dumps(generated, ensure_ascii=False))
        print(f"\nListo. Preguntas generadas con {args.ai_model}.")
    except Exception as exc:
        print(f"WARNING: AI generation failed, keeping blank template: {exc}", file=sys.stderr)
        if args.stdout_json:
            print("[]")
        print(f"\nListo. Brief generado y template vacio preservado en {questions_path}.")


if __name__ == "__main__":
    main()

