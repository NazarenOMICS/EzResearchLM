# EZresearchLM Setup

## Preparar una investigación con EZ

EZ usa el agente anfitrión que ya tienes abierto para planificar. NotebookLM
aporta la evidencia. No necesitas otra API de modelos ni escribir archivos JSON.
La aceptación de este candidato con usuarios nuevos y Windows limpio sigue
pendiente. Las pruebas internas y CI se registran en `docs/history/refurbish-progress.md`.

Pide al agente: «EZ, prepara el entorno y ayúdame a investigar esta pregunta».
Para ver el recorrido completo, empieza por la [guía de primer uso](docs/ez-user-guide.md).
El agente sigue [la guía operativa](docs/ez-host-operator.md): comprueba capacidades,
conserva tu configuración, arma el plan y explica el siguiente paso.
EZ solo adquiere PDFs de acceso abierto o importados por el
usuario; no usa Anna's Archive ni instala un navegador para eludir restricciones de acceso.

Si partes de un clon sin instalar, el agente prepara un entorno separado:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements.lock .
.\.venv\Scripts\ez.exe setup --check
.\.venv\Scripts\ez.exe setup
```

La bienvenida aparece con `.\.venv\Scripts\ez.exe`; la guía completa, con
`.\.venv\Scripts\ez.exe --guide`. No abren un chat separado: vuelve a tu agente
para plantear la pregunta. Si `ez` no se encuentra en la terminal, usa esa ruta
completa del entorno instalado; no hace falta modificar el PATH del sistema.

Si falta NotebookLM, `ez setup --install-notebooklm` permite instalar la versión
compatible en un entorno propio. `ez setup --check` muestra la ruta del comando de
login cuando hace falta autenticar. El titular completa ese acceso en su navegador;
el agente no lee ni copia cookies. Una comprobación de acceso no acredita el E2E.

Se puede elegir otra carpeta con `--root "D:\Mis investigaciones\runs"` en cada
comando o mediante `EZRESEARCH_RUNS_ROOT`. Sin esa opción ni un override de `.env`,
EZ usa `~/.ezresearch/runs`. Conserva el mismo root al continuar.

Continúa con [la guía de usuario](docs/ez-user-guide.md).
