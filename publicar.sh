#!/bin/bash
# Publica o app no GitHub (e deixa pronto pro Streamlit Cloud).
# Uso:   ./publicar.sh SEU-USUARIO-DO-GITHUB [nome-do-repo]
# Ex.:   ./publicar.sh gabriellima contagem-piso-aubicon
#
# ANTES de rodar: crie o repositório vazio em https://github.com/new
# (mesmo nome do repo abaixo; NÃO marque "Add README").
set -e
cd "$(dirname "$0")"

USUARIO="$1"
REPO="${2:-contagem-piso-aubicon}"
if [ -z "$USUARIO" ]; then
  echo "Uso: ./publicar.sh SEU-USUARIO-DO-GITHUB [nome-do-repo]"
  exit 1
fi

# guarda o login do GitHub no chaveiro do macOS (só pede uma vez)
git config --global credential.helper osxkeychain || true

git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$USUARIO/$REPO.git"

echo ""
echo ">> Enviando para https://github.com/$USUARIO/$REPO"
echo ">> Se pedir login: usuário = seu login do GitHub; senha = um Personal Access Token"
echo "   (crie em https://github.com/settings/tokens  ->  'Generate new token (classic)', marque 'repo')."
echo ""
git push -u origin main

echo ""
echo "✅ Código no GitHub!"
echo "Agora publique em https://share.streamlit.io :"
echo "   Create app -> repo '$USUARIO/$REPO' -> branch 'main' -> main file 'app.py' -> Deploy"
