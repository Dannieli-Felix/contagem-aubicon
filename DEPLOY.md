# 🚀 Publicar na nuvem (Streamlit Community Cloud — grátis)

O repositório já está pronto e com o commit inicial feito. Faltam só 2 partes:
mandar para o **GitHub** e ligar no **Streamlit Cloud**.

## 1) Criar o repositório no GitHub
1. Acesse https://github.com/new
2. Nome sugerido: `contagem-piso-aubicon`
3. Pode deixar **Private** (privado). **Não** marque "Add README" (já temos um).
4. Clique em **Create repository**.

## 2) Enviar o código (rode no Terminal, dentro desta pasta)
Troque `SEU-USUARIO` pelo seu usuário do GitHub:

```bash
cd "/Users/gabriellima/Documents/Aubicon - Contagem de piso/contagem_piso"
git remote add origin https://github.com/SEU-USUARIO/contagem-piso-aubicon.git
git push -u origin main
```
(O GitHub vai pedir login na primeira vez.)

## 3) Publicar no Streamlit Cloud
1. Acesse https://share.streamlit.io e entre com a sua conta do **GitHub**.
2. Clique em **Create app** → **Deploy a public app from GitHub** (ou o repo privado).
3. Preencha:
   - **Repository:** `SEU-USUARIO/contagem-piso-aubicon`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Clique em **Deploy**. Em ~2 min você recebe um link público, ex.:
   `https://contagem-piso-aubicon.streamlit.app`

Pronto — qualquer pessoa com o link acessa, anexa o PDF e recebe o quantitativo.

## Atualizações futuras
Toda vez que você mudar o código:
```bash
git add -A
git commit -m "descrição da mudança"
git push
```
O app na nuvem atualiza sozinho em segundos.

## Observações
- As dependências (`streamlit`, `PyMuPDF`, `shapely`, `numpy`) estão no
  `requirements.txt` e são instaladas automaticamente. Não precisa de mais nada.
- Os PDFs/planilhas de projetos **não** vão para o repositório (estão no
  `.gitignore`) — só o app é publicado.
