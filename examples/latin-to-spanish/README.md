# Latín → español: una microfábula completa

**Borrador. Demostración mecánica, no edición certificada ni publicable.**

*Lucerna communis* («La lámpara compartida») es una obra original breve,
compuesta para este ejemplo: un título y seis líneas numeradas de prosa.
No es una fábula de Esopo o Fedro, ni un fragmento presentado como obra
completa. El texto se compuso para el proyecto; no se obtuvo ni utilizó
ningún texto remoto.

El proyecto dedica expresamente el texto latino, su instantánea y las dos
versiones españolas a **CC0 1.0**; véase [CC0.md](CC0.md). La clasificación
`public-domain` del perfil corresponde aquí a esa dedicación expresa, no a
la antigüedad de la obra ni a un dictamen jurídico. El manifiesto distingue
los derechos de la obra y de su transcripción.

## Contenido

- `works/lucerna-communis.md`: la obra completa en `Original`, `Literaria`
  y `Clara`, con procedencia y estado de borrador en los metadatos.
- `sources/raw/lucerna-communis.txt`: instantánea UTF-8 original sin cambios.
- `sources/manifest.json`: proveedor local, edición, identificador más
  SHA-256, derechos, límites de la obra, regla de limpieza y contribución.
- `editions/literaria.md` y `editions/clara.md`: los dos borradores de
  registro retenidos; sus textos coinciden con los del documento de obra.
- `champollion.json`: usa `../../profiles/latin-to-spanish.json`, el perfil
  distribuido en este repositorio. No contiene rutas privadas absolutas.

La limpieza solo retira la primera línea (título) y la siguiente línea
vacía de la instantánea. Todo lo restante es `Original`: no se corrigen ni
normalizan sus seis líneas. Cada registro lleva una unidad titulada
`Lucerna communis`, los marcadores `1.` a `6.` en el mismo orden y seis
líneas de texto. La última línea es el final completo de la obra.

## Registros y límites de la demostración

**Literaria:** español literario contemporáneo, con la imagen, la estructura
retórica y el contenido completo del latín. **Clara:** vocabulario familiar
y sintaxis directa, sin resumen ni explicación añadida.

Ambos textos se compusieron en pases directos del latín; no se obtuvo uno
retocando el otro. Los hizo el mismo asistente de IA en una sesión, sin
aislamiento entre colaboradores: no se afirma cumplimiento del despacho
separado WRK-2 ni una independencia demostrada por revisión. No se
consultaron traducciones externas, ayudas de comprensión ni testigos de
reparación. La declaración de producción se conserva en el manifiesto.

No hay lectura en voz alta ni revisión humana/modelo independiente de
sentido, términos o correspondencia semántica de los extremos. `reviews`
es una lista vacía deliberadamente; no es un registro de aprobación. La
integridad del archivo y la alineación de números no prueban fidelidad.

## Ejecutar sin red

Desde la raíz del repositorio, con Python 3.9 o posterior:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m champollion check \
  --root examples/latin-to-spanish
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m champollion report \
  --root examples/latin-to-spanish --json
```

O desde esta carpeta:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m champollion check --root .
```

Si el CLI está instalado, puede sustituirse `PYTHONPATH=… python3 -m
champollion` por `champollion`. Las rutas del perfil se resuelven desde la
raíz del ejemplo: funciona en otro checkout conservando la estructura del
repositorio. Si se copia solo este ejemplo, hay que proporcionar también
el perfil y actualizar `profile_path`; no se incluye una copia divergente.

Un resultado mecánico sin errores **no** aprueba la publicación: el informe
JSON debe seguir mostrando el bloqueo por ausencia de revisión VER-11.
El perfil desactiva las listas inglesas y las heurísticas de longitud y
copia. También declara `spelling_profile: null`: no se distribuye un
diccionario de variantes españolas, por lo que esa política queda
explícitamente desactivada, no aprobada. Eso tampoco evalúa la calidad del
español. Antes de publicar hacen falta las revisiones VER-10/VER-11 y la
resolución honesta de cualquier hallazgo; este ejemplo no las suplanta.
