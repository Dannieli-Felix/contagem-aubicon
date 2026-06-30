"""
Parser da tabela "LEGENDA DE PISOS" do PDF de paginação Aubicon.

Lê, para cada piso: código, acabamento (nome do acabamento/cor), produto,
dimensão da peça e área. Detecta o swatch de cor de cada linha para casar
com as regiões desenhadas. Também lê a METRAGEM TOTAL (para calibrar a escala).
"""
from __future__ import annotations
from dataclasses import dataclass
import re

HEADER_WORDS = {"CÓDIGO", "ACABAMENTOS", "PRODUTO", "DIMENSÃO", "ÁREA"}
AREA_RE = re.compile(r"([\d.]+,\d+)\s*m", re.IGNORECASE)
# dimensão: aceita "1,00 x 1,00m", "1,00m x 1,00m", "50cm x 50cm", "50 x 50cm" etc.
DIM_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(m|cm|mm)?\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(m|cm|mm)?",
    re.IGNORECASE)
CODE_RE = re.compile(r"^\d{2}$")
_UNIT = {"m": 1.0, "cm": 0.01, "mm": 0.001}


def parse_dim(text):
    """Extrai (largura, altura) da peça em METROS, ou None se não houver dimensão."""
    if not text:
        return None
    m = DIM_RE.search(text.replace(" ", ""))
    if not m:
        return None
    n1, u1, n2, u2 = m.group(1), m.group(2), m.group(3), m.group(4)
    unit = (u1 or u2 or "m").lower()
    f = _UNIT.get(unit, 1.0)
    return (_num(n1) * f, _num(n2) * f)


def despace(s: str) -> str:
    """Colapsa texto CAD espaçado: 'C I N Z A' -> 'CINZA', preserva separação de palavras."""
    s = s.replace("\n", " ")
    s = re.sub(r"\s{2,}", "|", s)   # separador de palavra = 2+ espaços
    s = s.replace(" ", "")           # remove espaços simples (entre glifos)
    s = s.replace("|", " ")          # restaura separadores
    return s.strip()


def _num(br: str) -> float:
    return float(br.replace(".", "").replace(",", "."))


@dataclass
class LegendEntry:
    codigo: str
    acabamento: str          # ex.: "ESTRELADO CINZA"
    produto: str             # ex.: "PESO LIVRE EVOLUTION 15MM"
    dimensao_txt: str        # ex.: "1,00 x 1,00m" ou "-"
    area_m2: float | None
    swatch_color: tuple | None = None   # (r,g,b) 0-255
    tile_size_m: tuple | None = None     # (larg, alt) em m, ou None se for por área

    @property
    def metodo(self) -> str:
        return "pecas" if self.tile_size_m else "area"

    @property
    def nome(self) -> str:
        """Nome do piso para o quantitativo (o acabamento, ex.: 'ESTRELADO CINZA')."""
        return self.acabamento.strip() or self.produto.strip() or self.codigo


def _spans(page):
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                t = despace(sp["text"])
                if not t:
                    continue
                x0, y0, x1, y1 = sp["bbox"]
                out.append({"t": t, "x": x0, "xc": (x0 + x1) / 2, "y": (y0 + y1) / 2})
    return out


def _small_color_fills(page, min_a=80, max_a=900):
    fills = []
    for d in page.get_drawings():
        f = d.get("fill")
        if f is None:
            continue
        r = d["rect"]
        a = (r.x1 - r.x0) * (r.y1 - r.y0)
        if min_a < a < max_a:
            fills.append({"color": tuple(int(round(c * 255)) for c in f),
                          "xc": (r.x0 + r.x1) / 2, "yc": (r.y0 + r.y1) / 2})
    return fills


def parse_total_m2(page):
    for sp in _spans(page):
        if "METRAGEMTOTAL" in sp["t"].replace(" ", "").upper():
            m = AREA_RE.search(sp["t"])
            if m:
                return _num(m.group(1))
    return None


