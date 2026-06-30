"""
Extração de geometria vetorial de PDFs de paginação Aubicon.

As regiões de piso são desenhadas como preenchimentos (fills) recortados por
*clip paths* (a fronteira real da região). Este módulo reconstrói o polígono
exato de cada região, lidando com:
  - múltiplos sub-caminhos (subpaths)
  - curvas Bézier (bordas orgânicas / arredondadas) -> flatten
  - regra even-odd (furos / anéis)
  - oclusão por pintura (regiões aninhadas: a de cima "esconde" a de baixo)
"""
from __future__ import annotations
from dataclasses import dataclass, field

import fitz  # PyMuPDF
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely import make_valid

BEZIER_STEPS = 18  # nº de segmentos por curva Bézier ao achatar


def _bezier_points(p0, p1, p2, p3, steps=BEZIER_STEPS):
    """Amostra uma curva Bézier cúbica (De Casteljau)."""
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = (mt**3) * p0[0] + 3 * (mt**2) * t * p1[0] + 3 * mt * (t**2) * p2[0] + (t**3) * p3[0]
        y = (mt**3) * p0[1] + 3 * (mt**2) * t * p1[1] + 3 * mt * (t**2) * p2[1] + (t**3) * p3[1]
        pts.append((x, y))
    return pts


def _rings_from_items(items):
    """Converte os 'items' de um drawing/clip do PyMuPDF em anéis (listas de pontos)."""
    rings = []
    cur = []
    last = None

    def flush():
        nonlocal cur
        if len(cur) >= 3:
            rings.append(cur)
        cur = []

    for it in items:
        op = it[0]
        if op == "re":
            flush()
            r = it[1]
            rings.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
            last = None
        elif op == "qu":
            flush()
            q = it[1]
            rings.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)])
            last = None
        elif op == "l":
            p1 = (it[1].x, it[1].y)
            p2 = (it[2].x, it[2].y)
            if last is None or (abs(p1[0] - last[0]) > 0.05 or abs(p1[1] - last[1]) > 0.05):
                flush()
                cur = [p1, p2]
            else:
                cur.append(p2)
            last = p2
        elif op == "c":
            # Bézier cúbica: it[1]=start, it[2]=ctrl1, it[3]=ctrl2, it[4]=end
            p0 = (it[1].x, it[1].y)
            c1 = (it[2].x, it[2].y)
            c2 = (it[3].x, it[3].y)
            p3 = (it[4].x, it[4].y)
            if last is None or (abs(p0[0] - last[0]) > 0.05 or abs(p0[1] - last[1]) > 0.05):
                flush()
                cur = [p0]
            cur.extend(_bezier_points(p0, c1, c2, p3))
            last = p3
    flush()
    return rings


def polygon_from_items(items, even_odd=False):
    """Constrói um (Multi)Polygon a partir dos items, aplicando furos (even-odd)."""
    rings = _rings_from_items(items)
    polys = []
    for r in rings:
        try:
            p = Polygon(r)
            if not p.is_valid:
                p = make_valid(p)
            if not p.is_empty and p.area > 0:
                polys.append(p)
        except Exception:
            continue
    if not polys:
        return None
    geom = polys[0]
    for p in polys[1:]:
        # even-odd cria furos (XOR); non-zero une.
        geom = geom.symmetric_difference(p) if even_odd else unary_union([geom, p])
    if geom.is_empty:
        return None
    return geom


@dataclass
class Region:
    color: tuple          # (r, g, b) 0-255
    polygon: object       # shapely geometry (coordenadas em pt do PDF)
    fill_rect: tuple      # bbox do fill (x0, y0, x1, y1)

    @property
    def area_pt2(self):
        return self.polygon.area


def _bounds_score(b, r):
    return abs(b[0] - r.x0) + abs(b[1] - r.y0) + abs(b[2] - r.x1) + abs(b[3] - r.y1)


def extract_regions(page, floor_colors, min_area_pt2=1500, match_tol=6.0):
    """
    Extrai as regiões de piso de uma página.

    floor_colors: conjunto de cores (r,g,b 0-255) que são pisos (vindas da legenda).
    Para cada fill com cor de piso, encontra o clip path (fronteira) de bbox correspondente.
    Retorna lista de Region (ainda SEM oclusão aplicada).
    """
    dr = page.get_drawings(extended=True)

    # 1) coletar todos os clips com geometria
    clips = []
    for d in dr:
        if d.get("type") != "clip":
            continue
        g = polygon_from_items(d.get("items", []), d.get("even_odd", False))
        if g is None or g.is_empty:
            continue
        if g.area < min_area_pt2:
            continue
        clips.append(g)

    # 2) coletar fills com cor de piso
    fills = []
    for d in dr:
        if d.get("type") != "f":
            continue
        f = d.get("fill")
        if f is None:
            continue
        color = tuple(int(round(c * 255)) for c in f)
        if color not in floor_colors:
            continue
        r = d["rect"]
        if (r.x1 - r.x0) * (r.y1 - r.y0) < min_area_pt2:
            continue  # ignora swatches pequenos da legenda
        fills.append((color, r))

    # 3) parear fill -> clip mais justo (menor score de bbox)
    regions = []
    for color, r in fills:
        best = None
        best_score = 1e9
        for g in clips:
            s = _bounds_score(g.bounds, r)
            if s < best_score:
                best_score = s
                best = g
        if best is not None and best_score < match_tol:
            regions.append(Region(color=color, polygon=best, fill_rect=(r.x0, r.y0, r.x1, r.y1)))
    return regions


def visible_areas_by_color(regions):
    """
    Aplica oclusão por pintura: regiões menores ficam por cima.
    visível(i) = polígono(i) - união(regiões menores).
    Retorna {cor: area_visivel_pt2}.
    """
    ordered = sorted(regions, key=lambda x: x.polygon.area)  # menor primeiro = topo
    out = {}
    for i, reg in enumerate(ordered):
        smaller = [ordered[j].polygon for j in range(i)]
        vis = reg.polygon
        if smaller:
            vis = reg.polygon.difference(unary_union(smaller))
        if not vis.is_empty:
            out[reg.color] = out.get(reg.color, 0.0) + vis.area
    return out


def visible_region_geoms(regions):
    """Como visible_areas_by_color, mas devolve a GEOMETRIA visível por cor (para a grade)."""
    ordered = sorted(regions, key=lambda x: x.polygon.area)
    out = {}
    for i, reg in enumerate(ordered):
        smaller = [ordered[j].polygon for j in range(i)]
        vis = reg.polygon
        if smaller:
            vis = reg.polygon.difference(unary_union(smaller))
        if vis.is_empty:
            continue
        if reg.color in out:
            out[reg.color] = unary_union([out[reg.color], vis])
        else:
            out[reg.color] = vis
    return out
