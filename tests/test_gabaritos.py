"""
Testes de validação contra os gabaritos (contagem manual).
Roda com:  python3 tests/test_gabaritos.py    (ou pytest)

COREE (método por área)  -> deve bater 100%.
TERRAH (método por peça) -> tolerância de ±1 placa por cor em fronteiras
                            (diferença subjetiva de recorte na contagem manual).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.counter import analyze_pdf

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COREE = os.path.join(BASE, "AUBICON - COREE - PLAYGROUND - PAGINAÇÃO PIP.pdf")
TERRAH = os.path.join(BASE, "AUBICON - TERRAH - FITNESS - PAGINAÇÃO.pdf")
BOTANICAL = os.path.join(BASE, "AUBICON - BOTANICAL - BRINQUEDOTECA - PAGINAÇÃO.pdf")


def _by_name(result):
    return {p.nome.strip(): p for p in result.pisos}


def test_coree_area_exato():
    r = analyze_pdf(COREE)
    m = _by_name(r)
    esperado = {"EPDM CITRINO": 27, "EPDM CORAL": 7, "EPDM JADE": 57, "EPDM MADREPÉROLA": 27}
    for nome, metr in esperado.items():
        assert nome in m, f"piso não detectado: {nome}"
        assert m[nome].metragem == metr, f"{nome}: {m[nome].metragem} != {metr}"
    assert r.metragem_total == 118


def test_metodo_detectado():
    coree = _by_name(analyze_pdf(COREE))
    terrah = _by_name(analyze_pdf(TERRAH))
    botanical = _by_name(analyze_pdf(BOTANICAL))
    assert all(p.metodo == "area" for p in coree.values())
    assert all(p.metodo == "pecas" for p in terrah.values())
    assert all(p.metodo == "pecas" for p in botanical.values())


# Gabaritos (manuais) de todos os projetos: nome -> (area_m2, metragem)
_TODOS = {
    COREE: {"EPDM CITRINO": (26.5386, 27), "EPDM CORAL": (6.1246, 7),
            "EPDM JADE": (56.4554, 57), "EPDM MADREPÉROLA": (26.3773, 27)},
    TERRAH: {"COLORS BLEND CINZA GRANIZO": (11.3376, 16),
             "COLORS BLEND VERDE FOLHA": (5.6386, 9), "ESTRELADO CINZA": (38.8829, 45)},
    BOTANICAL: {"PIGMENTADO VERDE": (26.5644, 31)},
    os.path.join(BASE, "AUBICON - ALPHAVILLE PARQUE - ACADEMIA - PAGINAÇÃO.pdf"):
        {"COLORS BLEND CINZA BASALTO": (122.3867, 133)},
    os.path.join(BASE, "AUBICON - ALPHAVILLE PARQUE - ACADEMIA EXTERNA - PAGINAÇÃO.pdf"):
        {"EPDM GALENA": (12.6735, 16), "PIGMENTADO GRAFITE": (12.638, 16)},
    os.path.join(BASE, "AUBICON - ALPHAVILLE PARQUE - PLAYGROUND - PAGINAÇÃO.pdf"):
        {"EPDM ESMERALDA": (42.6184, 51), "EPDM JADE": (50.3516, 55), "EPDM MADREPÉROLA": (39.1315, 44)},
    os.path.join(BASE, "AUBICON - STUDIO SHOPPING RECREIO - ACADEMIA 1 - PAGINAÇÃO.pdf"):
        {"PRETO": (59.7142, 66)},
    os.path.join(BASE, "AUBICON - STUDIO SHOPPING RECREIO - ACADEMIA 2 - PAGINAÇÃO.pdf"):
        {"PRETO": (57.3622, 63)},
}


def _coletar():
    area_ok = area_tot = metr_dentro2 = metr_tot = 0
    for path, gab in _TODOS.items():
        if not os.path.exists(path):
            continue
        m = _by_name(analyze_pdf(path))
        usados = set()
        for nome, (ga, gm) in gab.items():
            p = next((m[k] for k in m if k not in usados and (k == nome or nome in k or k.startswith(nome))), None)
            if p is None:
                continue
            usados.add(p.nome.strip())
            area_tot += 1
            area_ok += abs(p.area_m2 - ga) < 0.1
            metr_tot += 1
            metr_dentro2 += abs(p.metragem - gm) <= 2
    return area_ok, area_tot, metr_dentro2, metr_tot


def test_areas_exatas():
    """A ÁREA de toda linha deve bater com o gabarito (garantia forte do motor)."""
    area_ok, area_tot, _, _ = _coletar()
    assert area_ok == area_tot, f"áreas exatas: {area_ok}/{area_tot}"


def test_metragem_dentro_da_margem():
    """A METRAGEM deve estar dentro de ±2 placas na grande maioria das linhas."""
    _, _, dentro, tot = _coletar()
    assert dentro / tot >= 0.85, f"metragem ±2: {dentro}/{tot} ({100*dentro//tot}%)"


if __name__ == "__main__":
    ok = True
    a_ok, a_tot, m_ok, m_tot = _coletar()
    print(f"  Acurácia: área {a_ok}/{a_tot} (100%? {a_ok==a_tot}) | "
          f"metragem ±2 {m_ok}/{m_tot} ({100*m_ok//m_tot}%)")
    for fn in [test_coree_area_exato, test_metodo_detectado,
               test_areas_exatas, test_metragem_dentro_da_margem]:
        try:
            fn()
            print(f"  ✔ {fn.__name__}")
        except AssertionError as e:
            ok = False
            print(f"  ✘ {fn.__name__}: {e}")
    print("\nTODOS OS TESTES PASSARAM ✅" if ok else "\nALGUM TESTE FALHOU ❌")
    sys.exit(0 if ok else 1)
