"""Renderiza a página do PDF em imagem (para conferência visual na interface)."""
from __future__ import annotations
import io
import fitz


def render_page_png(path, page_index=0, dpi=140):
    doc = fitz.open(path)
    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    data = pix.tobytes("png")
    doc.close()
    return data


def first_legend_page(path):
    """Índice da primeira página que tem uma legenda (para mostrar no preview)."""
    from .legend import parse_legend
    doc = fitz.open(path)
    idx = 0
    for i in range(doc.page_count):
        entries, total = parse_legend(doc[i])
        if entries and total:
            idx = i
            break
    doc.close()
    return idx
