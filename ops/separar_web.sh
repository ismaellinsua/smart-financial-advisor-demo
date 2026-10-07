#!/usr/bin/env bash
# Copies the public website (docs/) to its own public repository, so this one (the app's code) can be private while
# nirkana.es stays online. Run it yourself after creating the EMPTY repository on GitHub (see ops/REPOSITORIO.md).
#
#   bash ops/separar_web.sh https://github.com/ismaellinsua/nirkana-web.git
#
# Later updates of the website are made in that repository; this script can be run again to copy docs/ over.
set -euo pipefail

WEB_REPO="${1:?Uso: bash ops/separar_web.sh URL_DEL_REPOSITORIO_DE_LA_WEB}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone --quiet "$WEB_REPO" "$WORK/web" 2>/dev/null || { mkdir -p "$WORK/web" && git -C "$WORK/web" init --quiet; }
cd "$WORK/web"
if git rev-parse --verify --quiet origin/main >/dev/null; then
  git checkout --quiet -B main origin/main   # run again: on top of what is already published
else
  git checkout --quiet -B main               # first time: an empty repository
fi
# Everything from docs/ (the PNG screenshots live outside it, in capturas/); what was removed from docs/ goes.
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$ROOT/docs/." ./
test -f CNAME && test -f index.html || { echo "ERROR: docs/ no tiene index.html y CNAME"; exit 1; }
cat > README.md <<'README'
# nirkana.es

Web pública de NirKanA, publicada con GitHub Pages (rama `main`, carpeta raíz, dominio en `CNAME`).
El código de la aplicación está en un repositorio privado.
README
git add -A
if git diff --cached --quiet; then
  echo "La web ya estaba al día."
  exit 0
fi
git commit --quiet -m "Web pública de NirKanA (copiada de docs/)"
git remote add origin "$WEB_REPO" 2>/dev/null || git remote set-url origin "$WEB_REPO"
git push --quiet -u origin main
echo "Web subida a $WEB_REPO. Sigue con «Activar GitHub Pages» en ops/REPOSITORIO.md."
