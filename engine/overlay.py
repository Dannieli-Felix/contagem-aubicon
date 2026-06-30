"""
Conferência visual: renderiza a página do PDF com as REGIÕES DETECTADAS
sobrepostas (contorno na cor do piso + rótulo com nome). Serve para a equipe
confirmar de relance se o sistema "enxergou" os pisos certos nos lugares certos.
"""
from __future__ import annotations
import io

import fitz
from PIL import Image, ImageDraw, ImageFont

from .legend import parse_legend
from .counter import _big_fill_colors, _match_swatches_to_regions
from .geometry import extract_regions, visible_region_geoms


def _font(size):
    for path in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/System/Library/Fonts/Helvetica.ttc",
                 "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _ideal_text_color(rgb):
    r, g, b = rgb
    return (15, 20, 30) if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else (255, 255, 255)


def render_overlay(path, dpi=170):
    """Retorna PNG (bytes) com as regiões detectadas sobrepostas, ou None se falhar."""
    doc = fitz.open(path)
    page = entries = None
    for i in range(doc.page_count):
        e, t = parse_legend(doc[i])
        if e and t:
            page, entries = doc[i], e
            break
    if page is None:
        doc.close()
        return None

    big = _big_fill_colors(page)
    rc = _match_swatches_to_regions(entries, big)
    regs = extract_regions(page, set(rc.values()))
    geoms = visible_region_geoms(regs)
    name_by_color = {rc[x.codigo]: x.nome for x in entries if x.codigo in rc}

    f = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(f, f))
    base = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(max(13, int(f * 9)))
    lw = max(3, int(f * 2.2))

    labels = []
    for col, g in geoms.items():
        rgb = tuple(int(c) for c in col)
        polys = g.geoms if g.geom_type.startswith("Multi") else [g]
        for poly in polys:
            if poly.is_empty:
                continue
            pts = [(x * f, y * f) for x, y in poly.exterior.coords]
            # contorno com halo branco + linha na cor do piso
            draw.line(pts + [pts[0]], fill=(255, 255, 255, 235), width=lw + 3)
            draw.line(pts + [pts[0]], fill=rgb + (255,), width=lw)
        # rótulo no centroide da maior parte
        biggest = max(polys, key=lambda p: p.area)
        c = biggest.representative_point()
        labels.append((c.x * f, c.y * f, name_by_color.get(col, ""), rgb))

    out = Image.alpha_composite(base, overlay)
    d2 = ImageDraw.Draw(out)
    for cx, cy, txt, rgb in labels:
        if not txt:
            continue
        tb = d2.textbbox((0, 0), txt, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        x, y = cx - tw / 2, cy - th / 2
        pad = max(4, int(f * 3))
        d2.rounded_rectangle([x - pad, y - pad, x + tw + pad, y + th + pad],
                             radius=pad, fill=rgb + (235,))
        d2.text((x, y - tb[1]), txt, fill=_ideal_text_color(rgb), font=font)

    buf = io.BytesIO()
    out.convert("RGB").save(buf, "PNG")
    doc.close()
    return buf.getvalue()
