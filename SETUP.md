# EZresearchLM Setup

## Preparar una investigación con EZ

EZ usa el agente anfitrión que ya tienes abierto para planificar. NotebookLM
aporta la evidencia. No necesitas otra API de modelos ni escribir archivos JSON.
La aceptación con usuarios nuevos y en un Windows limpio sigue pendiente.

Pide al agente: «EZ, prepara el entorno y ayúdame a investigar esta pregunta».
Para ver el recorrido completo, empieza por la [guía de primer uso](docs/ez-user-guide.md).
El agente sigue [la guía operativa](docs/ez-host-operator.md): comprueba capacidades,
conserva tu configuración, arma el plan y explica el siguiente paso.
EZ solo adquiere PDFs de acceso abierto o importados por el
usuario; no usa Anna's Archive ni instala un navegador para eludir restricciones de acceso.

## Dónde se instala

Si existe `~/.ezresearch/install.json`, EZ ya está instalado y ese archivo dice dónde está
su `ez`. Si no, el agente te pregunta dónde instalarlo (propone `Documents\EZresearchLM`),
clona el repositorio ahí y prepara un entorno separado dentro del clon:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements.lock .
.\.venv\Scripts\ez.exe setup --check
.\.venv\Scripts\ez.exe setup
```

`ez setup` escribe `~/.ezresearch/install.json`, así un chat nuevo encuentra EZ sin
preguntarte. La bienvenida aparece con `.\.venv\Scripts\ez.exe`; la guía completa, con
`.\.venv\Scripts\ez.exe --guide`. No abren un chat separado: vuelve a tu agente para
plantear la pregunta. Si `ez` no se encuentra en la terminal, usa esa ruta completa del
entorno instalado; no hace falta modificar el PATH del sistema.

## NotebookLM

Si falta NotebookLM, `ez setup --install-notebooklm` instala la versión compatible en un
entorno propio. Para iniciar sesión, `ez setup --login` abre una ventana de Google donde
entras tú; el agente no lee ni copia cookies. EZ informa acceso listo solo cuando la salida de
`notebooklm list --json` tiene el formato esperado. Esa señal no acredita una corrida completa,
una respuesta con pasajes ni una afirmación verificada.

En una investigación, un marcador válido solo identifica un registro. Un pasaje localizado
aparece literalmente en el texto cotejado; una entrega directa conserva lo que respondió NotebookLM junto
con su pasaje citado, aunque la localización quede pendiente; una afirmación verificada pasó un cotejo automático aparte. La revisión humana
se registra por separado.

## Carpetas

Tus proyectos (bandeja de PDFs, informes e índice) quedan en una carpeta visible que eliges
con `ez setup --projects-dir "<carpeta>"`; el agente propone
`Documents\EZresearchLM\projects`. EZ copia los proyectos existentes, verifica la copia y
después cambia la configuración; conserva la carpeta de origen. Si hay una colisión o falla
la copia, conserva el origen y la ruta configurada. La organización está en
[docs/carpetas.md](docs/carpetas.md).

Las corridas se guardan en `~/.ezresearch/runs`. Se puede elegir otra carpeta con
`--root "D:\Mis investigaciones\runs"` en cada comando o mediante `EZRESEARCH_RUNS_ROOT`.
Conserva el mismo root al continuar.

Continúa con [la guía de usuario](docs/ez-user-guide.md).
