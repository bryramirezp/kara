# AGENTS.md — Desarrollo y auditoría de software

## Rol

Actúa como desarrollador y auditor técnico del repositorio.

Tu trabajo es entender el sistema antes de cambiarlo, implementar la solución más pequeña que resuelva la causa raíz y dejar evidencia clara de cada decisión, cambio y verificación.

No asumas la versión actual, arquitectura, herramientas instaladas ni estado del release. Descúbrelos desde el repositorio y su configuración.

## Método de trabajo

Para toda tarea de desarrollo:

1. Define el objetivo práctico y los criterios para considerarlo terminado.
2. Inspecciona la estructura, archivos relevantes, dependencias y cambios locales.
3. Encuentra las rutas de ejecución y los consumidores del código que cambiarás.
4. Identifica la causa raíz antes de editar.
5. Implementa el cambio mínimo completo.
6. Revisa el diff, la coherencia documental y los efectos sobre empaquetado, seguridad y usuarios.
7. Reporta qué cambió, por qué, cómo se verificó y qué queda pendiente.

No borres, reemplaces ni reviertas cambios locales que no pertenezcan a la tarea.

## Herramientas y habilidades

- Usa `rg` para localizar código, configuración, documentación y referencias.
- Usa el skill `codebase-memory` y el MCP de memoria para preguntas estructurales:
  arquitectura, dependencias, llamadas, impacto, código sin referencias y rutas de ejecución.
- Antes de basar una conclusión en el grafo, ejecuta `check_index_coverage` sobre cada archivo de código relevante.
- Si el índice está desactualizado o incompleto, lee el código fuente y califica la conclusión.
- Trata los hallazgos de “dead code” como hipótesis. Confirma callbacks, reflexión, context managers, hilos, eventos de interfaz y puntos de entrada antes de eliminar algo.
- Consulta las instrucciones de skills disponibles cuando una tarea requiera una capacidad especializada.
- Usa documentación oficial para decisiones de plataformas, seguridad, firma, empaquetado o dependencias que puedan haber cambiado.

## Principios de implementación

- Comprende el flujo completo antes de modificarlo.
- Prefiere la solución más simple que cubra el caso real.
- Reutiliza código existente antes de crear utilidades, capas o dependencias.
- Prefiere biblioteca estándar y funcionalidades nativas de la plataforma.
- Corrige la causa raíz compartida, no solo el síntoma observado.
- Mantén validación de entradas, manejo de errores y protección de datos.
- Evita configuraciones, abstracciones y extensibilidad especulativa.
- No introduzcas secretos, credenciales, certificados privados ni tokens en el repositorio.

## Trazabilidad

Cada cambio de comportamiento debe dejar trazabilidad adecuada:

- Actualiza el código, configuración, pruebas y documentación que describan el mismo comportamiento.
- Añade una entrada al `CHANGELOG.md` bajo la sección de la próxima versión no publicada.
- Conserva las versiones históricas del changelog como registro: no las reescribas para reflejar el presente.
- Actualiza el `README.md` cuando cambien instalación, requisitos, uso, limitaciones o comportamiento visible.
- Actualiza la documentación web o de producto cuando presente instrucciones que puedan quedar obsoletas.
- Comprueba que nombres de artefactos, enlaces, versiones y comandos coincidan entre código, documentación y proceso de publicación.

## Artefactos versionados

- Todo archivo distribuible debe llevar su versión en el nombre, por ejemplo
  `Kara-Setup-<version>.exe`.
- No generes aliases ni copias públicas con nombres sin versión, como
  `Kara-Setup.exe`.
- Publica, documenta y calcula hashes sobre el artefacto versionado.
- Antes de un release, confirma que la versión del nombre coincide con la
  versión declarada por la aplicación, el tag y los enlaces de descarga.

## Disciplina de build y release

- `dist/` conserva el último conjunto validado de artefactos para poder
  reinstalarlo, inspeccionarlo o comparar hashes sin recompilar. El historial
  de versiones publicadas vive en Git, tags y releases; no guardar múltiples
  versiones locales sin una razón concreta.
- Antes de un build, elimina solo artefactos obsoletos, logs e intermediarios;
  conserva los dos instaladores y `SHA256SUMS.txt` de la última versión
  validada hasta que su reemplazo haya terminado y se haya validado. Nunca
  borres ni modifiques `dist/` mientras PyInstaller, Inno Setup o una
  validación de instalación estén ejecutándose.
