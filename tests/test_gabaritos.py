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


def test_terrah_pecas_tolerancia():
    r = analyze_pdf(TERRAH)
    m = _by_name(r)
    # ESTRELADO e VERDE devem bater exato; CINZA pode variar ±1 (placa de fronteira)
    assert m["ESTRELADO CINZA"].metragem == 45
    assert m["COLORS BLEND VERDE FOLHA"].metragem == 9
    assert abs(m["COLORS BLEND CINZA GRANIZO"].metragem - 16) <= 1


def test_botanical_pecas_tolerancia():
    # IMPACT SOFT 50: dimensão "1,00m x 1,00m" -> deve ser PEÇAS (não área).
    m = _by_name(analyze_pdf(BOTANICAL))
    p = m["PIGMENTADO VERDE"]
    assert p.metodo == "pecas", f"método errado: {p.metodo} (esperado pecas)"
    assert abs(p.metragem - 31) <= 1, f"metragem {p.metragem} fora de 31±1"


def test_metodo_detectado():
    coree = _by_name(analyze_pdf(COREE))
    terrah = _by_name(analyze_pdf(TERRAH))
    botanical = _by_name(analyze_pdf(BOTANICAL))
    assert all(p.metodo == "area" for p in coree.values())
    assert all(p.metodo == "pecas" for p in terrah.values())
    assert all(p.metodo == "pecas" for p in botanical.values())


if __name__ == "__main__":
    ok = True
    for fn in [test_coree_area_exato, test_terrah_pecas_tolerancia,
               test_botanical_pecas_tolerancia, test_metodo_detectado]:
        try:
            fn()
            print(f"  ✔ {fn.__name__}")
        except AssertionError as e:
            ok = False
            print(f"  ✘ {fn.__name__}: {e}")
    print("\nTODOS OS TESTES PASSARAM ✅" if ok else "\nALGUM TESTE FALHOU ❌")
    sys.exit(0 if ok else 1)
