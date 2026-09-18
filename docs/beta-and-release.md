# Protocolo de beta cerrada y evidencia de lanzamiento

Estado: **candidato interno; validación de lanzamiento pendiente**. Las corridas
autenticadas internas se documentan en `refurbish-progress.md`. La instalación en un
entorno Python vacío se probó en el equipo de desarrollo; eso no constituye una
prueba sobre una instalación limpia de Windows ni una beta independiente.

## Cohorte y consentimiento

Propuesta del plan: 6–10 investigadores, al menos tres disciplinas, 2–4 semanas o
30 corridas elegibles. Los participantes, el revisor de evidencia y los responsables
técnico/de producto todavía deben ser designados. No se contactará a personas ni se
enviará telemetría sin instrucciones explícitas. Mantener corpus y credenciales en
los equipos o cuentas autorizados por sus titulares.

Cada participante ejecuta onboarding, una pregunta nueva, una respuesta parcial y
una interrupción con rescate. Registrar también abandonos y fallos; no excluirlos
por producir malos resultados. Las corridas de desarrollo con servicios simulados
no entran en el denominador de E2E real ni en métricas de adopción.

## Registro por caso

Conservar localmente: identificador del candidato/artefacto y hash, sistema y Python,
fecha, caso ejecutado, duración activa, tiempo de espera externa, estado final,
códigos de fallo, decisiones y evidencia revisable. El informe compartido no incluye
preguntas privadas, PDFs, respuestas completas, rutas personales, tokens ni cookies.

`ez doctor <corrida> --metrics --json` produce conteos locales saneados. Los campos
que exigen juicio humano o prueba autenticada quedan `null`; el programa no los
infiere de un exit code. No envía el informe a ningún servicio.

El revisor independiente evalúa, por afirmación central: correspondencia con QA,
cita y pasaje; identificación de fuente y versión; alcance, población, causalidad y
limitaciones; distinción entre ausencia de evidencia y evidencia negativa. Registra
su dictamen y discrepancias. Un `PASS` mecánico no sustituye esta revisión.

## Métricas y umbrales propuestos

| Métrica | Denominador | Umbral del plan |
|---|---|---|
| Onboarding sin ayuda del desarrollador | Participantes nuevos | ≥80%; mediana ≤20 min |
| Recuperación autorizada | Obras curadas con ruta autorizada conocida | ≥90% |
| Bloqueos injustificados | Bloqueos globales revisados independientemente | ≤5%; investigar todos |
| Trazabilidad de afirmaciones centrales | Afirmaciones centrales entregadas | 100%; cero invenciones detectadas |
| Reanudación sin pérdida ni duplicación | Casos controlados / corridas de beta interrumpidas | 100% / ≥95% |
| Fronteras con deadline comprobado | Fronteras externas inventariadas | 100% |
| E2E real con resultado correcto | Corridas reales elegibles intentadas | ≥90%; separar respuesta de bloqueo justificado |
| Abandono por problemas del producto | Participantes que comienzan | ≤20% |
| Comprensión de estado y siguiente paso | Casos de comprensión evaluados | ≥90% |
| Presupuesto respetado | Corridas elegibles | 100%, con espera externa separada |

Publicar números absolutos y exclusiones junto a porcentajes. Una muestra pequeña
no acredita eficacia general en todas las disciplinas. Los umbrales y el alcance
de soporte se aprueban antes de evaluar el lanzamiento.

## Manifiesto del candidato

Antes de pedir aprobación de release, reunir una carpeta privada de evidencias y
un resumen saneado que identifique:

1. Commit o árbol exacto y SHA-256 del wheel, dependencias fijadas y versión de CLI.
2. Resultado de CI para ese candidato; instalación fuera del checkout y Windows
   limpio; matrices de políticas, migración, timeouts, integridad y rollback.
3. Al menos dos E2E autenticados completos del mismo candidato: uno desde entorno
   limpio y otro con interrupción y rescate, conservando notebook/QA y procedencia.
4. Revisión independiente de las citas y afirmaciones centrales de esas corridas.
5. Resultados de beta con denominadores; incidentes y fixes; cero P0/P1 abiertos de
   integridad, pérdida de datos o consentimiento.
6. Revisión de privacidad, condiciones de proveedores, versiones soportadas,
   instrucciones de soporte y reversión.
7. Aprobación explícita de responsables de producto y técnico, ligada al manifiesto
   concreto. La existencia de este protocolo no constituye esa aprobación.

Hasta reunir y revisar esa evidencia, no etiquetar ni publicar el producto como
listo para lanzar. Los wrappers se conservan durante la beta y el período de
compatibilidad definido en el plan; no se eliminan corridas originales.
