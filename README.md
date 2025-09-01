# 🔎 Detector de OCR por página (Streamlit + PyMuPDF)

Mini-app para analizar un PDF y marcar qué páginas tienen **texto extraíble** (texto nativo u OCR) y cuáles no.

## Cómo funciona
- Usa PyMuPDF para extraer texto por página.
- Si el número de caracteres extraídos ≥ umbral (configurable), se considera “con texto”.
- Exporta un CSV con el detalle por página.

## Requisitos