def parse_legend(page, region_colors=None):
    """
    Retorna (entries, total_m2).
    Se region_colors for dado, casa o swatch de cada linha à cor de região mais próxima.
    """
    spans = _spans(page)
    total_m2 = parse_total_m2(page)

    # 1) localizar blocos de cabeçalho (pode haver 2 colunas) -> posições das colunas
    headers = [s for s in spans if s["t"].upper() in HEADER_WORDS]
    code_headers = sorted([s for s in headers if s["t"].upper() == "CÓDIGO"], key=lambda s: s["xc"])
    if not code_headers:
        return [], total_m2
    blocks = []
    for bi, ch in enumerate(code_headers):
        # limite direito do bloco = início do próximo bloco (evita vazar p/ a coluna seguinte)
        right = code_headers[bi + 1]["xc"] - 10 if bi + 1 < len(code_headers) else ch["xc"] + 175
        cols = {}
        for h in headers:
            if abs(h["y"] - ch["y"]) < 6 and ch["xc"] - 5 <= h["xc"] < right:
                cols[h["t"].upper()] = h["xc"]
        blocks.append({"y": ch["y"], "cols": cols, "x0": ch["xc"] - 8, "x1": right})

    # 2) achar códigos (NN) abaixo do cabeçalho, dentro de cada bloco
    entries = []
    fills = _small_color_fills(page)
    for blk in blocks:
        cols = blk["cols"]
        cod_x = cols.get("CÓDIGO", blk["x0"] + 8)
        # fronteiras de coluna = pontos médios entre centros de colunas vizinhas
        ordered_cols = sorted(cols.items(), key=lambda kv: kv[1])

        def nearest_col(xc):
            return min(ordered_cols, key=lambda kv: abs(kv[1] - xc))[0]

        codes = [s for s in spans if CODE_RE.match(s["t"]) and s["y"] > blk["y"] + 3
                 and abs(s["xc"] - cod_x) < 16 and s["y"] < blk["y"] + 80]
        codes.sort(key=lambda s: s["y"])
        for cs in codes:
            yb = cs["y"]
            row = [s for s in spans if abs(s["y"] - yb) <= 9
                   and blk["x0"] <= s["xc"] <= blk["x1"] and s is not cs]
            bycol = {}
            for s in row:
                col = nearest_col(s["xc"])
                bycol.setdefault(col, []).append(s)

            def col_text(name):
                parts = sorted(bycol.get(name, []), key=lambda s: (s["y"], s["x"]))
                return " ".join(p["t"] for p in parts).strip()

            acab = col_text("ACABAMENTOS")
            prod = col_text("PRODUTO")
            dim = col_text("DIMENSÃO")
            area_txt = col_text("ÁREA")

            am = AREA_RE.search(area_txt)
            area_m2 = _num(am.group(1)) if am else None
            tile = parse_dim(dim)

            # swatch: fill colorido pequeno mais próximo da posição (acabamento_x, código_y)
            sx = cols.get("ACABAMENTOS", cod_x + 20)
            swatch = None
            best = 1e9
            for fl in fills:
                if abs(fl["yc"] - yb) <= 14 and abs(fl["xc"] - sx) <= 40:
                    d = abs(fl["yc"] - yb) + abs(fl["xc"] - sx)
                    if d < best:
                        best = d
                        swatch = fl["color"]

            entries.append(LegendEntry(
                codigo=cs["t"], acabamento=acab.strip(), produto=prod.strip(),
                dimensao_txt=(dim.strip() or "-"), area_m2=area_m2,
                swatch_color=swatch, tile_size_m=tile))

    # 3) opcional: casar swatch -> cor de região mais próxima (corrige variação de tom)
    if region_colors:
        rc = list(region_colors)
        for e in entries:
            if e.swatch_color is None:
                continue
            best = min(rc, key=lambda c: sum((a - b) ** 2 for a, b in zip(c, e.swatch_color)))
            if sum((a - b) ** 2 for a, b in zip(best, e.swatch_color)) < 60 ** 2:
                e.swatch_color = best
    entries.sort(key=lambda e: e.codigo)
    return entries, total_m2
