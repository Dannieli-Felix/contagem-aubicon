"""
Contagem peça-por-peça lendo a GRADE REALMENTE DESENHADA no PDF.

Detecta as linhas das fileiras e as juntas de cada fileira a partir da imagem
renderizada — então funciona com paginação alinhada OU desencontrada (junta
amarrada), porque lê o que está desenhado de verdade.

- PEÇAS INTEIRAS: células cheias 100% cobertas pela região.
- PEÇAS COM RECORTES: células de borda. A equipe Aubicon reaproveita a sobra
  (1 placa cortada cobre 2 recortes complementares), então emparelhamos as
  frações de borda que somam <= 1 numa placa só.
"""
from __future__ import annotations
import numpy as np
import fitz
from shapely.geometry import box
from shapely.ops import unary_union

WHOLE_MIN = 0.985   # cobertura >= isto -> peça inteira
CUT_MIN = 0.06      # cobertura entre CUT_MIN e WHOLE_MIN -> recorte


def _lines(prof, pitch, rel=0.20, sep=0.45):
    """Posições (px) das linhas claras (juntas) num perfil de brilho, espaçadas ~pitch."""
    if len(prof) < 3 or prof.max() <= prof.min():
        return []
    thr = prof.mean() + (prof.max() - prof.mean()) * rel
    cand = [i for i in range(1, len(prof) - 1)
            if prof[i] > thr and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]]
    out = []
    for c in cand:
        if not out or c - out[-1] > pitch * sep:
            out.append(c)
        elif prof[c] > prof[out[-1]]:
            out[-1] = c
    return out


def _bounds(positions, lo, hi, min_gap):
    b = sorted(set([lo] + list(positions) + [hi]))
    keep = [b[0]]
    for x in b[1:]:
        if x - keep[-1] > min_gap:
            keep.append(x)
    return keep


def pair_recortes(fracs):
    """Placas de recorte com reaproveitamento de sobra: 1 placa = 2 recortes que somam <= 1."""
    fr = sorted(fracs, reverse=True)
    used = [False] * len(fr)
    placas = 0
    for i in range(len(fr)):
        if used[i]:
            continue
        used[i] = True
        placas += 1
        for j in range(len(fr) - 1, i, -1):       # tenta casar com a maior sobra que ainda cabe
            if not used[j] and fr[i] + fr[j] <= 1.0:
                used[j] = True
                break
    return placas


def count_pieces_multicolor(geoms_by_color, pitch_x, pitch_y=None, search_steps=10):
    """
    Contagem peça-por-peça para desenho MULTI-COR (vários pisos no mesmo desenho).

    Modelo físico: cada cor conta TODA célula que ela toca (uma placa cortada
    pode pertencer a 2 cores numa fronteira). Os recortes são então emparelhados
    (1 placa cobre 2 recortes complementares) — o reaproveitamento de sobra que a
    equipe Aubicon usa. A grade é alinhada minimizando o total de recortes.
    """
    import numpy as np
    if pitch_y is None:
        pitch_y = pitch_x
    geoms = geoms_by_color
    union = unary_union(list(geoms.values()))
    minx, miny, maxx, maxy = union.bounds
    ca = pitch_x * pitch_y

    def at(ox, oy):
        res = {c: {"i": 0, "fr": []} for c in geoms}
        i0 = int(np.floor((minx - ox) / pitch_x)) - 1
        i1 = int(np.ceil((maxx - ox) / pitch_x)) + 1
        j0 = int(np.floor((miny - oy) / pitch_y)) - 1
        j1 = int(np.ceil((maxy - oy) / pitch_y)) + 1
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                cell = box(ox + i * pitch_x, oy + j * pitch_y,
                           ox + (i + 1) * pitch_x, oy + (j + 1) * pitch_y)
                if not cell.intersects(union):
                    continue
                for c, g in geoms.items():
                    f = cell.intersection(g).area / ca
                    if f < CUT_MIN:
                        continue
                    if f >= WHOLE_MIN:
                        res[c]["i"] += 1
                    else:
                        res[c]["fr"].append(min(f, 0.999))
        return res

    best = None
    for ox in np.linspace(minx, minx + pitch_x, search_steps, endpoint=False):
        for oy in np.linspace(miny, miny + pitch_y, search_steps, endpoint=False):
            r = at(ox, oy)
            cut = sum(len(v["fr"]) for v in r.values())
            if best is None or cut < best[0]:
                best = (cut, r)
    return {c: {"inteiras": v["i"], "recortes": pair_recortes(v["fr"])}
            for c, v in best[1].items()}


