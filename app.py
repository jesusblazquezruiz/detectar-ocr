import io
import os
import time
import fitz  # PyMuPDF
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Detector OCR por página", page_icon="🔎", layout="wide")

st.title("🔎 Detector de OCR por página (PyMuPDF)")
st.write(
    "Sube un PDF y detecta qué páginas tienen **texto extraíble** (texto nativo u OCR) "
    "y cuáles son **solo imagen**. "
    "Nota: este método **no distingue** entre texto nativo y texto OCR; solo comprueba si puede extraerse texto."
)

with st.sidebar:
    st.header("Ajustes")
    min_chars = st.slider(
        "Umbral mínimo de caracteres para considerar 'con texto'",
        min_value=0, max_value=400, value=5, step=1,
        help="Si el recuento de caracteres extraídos en la página es >= a este valor, se marcará como 'con texto'."
    )
    analizar_rango = st.checkbox("Analizar solo un rango de páginas")
    page_start, page_end = 1, 1
    if analizar_rango:
        page_start = st.number_input("Desde la página (1-index)", min_value=1, value=1, step=1)
        page_end = st.number_input("Hasta la página (1-index, inclusive)", min_value=1, value=1, step=1)

uploaded = st.file_uploader("📄 Sube tu PDF", type=["pdf"])

def analizar_pdf(pdf_bytes: bytes, min_chars: int, start_idx: int = None, end_idx: int = None):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    # Normalizar rango
    if start_idx is None or end_idx is None:
        start_idx = 0
        end_idx = total_pages - 1
    else:
        # Convertir 1-index a 0-index y acotar
        start_idx = max(0, min(total_pages - 1, start_idx - 1))
        end_idx = max(0, min(total_pages - 1, end_idx - 1))
        if end_idx < start_idx:
            start_idx, end_idx = end_idx, start_idx

    registros = []
    paginas_con = []
    paginas_sin = []

    progress = st.progress(0.0, text="Analizando páginas...")
    last_update = time.time()

    pages_to_process = list(range(start_idx, end_idx + 1))
    for idx, i in enumerate(pages_to_process, start=1):
        page = doc[i]

        # Extraer texto plano
        text = page.get_text().strip()
        char_count = len(text)
        word_count = len(text.split()) if text else 0

        tiene_texto = char_count >= min_chars
        if tiene_texto:
            paginas_con.append(i + 1)  # 1-index
        else:
            paginas_sin.append(i + 1)

        registros.append({
            "pagina": i + 1,
            "tiene_texto": tiene_texto,
            "caracteres": char_count,
            "palabras": word_count,
            "muestra_texto": (text[:200].replace("\n", " ") if text else "")
        })

        # Actualizar barra (con throttling suave para no saturar el frontend)
        now = time.time()
        if now - last_update > 0.05 or idx == len(pages_to_process):
            progress.progress(idx / len(pages_to_process), text=f"Analizando páginas... {idx}/{len(pages_to_process)}")
            last_update = now

    doc.close()

    df = pd.DataFrame(registros).astype({
        "pagina": int, "tiene_texto": bool, "caracteres": int, "palabras": int
    }).sort_values("pagina").reset_index(drop=True)

    resumen = {
        "total_paginas_analizadas": len(df),
        "paginas_con_texto": len(paginas_con),
        "paginas_sin_texto": len(paginas_sin),
        "lista_paginas_con_texto": paginas_con,
        "lista_paginas_sin_texto": paginas_sin
    }

    return df, resumen

if uploaded is not None:
    pdf_bytes = uploaded.read()
    st.info("Archivo cargado correctamente. Haz clic en **Analizar** cuando quieras.", icon="✅")

    if st.button("🚀 Analizar"):
        with st.spinner("Procesando..."):
            df, resumen = analizar_pdf(
                pdf_bytes,
                min_chars=min_chars,
                start_idx=(page_start if analizar_rango else None),
                end_idx=(page_end if analizar_rango else None)
            )

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📊 Resumen")
            st.write(f"**Páginas analizadas:** {resumen['total_paginas_analizadas']}")
            st.write(f"**Con texto (≥ {min_chars} caracteres):** {resumen['paginas_con_texto']}")
            st.write(f"**Sin texto:** {resumen['paginas_sin_texto']}")

            with st.expander("Ver lista de páginas con texto"):
                st.write(resumen["lista_paginas_con_texto"] if resumen["lista_paginas_con_texto"] else "—")
            with st.expander("Ver lista de páginas sin texto"):
                st.write(resumen["lista_paginas_sin_texto"] if resumen["lista_paginas_sin_texto"] else "—")

        with col2:
            st.subheader("⬇️ Exportar")
            csv_bytes = df.to_csv(index=False, encoding="utf-8").encode("utf-8")
            st.download_button(
                label="Descargar CSV (detalle por página)",
                data=csv_bytes,
                file_name="resultado_ocr_por_pagina.csv",
                mime="text/csv"
            )

        st.subheader("🔎 Detalle por página")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

else:
    st.info("Sube un PDF para comenzar.", icon="📥")

st.caption(
    "⚠️ Limitación: detectar 'texto extraíble' no distingue entre texto nativo y texto generado por OCR. "
    "Si necesitas distinguirlo con precisión, habría que combinar análisis visual y/o re-OCR de la imagen para comparar."
)
