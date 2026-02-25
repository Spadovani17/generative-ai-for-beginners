# SPIJ Norma Tracker (prototipo)

Aplicación para PC (ejecutable local con navegador) que permite:

- Registrar versiones históricas de una norma desde su URL.
- Detectar si la norma cambió respecto de la captura anterior.
- Mostrar diferencias resaltadas entre dos versiones.
- Revisar evolución de cambios en el tiempo.

> Este prototipo está pensado como base técnica. Si la web objetivo aplica restricciones de acceso o términos de uso específicos, debes respetarlos.

## Arquitectura rápida

1. **Ingesta**: descarga HTML de una URL de norma.
2. **Normalización**: limpia elementos no textuales (`script`, `style`, etc.) y compacta espacios.
3. **Versionado**: guarda cada estado en SQLite con hash SHA-256.
4. **Comparación**:
   - Resumen por líneas agregadas/eliminadas.
   - Vista detallada tipo *side-by-side* con `difflib.HtmlDiff`.

## Requisitos

- Python 3.10+
- Dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

Abre la URL local que te muestra Streamlit (normalmente `http://localhost:8501`).

## Flujo de uso

1. Define un **ID interno** (por ejemplo: `LEY-26842`).
2. Ingresa la **URL** de la norma en SPIJ.
3. Presiona **Capturar versión actual**.
4. Repite periódicamente (manual o con automatización externa).
5. En el comparador, elige versión base y nueva para ver cambios resaltados.

## Siguiente evolución recomendada

- Programar capturas automáticas (scheduler diario).
- Parseo estructurado por artículos/incisos (no solo texto plano).
- Alertas por correo/Teams cuando cambie una norma crítica.
- Exportar reporte PDF con historial de cambios.
- Generar ejecutable de escritorio con `pyinstaller`.

## Nota legal

Antes de automatizar consultas al portal, verifica:

- términos de uso,
- políticas de robots/rate limit,
- y permisos aplicables.
