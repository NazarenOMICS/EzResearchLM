# Compatibilidad de corridas

| Formato | Localización | Tratamiento |
|---|---|---|
| Legacy plano | `runs/<slug>` y `Search/<slug>-papers` | Lectura sin migración implícita |
| Legacy por proyecto | `runs/<project>/<slug>` y `Search/<project>/<slug>-papers` | Usar save_dir persistido |
| Pipeline actual | `runs/<project>/<slug>` y `Search/<project>/<slug>/papers` | Conservar rutas actuales |
| Vault externo | `EZRESEARCH_VAULT` / rutas registradas | No asumir que Notes vive en el checkout |
| EZ v2 | Contrato versionado, journal y run-state | Un escritor, validación, revisión explícita |

Un `required` legacy seguía bloqueando aun con false en run-state. Al importar
se preserva `block_all_required`; no se interpreta false histórico como permiso
para omitir fuentes. En corridas nuevas el switch sí controla el gate legacy.
Ausencia del switch al continuar hereda la decisión anterior.

Un notebook existente no implica que todos los PDFs locales estén subidos.
Conflictos de notebook_id o vault_slug se muestran para revisión; nunca se
resuelven eligiendo silenciosamente el archivo más reciente.
