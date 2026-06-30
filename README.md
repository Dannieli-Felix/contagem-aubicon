# 🧱 Contagem de Piso — Aubicon

App web que lê o **PDF de paginação** de um projeto e devolve a **quantidade de cada piso**
necessária para a instalação, reproduzindo a contagem manual — com margem de segurança
(sempre arredondando para cima).

Funciona com **qualquer** PDF de paginação Aubicon (vetorial, com a tabela
"LEGENDA DE PISOS"), independente do layout, das dimensões ou do padrão do desenho.

---

## ▶️ Como rodar no seu computador

```bash
cd contagem_piso
pip install -r requirements.txt
streamlit run app.py
```

Abre no navegador (http://localhost:8501). Arraste o PDF e pronto.

---

## ☁️ Como publicar na nuvem (link compartilhável, grátis)

A forma mais fácil é o **Streamlit Community Cloud**:

1. Crie uma conta em https://streamlit.io/cloud (login com GitHub).
2. Suba esta pasta `contagem_piso/` para um repositório no GitHub.
3. No Streamlit Cloud: **New app** → escolha o repositório → arquivo principal `app.py`.
4. Deploy. Você recebe um link público tipo `https://contagem-piso-aubicon.streamlit.app`.

Pronto: qualquer pessoa com o link acessa, anexa o PDF e recebe o quantitativo.
Toda vez que você atualizar o código no GitHub, o app atualiza sozinho.

> Alternativas de hospedagem: Hugging Face Spaces, Render, Railway. Todas rodam
> o mesmo `app.py` + `requirements.txt`.

---

## 🧠 Como funciona (e por que é genérico)

O sistema **não depende** dos arquivos de exemplo. Para cada PDF ele:

1. **Lê a legenda** ("LEGENDA DE PISOS") automaticamente: código, acabamento,
   produto, dimensão da peça, área e a cor de cada piso.
2. **Detecta o método** pela dimensão:
   - tem dimensão (ex.: `1,00 x 1,00m`) → **peça por peça**;
   - dimensão `-` (piso despejado, P.I.P) → **por área (m²)**.
3. **Extrai a geometria exata** de cada região do desenho (preenchimentos
   recortados por *clip paths*, curvas Bézier achatadas, regiões sobrepostas
   resolvidas por ordem de pintura).
4. **Calibra a escala** pela METRAGEM TOTAL da legenda.
5. **Conta**:
   - *Área*: mede os m² de cada cor e arredonda para cima ao m² inteiro.
   - *Peças*: encaixa a grade do tamanho da placa (alinhada às juntas reais) e
     conta peças inteiras + recortes por cor.
6. **Aplica a margem** (~5%, configurável) **sempre para cima**.

### Precisão (validado contra os 2 gabaritos manuais)
- **COREE / PLAYGROUND** (por área): **4/4 exato** → 118 m².
- **TERRAH / FITNESS** (por peça): ESTRELADO e VERDE FOLHA exatos; CINZA GRANIZO
  com diferença de **1 placa** (célula de fronteira) — coberta pela margem de segurança.

Rode os testes:
```bash
python3 tests/test_gabaritos.py
```

---

## ⚠️ Limitações / suposições
- O PDF precisa ser **vetorial** (exportado de CAD), não uma imagem escaneada.
- Precisa conter a tabela **"LEGENDA DE PISOS"** e a **METRAGEM TOTAL** no padrão Aubicon.
- Na contagem peça por peça, recortes em fronteiras complexas podem variar **±1 placa**
  por cor frente à contagem manual — a margem de segurança absorve essa diferença.
- A cada novo PDF que fugir do padrão, a tela de **Conferência** mostra o desenho
  para você validar visualmente; ajustes de parser podem ser feitos pontualmente.

---

## 📁 Estrutura
```
contagem_piso/
├── app.py                 # interface web (Streamlit)
├── requirements.txt
├── engine/
│   ├── legend.py          # lê a tabela LEGENDA DE PISOS
│   ├── geometry.py        # extrai polígonos exatos (clip + Bézier + oclusão)
│   ├── grid.py            # método peça por peça (grade genérica)
│   ├── counter.py         # orquestra tudo e monta o quantitativo
│   └── preview.py         # imagem para conferência
└── tests/
    └── test_gabaritos.py  # validação contra a contagem manual
```
