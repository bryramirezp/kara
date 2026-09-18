# Automático — evaluación local para 0.3.2

Fecha: 2026-09-18. Versión pública conservada: 0.3.1.

Decisión posterior a esta evaluación: publicar 0.3.2 como el regreso de
Automático para alternar entre dictados, comunicando los límites del habla mixta.
El fallo de reconocimiento mixto documentado abajo no se presenta como resuelto.
El resto del informe conserva los resultados y el estado de aquella evaluación.

## Verificación local del release 0.3.2

- Se repitieron las 99 pruebas con `KARA_TEST_UI=1`: todas aprobadas.
- Se construyeron instaladores y portables CPU/GPU. Instaladores: 76.657.243
  y 576.037.104 bytes, respectivamente; ambos declaran la versión 0.3.2.
- Se verificaron SHA256, aliases, integridad ZIP, recursos de audio y presencia
  de CUDA solo en GPU; los paquetes no incluyen las herramientas de evaluación.
- Ambos ejecutables abrieron la ventana Kara y siguieron activos durante
  15 segundos con ajustes temporales separados de los del usuario.
- No se ejecutaron los instaladores: no hay un Windows aislado disponible para
  certificar instalación limpia o actualización. El arranque no sustituye esa
  prueba ni una prueba física del micrófono.
- Documentación, enlaces de descarga y notas de release preparados para 0.3.2.

## Conclusión

La integración de Automático está implementada y sus pruebas de código y widgets
pasan. La alternancia entre grabaciones y los anglicismos del corpus funcionan.
**Los cambios completos de idioma dentro de una grabación no superan la aceptación:**
el reconocimiento puede omitir o traducir tramos, tanto con `small` en CPU como
con `large-v3-turbo` en GPU. No está listo para anunciar soporte mixto fiable.

No se añadieron correcciones de puntuación por frase: no hay identificación
fiable de idioma por frase en la API usada. Se conserva la puntuación del motor,
con limpieza genérica, sin añadir signos a partir del idioma inicial.

## Cambios y pruebas de código

- Automático es el predeterminado para ajustes nuevos. Las selecciones existentes
  se conservan, al igual que las preferencias de números y comandos.
- Se envían `language=None`, `multilingual=True`, `task="transcribe"` y prompt
  vacío. No se guarda el idioma detectado como preferencia de la próxima toma.
- Los idiomas fijos mantienen prompts, conversiones, comandos y signos existentes.
- UI de seis idiomas, controles de texto deshabilitados en Automático, restauración
  de sus valores al fijar idioma, cambios de tema y de idioma de interfaz.
- Diagnóstico con `lang="auto"`, `initial_lang` y probabilidad inicial, sin texto.

Resultado: **99 pruebas aprobadas**, incluidas 64 preexistentes; tres casos de UI
usan ventanas reales, dos de ellos en procesos nuevos para verificar arranque y
persistencia. Se prueban también errores durante la decodificación, recuperación,
silencio, remuestreo, beam CPU/GPU y consistencia de preferencias durante un dictado.

El pegado y la restauración del texto anterior del portapapeles se verifican con
dobles de prueba; no se inyectaron teclas en aplicaciones del usuario. Los tests
de UI aíslan ajustes y sustituyen micrófono, listeners y carga del modelo. No son
una prueba de captura física de audio ni de interacción completa por clics.

Comprobaciones adicionales: compilación Python y `tools/stamp_docs.py --check`
aprobadas. No se modificaron sitio, versión pública, instaladores ni dependencias
de producción. La carpeta preexistente `Kara-notebook-export/` no se modificó.

## Audio y resultados

Entorno: Python 3.11, faster-whisper 1.2.1, ctranslate2 4.7.2, NumPy 2.4.6,
NVIDIA GeForce RTX 3070 Ti (8 GB). CPU: `small`/int8/beam 1;
GPU: `large-v3-turbo`/float16/beam 5. Modelos ya almacenados localmente.

Corpus: 16 WAV sintéticos de 1 a 55 segundos, generados localmente con Piper 1.4.2,
voces `es_ES-davefx-medium` y `en_US-lessac-medium`. Los clips mixtos unen dos
hablantes sintéticos; **no prueban habla espontánea ni cambio de idioma del mismo
hablante**. No se grabó el micrófono ni se enviaron voces/transcripciones a servicios.
Se descargaron únicamente el generador y las voces públicas en `build/validation/`.

Se realizaron 64 transcripciones comparativas: 16 audios × dos modos (detección
inicial / multilingüe) × dos configuraciones. Ocho transcripciones adicionales
sin VAD en GPU comprobaron que las pérdidas observadas no se resolvían quitando
el filtro de silencio. La evaluación ejecuta `_transcribe` real de Kara;
se sustituyen únicamente las salidas de portapapeles/teclado y la pausa de pegado.

