"""
Método B — contagem peça por peça (pisos modulares de qualquer dimensão).

Genérico: funciona para qualquer tamanho de placa (quadrada ou retangular) e
qualquer layout. A grade é alinhada às BORDAS RETAS das regiões (que caem sobre
as juntas reais das placas); se não houver bordas retas suficientes, cai para
uma busca que minimiza recortes.

Por cor, conta:
  - PEÇAS INTEIRAS  = células ~100% dentro da região
  - PEÇAS C/ RECORTE = células parcialmente dentro (placa cortada = 1 placa)
"""
from __future__ import annotations
import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

WHOLE_MIN = 0.985   # cobertura >= isto -> peça inteira
# cobertura entre CUT_MIN e WHOLE_MIN -> recorte (placa cortada).
# Abaixo de CUT_MIN a região só "encosta" na célula: é sobra de uma placa
# vizinha (off-cut), não uma placa nova — alinhado a como o instalador conta.
CUT_MIN = 0.10


def _circ_phase(coords, pitch, weights=None):
    """Fase dominante (origem) das coordenadas em relação a um passo 'pitch'."""
    if len(coords) == 0:
        return None
    a = (np.array(coords) % pitch) / pitch * 2 * np.pi
    if weights is None:
        weights = np.ones(len(coords))
    w = np.array(weights, dtype=float)
    m = np.arctan2(np.sum(w * np.sin(a)), np.sum(w * np.cos(a)))
    return (m / (2 * np.pi) * pitch) % pitch


def _axis_edges(region_geoms):
    """Coordenadas (e comprimentos) das arestas verticais e horizontais das regiões."""
    vx, vw, hy, hw = [], [], [], []
    for g in region_geoms:
        geoms = g.geoms if g.geom_type.startswith("Multi") else [g]
        for poly in geoms:
            if poly.is_empty:
                continue
            rings = [poly.exterior] + list(poly.interiors)
            for ring in rings:
                xy = list(ring.coords)
                for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
                    if abs(x1 - x2) < 0.4 and abs(y1 - y2) > 2:   # vertical
                        vx.append(x1); vw.append(abs(y1 - y2))
                    elif abs(y1 - y2) < 0.4 and abs(x1 - x2) > 2:  # horizontal
                        hy.append(y1); hw.append(abs(x1 - x2))
    return vx, vw, hy, hw


def detect_grid_origin(region_geoms, pitch_x, pitch_y):
    """Origem (ox, oy) alinhando as arestas retas das regiões à grade. None se insuficiente."""
    vx, vw, hy, hw = _axis_edges(region_geoms)
    if sum(vw) < pitch_x or sum(hw) < pitch_y:
        return None
    ox = _circ_phase(vx, pitch_x, vw)
    oy = _circ_phase(hy, pitch_y, hw)
    if ox is None or oy is None:
        return None
    return ox, oy


def _count_at(region_geoms_by_color, union, bounds, px, py, ox, oy):
    minx, miny, maxx, maxy = bounds
    cell_area = px * py
    i0 = int(np.floor((minx - ox) / px)) - 1
    i1 = int(np.ceil((maxx - ox) / px)) + 1
    j0 = int(np.floor((miny - oy) / py)) - 1
    j1 = int(np.ceil((maxy - oy) / py)) + 1
    result = {c: {"inteiras": 0, "recortes": 0} for c in region_geoms_by_color}
    for j in range(j0, j1 + 1):
        cy0 = oy + j * py
        for i in range(i0, i1 + 1):
            cx0 = ox + i * px
            cell = box(cx0, cy0, cx0 + px, cy0 + py)
            if not cell.intersects(union):
                continue
            best_color, best_frac = None, 0.0
            for color, geom in region_geoms_by_color.items():
                frac = cell.intersection(geom).area / cell_area
                if frac > best_frac:
                    best_frac, best_color = frac, color
            if best_color is None or best_frac < CUT_MIN:
                continue
            key = "inteiras" if best_frac >= WHOLE_MIN else "recortes"
            result[best_color][key] += 1
    return result


def count_pieces(region_geoms_by_color, pitch_x, pitch_y=None, origin=None, search_steps=14):
    """
    region_geoms_by_color: {cor: geometria visível (shapely)}.
    pitch_x, pitch_y: lados da peça em pt (= escala_pt_por_m * lado_em_m).
    origin: (ox, oy) opcional; se None, detecta pelas bordas retas e, em último
            caso, busca a origem que minimiza recortes.
    Retorna {cor: {'inteiras': n, 'recortes': n}}.
    """
    if pitch_y is None:
        pitch_y = pitch_x
    all_geoms = list(region_geoms_by_color.values())
    union = unary_union(all_geoms)
    bounds = union.bounds

    if origin is None:
        origin = detect_grid_origin(all_geoms, pitch_x, pitch_y)

    if origin is not None:
        return _count_at(region_geoms_by_color, union, bounds, pitch_x, pitch_y, *origin)

    # fallback: busca a origem que minimiza recortes (regiões sem bordas retas)
    minx, miny = bounds[0], bounds[1]
    best = None
    for ox in np.linspace(minx, minx + pitch_x, search_steps, endpoint=False):
        for oy in np.linspace(miny, miny + pitch_y, search_steps, endpoint=False):
            res = _count_at(region_geoms_by_color, union, bounds, pitch_x, pitch_y, ox, oy)
            key = (sum(v["recortes"] for v in res.values()),
                   sum(v["inteiras"] + v["recortes"] for v in res.values()))
            if best is None or key < best[0]:
                best = (key, res)
    return best[1]
