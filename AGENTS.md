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
- Comprueba que nombres de artefactos, enlaces, versiones y comandos coincidan entre código, documentación y pipeline.

## Artefactos versionados

- Todo archivo distribuible debe llevar su versión en el nombre, por ejemplo
  `Kara-Setup-<version>.exe`.
- No generes aliases ni copias públicas con nombres sin versión, como
  `Kara-Setup.exe`.
- Publica, documenta y calcula hashes sobre el artefacto versionado.
- Antes de un release, confirma que la versión del nombre coincide con la
  versión declarada por la aplicación, el tag y los enlaces de descarga.

## Disciplina de build y release

- `dist/` es temporal, no un archivo histórico: el historial vive en Git,
  tags y releases. Límpialo solo antes de un build y tras confirmar que no
  hay procesos de PyInstaller, Inno Setup o validación en curso.
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
- Los tags y assets publicados son inmutables: nunca usar `--clobber` ni
  reemplazar un asset. Si un release publicado falla, publicar una versión
  nueva.

### Flujo operativo de publicación

1. Trabaja y valida en una rama o en `main`; no crees un tag hasta que el
   árbol de trabajo esté revisado, el changelog tenga la sección de la versión
   y `__version__`, documentación y nombres de artefactos coincidan.
2. Confirma los cambios y sube primero el commit a `main`. Comprueba que el
   commit remoto es exactamente el que se quiere liberar.
3. Con autorización explícita, crea un tag anotado e inmutable con SemVer:
   `git tag -a vX.Y.Z -m "Kara X.Y.Z"`, y sube únicamente ese tag con
   `git push origin vX.Y.Z`.
4. El tag dispara `.github/workflows/release.yml` en un runner Windows limpio.
   El workflow verifica versión y documentación, construye CPU y GPU, ejecuta
   pruebas, valida instalación/migración, firma si existe la credencial y
   adjunta ambos instaladores más `SHA256SUMS.txt` a un **draft release**.
5. Revisa ese draft en la lista de Releases: título, notas tomadas de
   `CHANGELOG.md`, los dos nombres versionados, hashes y firmas. Solo entonces
   publícalo. Un release publicado no se modifica; un error requiere una
   versión nueva.
6. Para ensayar el pipeline sin crear tag, usa `workflow_dispatch`; sus
   artefactos quedan como artefactos temporales de Actions, no como release.

## Auditoría antes de release

Antes de recomendar una publicación, revisa:

1. Versión y estado de Git.
2. Changelog, README y documentación de instalación.
3. Dependencias, build y pipeline de publicación.
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
