#!/usr/bin/env bash
# Removes from EVERY commit of the repository the files that should never have been public (the business plan), and
# pushes the rewritten history. Run it yourself, once, on your own computer, after reading ops/REPOSITORIO.md.
#
#   bash ops/limpiar_historial.sh https://github.com/ismaellinsua/smart-financial-advisor-demo.git
#
# What it does:
#   1. Clones a full mirror to ./copia-antes-de-limpiar.git (keep it until you are sure all is well).
#   2. Rewrites a second mirror without those files (git filter-repo) and checks they are gone.
#   3. Asks before the force push: it rewrites every branch and tag, so open pull requests and other clones must be
#      re-cloned afterwards. GitHub may keep cached views of old commits for a while: ask GitHub Support to purge them
#      (https://support.github.com, «Remove sensitive data»).
set -euo pipefail

REPO="${1:?Uso: bash ops/limpiar_historial.sh URL_DEL_REPOSITORIO}"
FILES=(NEGOCIO.md NirKanA-negocio.pdf)
command -v git-filter-repo >/dev/null || { echo "Instala git-filter-repo: pip install git-filter-repo"; exit 1; }

git clone --mirror "$REPO" copia-antes-de-limpiar.git
git clone --mirror "$REPO" limpio.git
cd limpio.git
args=()
for f in "${FILES[@]}"; do args+=(--path "$f"); done
git filter-repo --invert-paths "${args[@]}" --force

for f in "${FILES[@]}"; do
  if [ -n "$(git log --all --format=%H -- "$f")" ]; then
    echo "ERROR: $f sigue en el historial; no se sube nada."
    exit 1
  fi
done
echo "Historial limpio: ${FILES[*]} ya no aparece en ningún commit."
git remote add origin "$REPO" 2>/dev/null || git remote set-url origin "$REPO"

read -r -p "¿Subir el historial reescrito a $REPO (force push de todas las ramas)? Escribe SI: " answer
if [ "$answer" != "SI" ]; then
  echo "No se ha subido nada. La copia limpia está en $(pwd)."
  exit 0
fi
git push --force --mirror origin
echo "Hecho. Vuelve a clonar el repositorio en cada equipo y guarda copia-antes-de-limpiar.git hasta comprobarlo."
