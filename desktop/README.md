# Extensión de Claude Desktop (experimental)

Permite usar EZ desde Claude Desktop, sin terminal. Claude Desktop instala las
dependencias con `uv`; la persona no necesita instalar Python. El agente es la propia
suscripción de Claude del usuario y NotebookLM se abre en su navegador: la extensión
no guarda credenciales.

## Estado

Probado offline: el servidor MCP responde por stdio, registra sus 13 herramientas,
el manifiesto pasa `mcpb validate` y el paquete se resuelve con `uv`. **No probado
todavía en Claude Desktop real ni en Windows limpio**, y el inicio de sesión de
NotebookLM desde la extensión (`ez_login`) está sin validar.

## Construir

```
npx @anthropic-ai/mcpb validate desktop/manifest.json
npx @anthropic-ai/mcpb pack desktop ezresearchlm.mcpb
```

`desktop/pyproject.toml` instala EZ desde la rama `main` del repositorio. Para probar
otra rama, cambiar la referencia después de `@` antes de empaquetar. No subir el
archivo `.mcpb` al repositorio.

## Instalar

Abrir el archivo `.mcpb` con Claude Desktop (doble clic o Configuración → Extensiones)
y aceptar la instalación. Las investigaciones se guardan en `~/.ezresearch/runs`
(o en `EZRESEARCH_RUNS_ROOT`).

## Cómo trabaja

Cada herramienta ejecuta el mismo comando `ez` que usaría un agente en la terminal,
así que las reglas de cribado, verificación e integridad son idénticas. Como Claude
Desktop no lee archivos locales, `ez_read` muestra los archivos de trabajo de una
investigación y `ez_submit` guarda los documentos que prepara el agente.