| Caso | Resultado observado |
| --- | --- |
| Español e inglés en tomas separadas | Ambos reconocidos; cifras convertidas por Whisper. |
| Anglicismos | `deploy`, `meeting`, `software`, `marketing` conservados en ambos modelos; pequeño error `el` → `del`. |
| Español → inglés, contenido equivalente | Se omite el tramo inglés en clips breves con ambos modos/modelos. |
| Inglés → español, contenido equivalente | Omisiones o traducción al español; activar multilingüe no resuelve estos casos. |
| Contenido distinto, ambas direcciones | Persisten omisiones; el problema no se limita a repetir el mismo contenido. |
| «¿Puedes revisar el deploy? Can you check the logs?» | GPU: «¿Puedes revisar el deploy? ¿Puedes revisar los logs?»; CPU: conserva sólo la primera pregunta. |
| Cambio tardío, grabación de 55 s | Se pierde el tramo inglés en ambas configuraciones. |
| Silencio | No se pega texto. |

Control del corpus: el tramo inglés aislado de `distinct_es_en.wav` se detectó
como inglés con probabilidad 0,9985 y se transcribió correctamente. No faltaba
audio inglés en el archivo. Desactivar VAD tampoco recuperó el tramo en la toma
completa. Esto localiza el fallo antes del procesamiento de texto de Kara.

Puntuación: «¿Dónde está mi teléfono?» conserva ambos signos; varias frases que
empiezan con «¿Puedes…?» terminan como afirmaciones con punto. La entonación
sintética limita esa conclusión. Añadir únicamente `¿` no resolvería una pregunta
que el motor ya convirtió en afirmación, y podría perjudicar el texto inglés.

Tiempos orientativos en modo multilingüe, excluyendo silencio: 4,2–10,9 s CPU y
0,40–1,68 s GPU. Incluyen el flujo de transcripción y limpieza, excluyen carga del
modelo y la espera artificial del pegado. Una ejecución por combinación, con
calentamiento; no son un benchmark controlado ni una garantía de latencia.

Los JSON incluyen WER léxico, sin normalizar números: `veinte` → `20` cuenta como
edición aunque sea correcto. No usar ese porcentaje solo para medir calidad;
la puntuación y la conservación de idiomas se inspeccionaron en los textos.

## Reproducción y evidencia

Desde un Python con las dependencias de Kara y pytest:

```powershell
$env:KARA_TEST_UI='1'
python -m pytest tests -q
python -m compileall -q kara.py karai18n.py tests tools/validate_auto.py
python tools/stamp_docs.py --check
```

El generador es herramienta de evaluación aislada, no dependencia de Kara:

```powershell
python -m pip install --target build/validation/tts --no-deps piper-tts==1.4.2
python tools/validate_auto.py --prepare
python tools/validate_auto.py --device cpu --model small
python tools/validate_auto.py --device cuda --model large-v3-turbo
```

`--prepare` reutiliza los WAV ya generados. `corpus.json` conserva referencias,
procedencia y hashes; la síntesis inicial es estocástica. La evaluación exige
modelos Whisper en caché y no los descarga. `--case` selecciona controles y
`--no-vad` permite reproducir el diagnóstico sin cambiar Kara.

Evidencia local (ignorada por Git):

- `build/validation/corpus.json` y sus WAV.
- `build/validation/audio-cpu-small.json` y `audio-cpu-small-extra.json`.
- `build/validation/audio-cuda-large-v3-turbo.json` y `audio-cuda-large-v3-turbo-extra.json`.
- `build/validation/audio-cuda-large-v3-turbo-extra-no-vad.json`.

Los archivos base contienen los primeros 12 casos; `extra` contiene los cuatro
controles posteriores. Una ejecución completa nueva incluye los 16 en el archivo base.

## Pendientes antes del release

1. Resolver el reconocimiento mixto antes de anunciarlo como fiable. La siguiente
   investigación debe evaluar detección/transcripción por fragmentos de voz,
   incluyendo cambios sin pausa y límites de fragmentos; no basta con puntuar
   después o con activar `multilingual=True`. No se implementó esa ampliación.
2. Validar grabaciones naturales de un mismo hablante y revisar visualmente la
   interfaz. El controlador de Computer Use falló al conectar incluso tras
   reintento y reinicio: `native pipe ... os error 2`. No se completó el recorrido
   por clics ni el pegado real en una aplicación externa.
3. Tras revisar estas conclusiones, preparar versión 0.3.2, instaladores,
   actualización del sitio, commit y pruebas del producto instalado según el
   alcance que se acuerde. No se hicieron commit, tag, push ni publicación.
