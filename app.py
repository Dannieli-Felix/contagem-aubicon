"""
Aubicon · Contagem de Piso
Anexe o PDF de paginação e receba a quantidade de cada piso.
Rodar:  streamlit run app.py
"""
import os
import tempfile

import streamlit as st

from engine.counter import analyze_pdf
from engine.preview import render_page_png, first_legend_page

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _logo_svg(dark=False):
    """Logo Aubicon embutido. Barra azul (claro) -> logo branco; barra verde (escuro) -> logo marinho."""
    nome = "logo-aubicon-marinho.svg" if dark else "logo-aubicon-branco.svg"
    cor = "#012B5E" if dark else "#fff"
    try:
        with open(os.path.join(_ASSETS, nome), encoding="utf-8") as f:
            svg = f.read()
        return svg.replace('width="2617"', 'width="124"').replace('height="688"', 'height="33"')
    except Exception:
        return f'<span style="color:{cor};font-weight:800;letter-spacing:.14em;">AUBICON</span>'

# ----------------------------------------------------------------------------
# Marca Aubicon · NAVY = azul-marinho, GREEN = verde de acento
NAVY, NAVY2, GREEN = "#012B5E", "#0A3D7A", "#3CA51B"
PERDA_PADRAO = 0.05  # margem de segurança (fixa, não editável pelo usuário)

# Tema CLARO (clean, padrão) e ESCURO — alternados pelo botão no topo
LIGHT = {
    "__BG__": "#EEF1F6", "__CARD__": "#FFFFFF", "__INK__": "#1B2533",
    "__MUTED__": "#6B7480", "__BORDER__": "#E6EBF2", "__ONBG__": "#1B2533",
    "__ONBG_MUTED__": "#5A6470", "__VAL__": NAVY, "__ACCENT__": NAVY,
    "__TBLHEAD__": "#F6F8FB", "__ROWHOVER__": "#FAFBFD", "__ROWBORDER__": "#F0F3F7",
    "__DASH__": "#C7D2E2", "__CHIPBD__": "rgba(0,0,0,.14)",
    "__PE_BG__": "#EAF5E4", "__PE_TX__": "#2E7D14", "__AR_BG__": "#E7EEF8", "__AR_TX__": NAVY2,
    "__NAVY__": NAVY, "__NAVY2__": NAVY2,
    # barra da marca: AZUL-MARINHO no tema claro
    "__BAR_BG__": "linear-gradient(100deg,#012B5E 0%,#0A3D7A 100%)",
    "__BAR_TXT__": "#CBD9EC", "__BAR_TAG__": "#A9C0DD", "__BAR_DIV__": "rgba(255,255,255,.22)",
    "__BAR_SHADOW__": "rgba(1,43,94,.22)",
    # acento da área de upload (botão + borda no hover): MARINHO no claro
    "__UPBTN__": NAVY, "__UPBTN_HOVER__": NAVY2, "__UPBORDER_HOVER__": NAVY, "__UPBTN_TX__": "#FFFFFF",
    # aba ativa (segmented control)
    "__TAB_ACTIVE_BG__": NAVY, "__TAB_ACTIVE_TX__": "#FFFFFF", "__TAB_TRACK__": "#FFFFFF",
}
DARK = {
    "__BG__": "#1B2330", "__CARD__": "#232E3D", "__INK__": "#EAF0F7",
    "__MUTED__": "#9DAABC", "__BORDER__": "rgba(255,255,255,.09)", "__ONBG__": "#EAF0F7",
    "__ONBG_MUTED__": "#A7B4C6", "__VAL__": "#FFFFFF", "__ACCENT__": "#9FD64A",
    "__TBLHEAD__": "#2A3647", "__ROWHOVER__": "#2A3647", "__ROWBORDER__": "rgba(255,255,255,.06)",
    "__DASH__": "rgba(255,255,255,.22)", "__CHIPBD__": "rgba(255,255,255,.28)",
    "__PE_BG__": "rgba(60,165,27,.20)", "__PE_TX__": "#7FD957",
    "__AR_BG__": "rgba(91,155,213,.20)", "__AR_TX__": "#8FC0F0",
    "__NAVY__": NAVY, "__NAVY2__": NAVY2,
    # barra da marca: VERDE Aubicon no tema escuro
    "__BAR_BG__": "linear-gradient(100deg,#8CA80A 0%,#98B60A 100%)",
    "__BAR_TXT__": "#1F3A00", "__BAR_TAG__": "#2C4A00", "__BAR_DIV__": "rgba(0,0,0,.20)",
    "__BAR_SHADOW__": "rgba(0,0,0,.30)",
    # acento da área de upload (botão + borda no hover): VERDE DA BARRA (#98B60A) no escuro
    "__UPBTN__": "#98B60A", "__UPBTN_HOVER__": "#8CA80A", "__UPBORDER_HOVER__": "#98B60A", "__UPBTN_TX__": "#16320A",
    # aba ativa (segmented control): verde da marca no escuro
    "__TAB_ACTIVE_BG__": "#98B60A", "__TAB_ACTIVE_TX__": "#16320A", "__TAB_TRACK__": "#2A3647",
}