def count_pieces_drawn(page, region_geoms_by_color, scale_pt_per_m,
                       tile_m=(1.0, 1.0), dpi=300):
    """
    Conta placas lendo a grade desenhada. Retorna {cor: {'inteiras','recortes'}}
    ou None se não der pra detectar a grade com segurança.
    """
    geoms = region_geoms_by_color
    if not geoms:
        return None
    union = unary_union(list(geoms.values()))
    minx, miny, maxx, maxy = union.bounds
    f = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(f, f))
    arr = (np.frombuffer(pix.samples, np.uint8)
           .reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(float).mean(axis=2))
    px = scale_pt_per_m * tile_m[0]      # passo horizontal (px de imagem? não: pt) -> *f abaixo
    py = scale_pt_per_m * tile_m[1]
    pitch_px = px * f
    pitch_py = py * f
    x0, y0, x1, y1 = int(minx * f), int(miny * f), int(maxx * f), int(maxy * f)
    if x1 - x0 < 5 or y1 - y0 < 5 or pitch_px < 4 or pitch_py < 4:
        return None
    sub = arr[y0:y1, x0:x1]
    H, W = sub.shape

    rows = _lines(sub.mean(axis=1), pitch_py)
    yb = _bounds(rows, 0, H - 1, pitch_py * 0.18)
    if len(yb) < 2:
        return None

    pa = (scale_pt_per_m ** 2) * tile_m[0] * tile_m[1]    # área de 1 placa em pt²
    res = {c: {"inteiras": 0, "recortes": 0} for c in geoms}
    fracs = {c: [] for c in geoms}

    for r in range(len(yb) - 1):
        ry0, ry1 = yb[r], yb[r + 1]
        strip = sub[ry0:ry1, :]
        joints = _lines(strip.mean(axis=0), pitch_px)
        xb = _bounds(joints, 0, W - 1, pitch_px * 0.18)
        for c in range(len(xb) - 1):
            cx0, cx1 = xb[c], xb[c + 1]
            cell = box(minx + cx0 / f, miny + ry0 / f, minx + cx1 / f, miny + ry1 / f)
            ca = cell.area
            if ca <= 0:
                continue
            best, best_inter = None, 0.0
            for col, g in geoms.items():
                it = cell.intersection(g).area
                if it > best_inter:
                    best_inter, best = it, col
            if best is None:
                continue
            frac = best_inter / pa            # fração de placa que a região ocupa nessa célula
            if frac < 0.06:
                continue
            cov = best_inter / ca             # quanto da célula está coberto
            full = (cx1 - cx0) > pitch_px * 0.85 and (ry1 - ry0) > pitch_py * 0.85
            if full and cov >= 0.985:
                res[best]["inteiras"] += 1
            else:
                fracs[best].append(min(frac, 0.999))

    # checagem de sanidade: nº de placas detectadas tem que bater com a área.
    # Se a detecção da grade falhou (multi-cor confuso, região pequena), rejeita.
    detected = sum(res[c]["inteiras"] for c in geoms) + sum(len(fracs[c]) for c in geoms)
    expected = union.area / pa
    if detected == 0 or detected < 0.75 * expected:
        return None
    for col in geoms:
        res[col]["recortes"] = pair_recortes(fracs[col])
    return res