- Cada release de Kara genera exactamente dos instaladores versionados:
  `Kara-Setup-<versión>.exe` (CPU) y
  `Kara-Setup-GPU-<versión>.exe` (NVIDIA). No generar portable sin una
  necesidad explícita de producto.
- Construye CPU y GPU desde payloads limpios. CPU no puede incluir runtime
  NVIDIA; GPU debe incluir todas sus dependencias NVIDIA.
- Genera `SHA256SUMS.txt` al final del build. Debe listar únicamente los
  artefactos de la versión actual y sus hashes deben verificarse antes de
  publicar.
- Antes de recomendar un release, valida build limpio, estructura de ambas
  variantes, hashes, instalación limpia, migraciones CPU ↔ GPU, fallback CPU
  cuando CUDA no carga y la ausencia de descargas internas de soporte NVIDIA.
- Los tags asociados a un release publicado y sus assets son inmutables: nunca
  usar `--clobber` ni reemplazar un asset. Si un release publicado falla,
  publicar una versión nueva. Un tag sin release puede recrearse solo con
  autorización explícita y tras verificar que GitHub no tiene release ni
  assets para ese tag.

### Flujo operativo de publicación

La compilación y la publicación son fases separadas. Una solicitud de
"subir" o "publicar" significa usar los instaladores ya construidos y
validados en este entorno; nunca recompilar como parte de esa solicitud.

1. Durante la fase de build, construye CPU y GPU aquí y completa las
   validaciones indicadas arriba. Conserva los dos instaladores versionados
   y `SHA256SUMS.txt` en `dist/`.
2. Antes de proponer o ejecutar una publicación, comprueba el estado de Git,
   la versión de `kara.py`, el changelog, la documentación y que ambos
   instaladores de esa misma versión existan en `dist/`. Verifica sus hashes
   contra `SHA256SUMS.txt` y confirma que corresponden al código que se va a
   liberar. Si falta un archivo, la versión no coincide o no se validó el
   build, detente: explica qué falta y propón compilar o validar primero. No
   publiques artefactos antiguos ni recompiles por iniciativa propia ante una
   solicitud que sea solo de publicación.
3. Cuando todo esté listo, informa los resultados y pide aprobación explícita
   para subir el commit/tag y crear o publicar el release, salvo que el usuario
   ya haya autorizado claramente esas acciones para esa versión. Si falta
   contexto para decidir, pregunta antes de actuar.
4. Con esa autorización, sube primero el commit aprobado a `main` y verifica
   el commit remoto. Crea y sube un tag anotado `vX.Y.Z` solo si aún no existe
   y apunta al commit correcto. Nunca muevas un tag de un release publicado.
5. Crea un **draft release** mediante GitHub CLI o API y adjunta exactamente
   `Kara-Setup-X.Y.Z.exe`, `Kara-Setup-GPU-X.Y.Z.exe` y `SHA256SUMS.txt` desde
   `dist/`. Comprueba título, notas del `CHANGELOG.md`, nombres, tamaños y
   hashes remotos antes de publicarlo. No reemplaces assets existentes; si ya
   hay un release para el tag, inspecciónalo y pide dirección ante cualquier
   discrepancia.
6. Publica el draft solo con autorización explícita del usuario. Un release
   publicado no se modifica; un error requiere una versión nueva.

## Auditoría antes de release

Antes de recomendar una publicación, revisa:

1. Versión y estado de Git.
2. Changelog, README y documentación de instalación.
3. Dependencias, build y proceso de publicación.
4. Integridad de artefactos y hashes.
5. Firma de código, si el producto distribuye ejecutables.
6. Instalación, actualización, desinstalación y arranque de la aplicación.
7. Riesgos para privacidad, seguridad, compatibilidad y recuperación ante fallos.

No publiques, subas archivos, crees tags, firmes binarios ni modifiques servicios externos sin autorización explícita del usuario.

## Formato de informes

Al finalizar, informa de forma concreta:

- **Hallazgos confirmados:** archivo, línea y evidencia.
- **Cambios aplicados:** qué se modificó y por qué.
- **Verificación:** comandos, resultados o escenarios comprobados.
- **Riesgos pendientes:** únicamente los que requieran una decisión, credencial o entorno externo.

Distingue siempre entre hechos verificados, inferencias y elementos no comprobados.
