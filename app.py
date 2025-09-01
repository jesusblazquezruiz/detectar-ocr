import sys, importlib
import streamlit as st

st.sidebar.write("Python:", sys.version)
for mod in ("fitz", "pymupdf", "pandas", "streamlit"):
    try:
        m = importlib.import_module(mod)
        st.sidebar.write(mod, getattr(m, "__version__", "sin versión"))
    except Exception as e:
        st.sidebar.write(mod, "❌ no disponible:", e)

import time
import fitz  # PyMuPDF
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Detector OCR por página", page_icon="🔎", layout="wide")

st.title("🔎 Detector de OCR por página (PyMuPDF)")
st.write(
    "Sube un PDF y detecta qué páginas tienen **texto extraíble** (texto nativo u OCR) y cuáles son **solo imagen**.\n\n"
    "ℹ️ Este método **no distingue** entre texto nativo y texto OCR; solo comprueba si se puede extraer texto."
)

with st.sidebar:
    st.header("Ajustes")
    min_chars = st.slider(
        "Umbral mínimo de caracteres para considerar 'con texto'",
        min_value=0, max_value=400, value=5, step=1,
        help="Si el recuento de caracteres extraídos en la página es ≥ a este valor, se marca como 'con texto'."
    )
    analizar_rango = st.checkbox("Analizar solo un rango de páginas")
    page_start = st.number_input("Desde la página (1-index)", min_value=1, value=1, step=1, disabled=not analizar_rango)
    page_end = st.number_input("Hasta la página (1-index, inclusive)", min_value=1, value=1, step=1, disabled=not analizar_rango)

uploaded = st.file_uploader("📄 Sube tu PDF", type=["pdf"])

def abrir_documento(pdf_bytes: bytes):
    """Abre un PDF desde bytes con control de errores y gestión de cifrado."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir el PDF. ¿Está dañado o no es un PDF válido?\nDetalle: {e}")

    if doc.is_encrypted:
        # Intentamos abrir sin contraseña (algunos permiten lectura)
        try:
            if not doc.authenticate(""):
                doc.close()
                raise RuntimeError("El PDF está cifrado y requiere contraseña. No se puede analizar.")
        except Exception:
            doc.close()
            raise RuntimeError("El PDF está cifrado y requiere contraseña. No se puede analizar.")
    return doc

def analizar_pdf(pdf_bytes: bytes, min_chars: int, start_1idx: int | None = None, end_1idx: int | None = None):
    doc = abrir_documento(pdf_bytes)
    total_pages = len(doc)

    # Normalizar rango (0-index)
    if start_1idx is None or end_1idx is None:
        start = 0
        end = total_pages - 1
    else:
        start = max(0, min(total_pages - 1, start_1idx - 1))
        end = max(0, min(total_pages - 1, end_1idx - 1))
        if end < start:
            start, end = end, start

    registros = []
    paginas_con, paginas_sin = [], []

    pages_to_process = list(range(start, end + 1))
    progress = st.progress(0.0, text="Analizando páginas...")
    last_update = time.time()

    for idx, i in enumerate(pages_to_process, start=1):
        page = doc[i]

        # `text` es suficiente para detectar si hay capa de texto/ocr
        try:
            text = page.get_text().strip()
        except Exception:
            text = ""  # si falla la extracción, tratamos como sin texto

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

        now = time.time()
        if now - last_update > 0.05 or idx == len(pages_to_process):
            try:
                progress.progress(idx / len(pages_to_process), text=f"Analizando páginas... {idx}/{len(pages_to_process)}")
            except Exception:
                pass
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
        "lista_paginas_sin_texto": paginas_sin,
    }
    return df, resumen

if uploaded is None:
    st.info("Sube un PDF para comenzar.", icon="📥")
else:
    # Lee bytes UNA sola vez y trabaja siempre con esos bytes
    try:
        pdf_bytes = uploaded.getvalue()
    except Exception:
        # Fallback por si getvalue no está disponible en algún entorno
        uploaded.seek(0)
        pdf_bytes = uploaded.read()

    st.success(f"Archivo cargado: **{uploaded.name}** ({len(pdf_bytes)/1024:.1f} KB)", icon="✅")

    if st.button("🚀 Analizar"):
        with st.spinner("Procesando..."):
            try:
                df, resumen = analizar_pdf(
                    pdf_bytes,
                    min_chars=min_chars,
                    start_1idx=(page_start if analizar_rango else None),
                    end_1idx=(page_end if analizar_rango else None)
                )
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.exception(e)
            else:
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
                st.dataframe(df, use_container_width=True, hide_index=True)

st.caption(
    "⚠️ Limitación: detectar 'texto extraíble' no distingue entre texto nativo y texto generado por OCR. "
    "Para distinguirlos con precisión habría que comparar contra un re-OCR u otras heurísticas."
)