def _style(css: str, pal: dict) -> str:
    for k, v in pal.items():
        css = css.replace(k, v)
    return css


_FAVICON = os.path.join(_ASSETS, "favicon-aubicon.png")
st.set_page_config(page_title="Aubicon · Contagem de Piso",
                   page_icon=_FAVICON if os.path.exists(_FAVICON) else "🟦",
                   layout="wide", initial_sidebar_state="collapsed")


def html(s: str):
    """Renderiza HTML sem que a indentação vire bloco de código no Streamlit."""
    st.markdown("\n".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


dark = st.session_state.get("dark", False)   # tema atual (o toggle abaixo controla a chave "dark")
PAL = DARK if dark else LIGHT


# ----------------------------------------------------------------------------
# Estilo (tema claro/escuro alternável) + ocultar elementos técnicos do Streamlit
html(_style("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ---- esconder a interface técnica do Streamlit ---- */
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton, [data-testid="stSidebarCollapsedControl"] { display:none !important; }
/* ---- esconder o selo/avatar do Streamlit Cloud (canto inferior direito) ---- */
[class*="viewerBadge"], [class*="_viewerBadge"], [class*="_profileContainer"],
[data-testid="stAppDeployButton"], [data-testid="manage-app-button"], .stAppDeployButton,
a[href*="streamlit.io/cloud"], a[href*="share.streamlit.io"], a[href*="streamlit.io"][class*="badge"] { display:none !important; visibility:hidden !important; }

/* ---- base ---- */
html, body, [class*="css"], .stApp { font-family:'Inter',-apple-system,sans-serif; }
.stApp { background:__BG__; }
.block-container { max-width:1160px; padding-top:1rem; padding-bottom:4.5rem; }
* { -webkit-font-smoothing:antialiased; }

/* ---- toggle de tema (switch nativo) à direita ---- */
div[data-testid="stToggle"] { justify-content:flex-end; }
div[data-testid="stToggle"] label { gap:9px !important; white-space:nowrap !important; }
div[data-testid="stToggle"] label p, div[data-testid="stToggle"] label span,
div[data-testid="stToggle"] label div[data-testid="stMarkdownContainer"] { color:__ONBG__ !important; font-weight:600; font-size:.86rem; white-space:nowrap !important; }

/* ---- texto de widgets nativos segue o tema (visível no escuro) ---- */
[data-testid="stFileUploaderFile"], [data-testid="stFileUploaderFile"] *,
[data-testid="stFileUploaderFileName"], [data-testid="stFileUploaderFileData"] * { color:__ONBG__ !important; }
[data-testid="stFileUploaderDeleteBtn"] svg { fill:__ONBG_MUTED__ !important; }
[data-testid="stSpinner"] p, .stSpinner > div { color:__ONBG__ !important; }

/* ---- cabeçalho da marca (cor da barra muda por tema) ---- */
.brandbar { display:flex; align-items:center; justify-content:space-between;
  background:__BAR_BG__; border-radius:16px;
  padding:18px 24px; box-shadow:0 8px 24px __BAR_SHADOW__; margin:6px 0 22px; transition:background .25s; }
.brand-left { display:flex; align-items:center; gap:15px; }
.brand-left svg { display:block; }
.brand-app { color:__BAR_TXT__; font-size:.92rem; font-weight:600; border-left:1px solid __BAR_DIV__; padding-left:15px; }
.brand-tag { color:__BAR_TAG__; font-size:.82rem; font-weight:600; }

/* ---- títulos ---- */
.h-obra { font-size:1.1rem; font-weight:800; color:__ONBG__; margin:6px 0 2px; }
.muted { color:__ONBG_MUTED__; font-size:.9rem; font-weight:500; }

/* ---- cartões de métrica ---- */
.mcard { background:__CARD__; border:1px solid __BORDER__; border-radius:14px;
  padding:17px 19px; box-shadow:0 4px 14px rgba(0,0,0,.06); }
.mcard .lbl { color:__MUTED__; font-size:.76rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; }
.mcard .val { color:__VAL__; font-size:1.95rem; font-weight:800; line-height:1.1; margin-top:5px; }
.mcard .val small { font-size:.95rem; font-weight:600; color:__MUTED__; }

/* ---- tabela de resultado ---- */
.tbl-wrap { background:__CARD__; border:1px solid __BORDER__; border-radius:16px;
  overflow:hidden; box-shadow:0 6px 18px rgba(0,0,0,.07); }
table.res { width:100%; border-collapse:collapse; font-size:.95rem; }
table.res thead th { background:__TBLHEAD__; color:__MUTED__; font-weight:700; font-size:.76rem;
  text-transform:uppercase; letter-spacing:.05em; text-align:left; padding:14px 18px; border-bottom:1px solid __BORDER__; }
table.res thead th.r, table.res td.r { text-align:right; }
table.res td { padding:16px 18px; border-bottom:1px solid __ROWBORDER__; color:__INK__; vertical-align:middle; }
table.res tbody tr:last-child td { border-bottom:none; }
table.res tbody tr:hover td { background:__ROWHOVER__; }
.pname { font-weight:600; color:__INK__; display:flex; align-items:center; gap:11px; }
.chip { width:16px; height:16px; border-radius:5px; border:1px solid __CHIPBD__; flex:0 0 auto; }
.badge { display:inline-block; padding:4px 12px; border-radius:999px; font-size:.78rem; font-weight:600; }
.badge.pe { background:__PE_BG__; color:__PE_TX__; }
.badge.ar { background:__AR_BG__; color:__AR_TX__; }
.qtd { font-weight:800; color:__ACCENT__; font-size:1.1rem; }
.qtd small { font-weight:600; color:__MUTED__; font-size:.8rem; }
.subnote { color:__MUTED__; font-size:.8rem; }
.introhint { text-align:center; color:__ONBG_MUTED__; margin-top:22px; font-size:.92rem; font-weight:500; }

/* ---- área de upload (texto interno escondido; legenda própria acima) ---- */
[data-testid="stFileUploaderDropzone"] { background:__CARD__; border:1.5px dashed __DASH__;
  border-radius:16px; padding:24px 32px; transition:.15s; justify-content:center; gap:14px; flex-wrap:wrap; }
[data-testid="stFileUploaderDropzone"]:hover { border-color:__UPBORDER_HOVER__; background:__ROWHOVER__; }
[data-testid="stFileUploaderDropzoneInstructions"] { display:none !important; }
/* SÓ o botão de procurar arquivo vira "Carregar PDF" (NÃO o X de remover) */
[data-testid="stFileUploaderDropzone"] button:not([data-testid="stFileUploaderDeleteBtn"]) {
  color:transparent !important; position:relative; background:__UPBTN__ !important;
  border:none !important; border-radius:10px !important; min-width:175px; height:46px; box-shadow:none !important; }
[data-testid="stFileUploaderDropzone"] button:not([data-testid="stFileUploaderDeleteBtn"]):hover { background:__UPBTN_HOVER__ !important; }
[data-testid="stFileUploaderDropzone"] button:not([data-testid="stFileUploaderDeleteBtn"])::after {
  content:"📄  Carregar PDF"; color:__UPBTN_TX__; font-weight:700; font-size:.98rem;
  position:absolute; inset:0; display:flex; align-items:center; justify-content:center; }
/* botão de remover (X): discreto, nunca verde, nunca relabel */
[data-testid="stFileUploaderDeleteBtn"], [data-testid="stFileUploaderDeleteBtn"] button {
  background:transparent !important; min-width:auto !important; height:auto !important; }
[data-testid="stFileUploaderDeleteBtn"] button::after { content:none !important; }
[data-testid="stFileUploaderDeleteBtn"] svg { fill:__ONBG_MUTED__ !important; }
.uphint { text-align:center; color:__ONBG__; font-weight:700; font-size:.98rem; margin:2px 0 10px; }
.uphint small { display:block; color:__ONBG_MUTED__; font-weight:500; font-size:.82rem; margin-top:3px; }
[data-testid="stFileUploaderFile"] { color:__ONBG__; background:transparent !important; }
[data-testid="stFileUploaderFile"] small { color:__ONBG_MUTED__; }
[data-testid="stFileUploaderFileName"] { color:__ONBG__ !important; }

/* ---- abas (estilo "segmented control") ---- */
.stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:none !important; background:__TAB_TRACK__;
  border:1px solid __BORDER__; border-radius:12px; padding:6px; display:inline-flex; box-shadow:0 2px 8px rgba(0,0,0,.05); }
.stTabs [data-baseweb="tab"] { font-weight:700; color:__ONBG_MUTED__; padding:9px 22px; border-radius:8px;
  transition:.15s; background:transparent; }
.stTabs [data-baseweb="tab"]:hover { color:__ONBG__; background:__ROWHOVER__; }
.stTabs [aria-selected="true"] { background:__TAB_ACTIVE_BG__ !important; color:__TAB_ACTIVE_TX__ !important; }
.stTabs [data-baseweb="tab"] p { font-size:.95rem !important; font-weight:700 !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top:18px; }

/* ---- botão de download ---- */
.stDownloadButton button { border:1px solid __BORDER__ !important; background:__CARD__ !important;
  color:__ACCENT__ !important; border-radius:10px !important; font-weight:700 !important; }
.stDownloadButton button:hover { border-color:__NAVY__ !important; background:__TBLHEAD__ !important; }

/* ---- avisos ---- */
[data-testid="stAlert"] { border-radius:12px; }

/* ---- imagem de conferência ---- */
[data-testid="stImage"] img { border-radius:12px; border:1px solid __BORDER__; box-shadow:0 8px 22px rgba(0,0,0,.16); background:#fff; }

/* ---- rodapé fixo ---- */
.appfooter { position:fixed; left:0; right:0; bottom:0; text-align:center; padding:9px 10px;
  font-size:.8rem; color:__ONBG_MUTED__; background:__BG__; border-top:1px solid __BORDER__; z-index:50; }
.appfooter a { color:__ACCENT__; font-weight:700; text-decoration:none; }
.appfooter a:hover { text-decoration:underline; }
</style>
""", PAL))

# ----------------------------------------------------------------------------
# Toggle de tema (switch nativo), alinhado à direita. A chave "dark" persiste
# o estado e o rerun do próprio widget já reaplica o tema — preserva o PDF.
_sp, _tg = st.columns([9, 2.4])
with _tg:
    st.toggle("🌙 Escuro", key="dark", help="Alternar tema claro/escuro")

# ---- Cabeçalho da marca ----
html(f"""
<div class="brandbar">
<div class="brand-left">
{_logo_svg(dark)}
<span class="brand-app">Contagem de Piso</span>
</div>
<span class="brand-tag">Soluções que transformam impacto em bem-estar</span>
</div>
""")

# ---- Rodapé fixo (crédito) ----
html('<div class="appfooter">desenvolvido por '
     '<a href="https://www.linkedin.com/in/dannieli-felix-vieira-40903a213/" target="_blank">'
     'Dannieli Felix</a></div>')


def chip(color):
    c = f"rgb({color[0]},{color[1]},{color[2]})" if color else "#CBD5E1"
    return f"<span class='chip' style='background:{c}'></span>"


# ----------------------------------------------------------------------------
# Upload
html('<div class="uphint">Arraste o PDF de paginação aqui ou clique no botão abaixo'
     '<small>Apenas arquivos PDF · até 200 MB</small></div>')
uploaded = st.file_uploader("PDF de paginação", type=["pdf"], label_visibility="collapsed")

if uploaded is None:
    html('<div class="introhint">Anexe o PDF de paginação do projeto. O sistema lê a legenda, '
         'mede as regiões e calcula automaticamente a quantidade de cada piso — com margem de segurança.</div>')
    st.stop()

# ----------------------------------------------------------------------------
# Processamento
with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
    tmp.write(uploaded.getvalue())
    pdf_path = tmp.name

try:
    with st.spinner("Analisando o projeto…"):
        result = analyze_pdf(pdf_path, perda=PERDA_PADRAO)

    if not result.pisos:
        st.error("Não foi possível identificar a legenda de pisos ou as regiões deste PDF. "
                 "Confirme que é um PDF de paginação vetorial com a tabela “Legenda de Pisos”.")
        with st.expander("🔧 Detalhes técnicos (para diagnóstico)"):
            from engine.counter import diagnose
            st.json(diagnose(pdf_path))
        st.stop()

    obra = result.obra or os.path.splitext(uploaded.name)[0]
    tot_m2 = sum(p.metragem for p in result.pisos if p.unidade == "m²")
    tot_pc = sum(p.metragem for p in result.pisos if p.unidade == "placas")

    # ---- cabeçalho da obra + métricas ----
    html(f'<div class="h-obra">Obra: {obra}</div>'
         f'<div class="muted">{len(result.pisos)} piso(s) identificado(s) no projeto</div>')
    st.write("")

    # cartões: mostra só os que fazem sentido pro projeto (sem caixa vazia "—")
    cards = [("Pisos no projeto", f'{len(result.pisos)}')]
    if tot_pc:
        cards.append(("Total de peças", f'{tot_pc} <small>placas</small>'))
    if tot_m2:
        cards.append(("Total em m²", f'{tot_m2} <small>m²</small>'))
    mcols = st.columns(len(cards))
    for col, (lbl, val) in zip(mcols, cards):
        with col:
            html(f'<div class="mcard"><div class="lbl">{lbl}</div><div class="val">{val}</div></div>')
    st.write("")

    tab_res, tab_conf = st.tabs(["📋  Resultado", "🔍  Conferência"])

    # ---- aba Resultado ----
    with tab_res:
        rows = ""
        for p in result.pisos:
            if p.metodo == "pecas":
                metodo = '<span class="badge pe">Peça por peça</span>'
                pecas = f'{(p.pecas_inteiras or 0)} inteiras&nbsp;·&nbsp;{(p.pecas_recortes or 0)} recortes'
            else:
                metodo = '<span class="badge ar">Por área</span>'
                pecas = '<span class="subnote">medido por m²</span>'
            qtd = f'{p.metragem} <small>{p.unidade}</small>'
            rows += (f'<tr><td><div class="pname">{chip(p.swatch_color)}{p.nome}</div></td>'
                     f'<td>{metodo}</td>'
                     f'<td class="r">{p.area_m2:.2f} m²</td>'
                     f'<td>{pecas}</td>'
                     f'<td class="r"><span class="qtd">{qtd}</span></td></tr>')
        html(f"""
        <div class="tbl-wrap">
        <table class="res">
        <thead><tr>
        <th>Piso</th><th>Método de cálculo</th><th class="r">Área medida</th>
        <th>Detalhe</th><th class="r">Total de peças</th>
        </tr></thead>
        <tbody>{rows}</tbody>
        </table>
        </div>
        """)

        if result.avisos:
            st.write("")
            for a in result.avisos:
                st.warning(a)

        st.write("")
        csv = "piso,produto,metodo,area_m2,pecas_inteiras,pecas_recortes,total,unidade\n"
        for p in result.pisos:
            csv += (f'"{p.nome}","{p.produto}",{p.metodo},{p.area_m2:.3f},'
                    f'{p.pecas_inteiras if p.pecas_inteiras is not None else ""},'
                    f'{p.pecas_recortes if p.pecas_recortes is not None else ""},'
                    f'{p.metragem},{p.unidade}\n')
        st.download_button("⬇  Exportar planilha (CSV)", csv,
                           file_name=f"quantitativo_{os.path.splitext(uploaded.name)[0]}.csv",
                           mime="text/csv")

    # ---- aba Conferência (PDF amplo, horizontal) ----
    with tab_conf:
        html('<div class="muted" style="margin-bottom:10px;">'
             'Confira se as cores e regiões detectadas correspondem ao desenho do projeto.</div>')
        try:
            idx = first_legend_page(pdf_path)
            st.image(render_page_png(pdf_path, idx, dpi=190), use_container_width=True)
        except Exception:
            st.info("Pré-visualização indisponível para este arquivo.")
finally:
    try:
        os.unlink(pdf_path)
    except OSError:
        pass
