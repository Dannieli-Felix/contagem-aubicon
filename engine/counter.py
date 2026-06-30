"""
Orquestrador: lê um PDF de paginação Aubicon e devolve o quantitativo
(quantidade de cada piso) reproduzindo a contagem manual.

Fluxo:
  1. Para cada página com legenda, lê a LEGENDA DE PISOS.
  2. Descobre as cores reais das regiões e casa com os swatches da legenda.
  3. Extrai a geometria exata de cada região (clip + Bézier + oclusão).
  4. Calibra a escala pela METRAGEM TOTAL.
  5. Aplica Método A (área -> arredonda pra cima) ou B (peças na grade + perda).
  6. Junta páginas distintas; ignora páginas duplicadas (mesma legenda).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math

import fitz

from .legend import parse_legend
from .geometry import extract_regions, visible_areas_by_color, visible_region_geoms
from .grid import count_pieces
from .drawn_grid import count_pieces_drawn

PERDA_PADRAO = 0.05  # 5%


@dataclass
class PisoResult:
    codigo: str
    nome: str
    produto: str
    metodo: str                 # "area" | "pecas"
    area_m2: float
    pecas_inteiras: int | None
    pecas_recortes: int | None
    metragem: int               # quantidade final a comprar (m² ou nº de placas)
    unidade: str                # "m²" | "placas"
    swatch_color: tuple | None = None


@dataclass
class ProjetoResult:
    arquivo: str
    obra: str
    pisos: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    @property
    def metragem_total(self):
        return sum(p.metragem for p in self.pisos)


def _big_fill_colors(page, min_area=1500):
    """Cores dos preenchimentos grandes (candidatos a região), com sua área total."""
    from collections import defaultdict
    areas = defaultdict(float)
    for d in page.get_drawings():
        f = d.get("fill")
        if f is None:
            continue
        r = d["rect"]
        a = (r.x1 - r.x0) * (r.y1 - r.y0)
        if a >= min_area:
            areas[tuple(int(round(c * 255)) for c in f)] += a
    return areas


def _match_swatches_to_regions(entries, big_colors, tol=60):
    """
    Para cada piso da legenda, acha a cor da REGIÃO correspondente ao swatch.
    Entre as cores dentro da tolerância, escolhe a de MAIOR área pintada —
    a região de piso é um preenchimento grande, evitando casar com cinzas/UI
    que por acaso fiquem perto no espaço de cor.
    """
    region_colors = {}
    used = set()
    for e in entries:
        if e.swatch_color is None:
            continue
        cands = [(col, area) for col, area in big_colors.items()
                 if sum((a - b) ** 2 for a, b in zip(col, e.swatch_color)) ** 0.5 <= tol]
        cands = [(c, a) for c, a in cands if c not in used] or cands
        if not cands:
            continue
        best = max(cands, key=lambda ca: ca[1])[0]  # maior área dentro da tolerância
        region_colors[e.codigo] = best
        used.add(best)
    return region_colors


def _legend_signature(entries, total):
    return (round(total or 0, 1), tuple(sorted((e.codigo, e.nome) for e in entries)))


def _round_perda(pieces, perda):
    """Metragem de placas = arredonda pra cima (nunca pedir a menos)."""
    return math.ceil(pieces * (1 + perda))


def analyze_page(page, perda=PERDA_PADRAO):
    entries, total_m2 = parse_legend(page)
    if not entries or not total_m2:
        return None

    big = _big_fill_colors(page)
    region_color = _match_swatches_to_regions(entries, big)
    floor_colors = set(region_color.values())
    if not floor_colors:
        return None

    regions = extract_regions(page, floor_colors)
    vis_area = visible_areas_by_color(regions)
    vis_geom = visible_region_geoms(regions)
    total_pt2 = sum(vis_area.values())
    if total_pt2 <= 0:
        return None

    # Escala (pt²/m²): calibra pela SOMA das áreas dos pisos na legenda — que são
    # confiáveis e batem com o gabarito. Antes usava o "METRAGEM TOTAL" único, que
    # em alguns PDFs é lido errado e jogava a escala (e as áreas) fora.
    pairs = [(vis_area[region_color[e.codigo]], e.area_m2)
             for e in entries
             if e.codigo in region_color and region_color[e.codigo] in vis_area and e.area_m2]
    if pairs and sum(a for _, a in pairs) > 0:
        scale_px2_per_m2 = sum(pt for pt, _ in pairs) / sum(a for _, a in pairs)
    else:
        scale_px2_per_m2 = total_pt2 / total_m2
    scale_pt_per_m = scale_px2_per_m2 ** 0.5

    # contagem de peças — agrupada por tamanho de placa (suporta placas retangulares)
    piece_entries = [e for e in entries if e.metodo == "pecas"]
    piece_counts = {}
    by_tile = {}
    for e in piece_entries:
        if e.codigo not in region_color or region_color[e.codigo] not in vis_geom:
            continue
        tile = e.tile_size_m or (1.0, 1.0)
        by_tile.setdefault(tile, {})[region_color[e.codigo]] = vis_geom[region_color[e.codigo]]
    for tile, geoms_pieces in by_tile.items():
        # Lê a GRADE REALMENTE DESENHADA (resolve junta amarrada e reaproveitamento
        # de sobra) — confiável em região de UM piso só. Multi-cor ou detecção
        # duvidosa caem para a grade geométrica.
        drawn = None
        if len(geoms_pieces) == 1:
            drawn = count_pieces_drawn(page, geoms_pieces, scale_pt_per_m, tile)
        if drawn:
            piece_counts.update(drawn)
        else:
            px = scale_pt_per_m * tile[0]
            py = scale_pt_per_m * tile[1]
            piece_counts.update(count_pieces(geoms_pieces, px, py))

    pisos = []
    avisos = []
    for e in entries:
        col = region_color.get(e.codigo)
        if col is None or col not in vis_area:
            avisos.append(f"Piso [{e.codigo}] {e.nome}: região não localizada no desenho.")
            continue
        # área da linha: usa a da legenda (exata, igual ao gabarito) quando houver
        area_m2 = e.area_m2 if e.area_m2 else vis_area[col] / scale_px2_per_m2
        if e.metodo == "area":
            metragem = math.ceil(area_m2 - 1e-6)
            pisos.append(PisoResult(e.codigo, e.nome, e.produto, "area", area_m2,
                                    None, None, metragem, "m²", col))
        else:
            pc = piece_counts.get(col, {"inteiras": 0, "recortes": 0})
            total_pc = pc["inteiras"] + pc["recortes"]
            metragem = _round_perda(total_pc, perda)
            pisos.append(PisoResult(e.codigo, e.nome, e.produto, "pecas", area_m2,
                                    pc["inteiras"], pc["recortes"], metragem, "placas", col))
    return entries, total_m2, pisos, avisos


def analyze_pdf(path, perda=PERDA_PADRAO):
    doc = fitz.open(path)
    obra = ""
    for ln in doc[0].get_text("text").split("\n"):
        if ln.strip().upper().startswith("PROJETO"):
            obra = ln.split(":", 1)[-1].strip()
            break

    seen_sigs = set()
    all_pisos = []
    avisos = []
    for i in range(doc.page_count):
        res = analyze_page(doc[i], perda)
        if res is None:
            continue
        entries, total_m2, pisos, page_avisos = res
        sig = _legend_signature(entries, total_m2)
        if sig in seen_sigs:
            continue   # página duplicada (mesma legenda) -> não recontar
        seen_sigs.add(sig)
        all_pisos.extend(pisos)
        avisos.extend(page_avisos)
    doc.close()

    import os
    return ProjetoResult(arquivo=os.path.basename(path), obra=obra,
                         pisos=all_pisos, avisos=avisos)


def diagnose(path):
    """Diagnóstico para entender por que um PDF não foi reconhecido (uso na interface)."""
    import shapely
    try:
        ver_mupdf = fitz.VersionBind
    except Exception:
        ver_mupdf = str(getattr(fitz, "version", "?"))
    info = {"pymupdf": ver_mupdf, "shapely": shapely.__version__, "paginas": []}
    try:
        doc = fitz.open(path)
    except Exception as e:
        info["erro_abrir"] = repr(e)
        return info
    info["num_paginas"] = doc.page_count
    for i in range(doc.page_count):
        page = doc[i]
        p = {"pagina": i}
        try:
            txt = page.get_text("text")
            p["tem_texto_LEGENDA"] = "LEGENDADEPISOS" in txt.upper().replace(" ", "").replace("\n", "")
            p["chars_texto"] = len(txt.strip())
            p["vetor_paths"] = len(page.get_drawings())
            try:
                ext = page.get_drawings(extended=True)
                p["paths_extended"] = len(ext)
                p["tem_clip"] = any(d.get("type") == "clip" for d in ext)
            except Exception as e:
                p["erro_extended"] = repr(e)
            entries, total = parse_legend(page)
            p["legenda_total_m2"] = total
            p["pisos_legenda"] = len(entries)
            p["nomes"] = [e.nome for e in entries][:8]
            p["metodos"] = [e.metodo for e in entries][:8]
            p["swatches"] = [e.swatch_color for e in entries][:8]
            big = _big_fill_colors(page)
            p["cores_grandes"] = len(big)
            rc = _match_swatches_to_regions(entries, big) if entries else {}
            p["regioes_casadas"] = len(rc)
            regs = extract_regions(page, set(rc.values())) if rc else []
            p["regioes_extraidas"] = len(regs)
        except Exception as e:
            p["erro"] = repr(e)
        info["paginas"].append(p)
    doc.close()
    return info
