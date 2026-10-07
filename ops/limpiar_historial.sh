#!/usr/bin/env bash
# Removes from EVERY commit of the repository the files that should never have been public (the business plan) and,
# given your GitHub noreply address, replaces your personal email in every commit with it. Then pushes the rewritten
# history. Run it yourself, once, on your own computer, after reading ops/REPOSITORIO.md.
#
#   bash ops/limpiar_historial.sh https://github.com/ismaellinsua/smart-financial-advisor-demo.git \
#        12345678+ismaellinsua@users.noreply.github.com
#
# (The noreply address is in GitHub → Settings → Emails, under «Keep my email addresses private».)
#
# What it does:
#   1. Clones a full mirror to ./copia-antes-de-limpiar.git (keep it until you are sure all is well).
#   2. Rewrites a second mirror without those files and, with the noreply address, with every author and committer
#      email that is not already a noreply one (yours) replaced by it (git filter-repo), and checks the result.
#   3. Asks before the force push: it rewrites every branch and tag, so open pull requests and other clones must be
#      re-cloned afterwards. GitHub may keep cached views of old commits for a while: ask GitHub Support to purge them
#      (https://support.github.com, «Remove sensitive data»).
set -euo pipefail

REPO="${1:?Uso: bash ops/limpiar_historial.sh URL_DEL_REPOSITORIO [TU_EMAIL_NOREPLY_DE_GITHUB]}"
NOREPLY="${2:-}"
if [ -n "$NOREPLY" ] && [[ "$NOREPLY" != *@users.noreply.github.com ]]; then
  echo "El segundo argumento debe ser tu dirección …@users.noreply.github.com (GitHub → Settings → Emails)."
  exit 1
fi
FILES=(NEGOCIO.md NirKanA-negocio.pdf)
command -v git-filter-repo >/dev/null || { echo "Instala git-filter-repo: pip install git-filter-repo"; exit 1; }

git clone --mirror "$REPO" copia-antes-de-limpiar.git
git clone --mirror "$REPO" limpio.git
cd limpio.git
args=()
for f in "${FILES[@]}"; do args+=(--path "$f"); done
git filter-repo --invert-paths "${args[@]}" --force

# Emails that are already private: GitHub's noreply addresses (yours, bots, web merges) and the assistant's.
private() { grep -viE '@users\.noreply\.github\.com$|^noreply@github\.com$|^noreply@anthropic\.com$' || true; }
mask() { sed -E 's/^(.)[^@]*@(.).*$/\1***@\2***/'; }
if [ -n "$NOREPLY" ]; then
  personal=$(git log --all --format='%ae%n%ce' | sort -u | private)
  if [ -n "$personal" ]; then
    echo "Se sustituyen por $NOREPLY: $(echo "$personal" | mask | tr '\n' ' ')"
    mailmap=$(mktemp)
    while read -r email; do echo "<$NOREPLY> <$email>"; done <<< "$personal" > "$mailmap"
    git filter-repo --mailmap "$mailmap" --force
    rm -f "$mailmap"
  fi
  if [ -n "$(git log --all --format='%ae%n%ce' | sort -u | private)" ]; then
    echo "ERROR: quedan emails personales en el historial; no se sube nada."
    exit 1
  fi
  echo "Ningún commit muestra ya un email personal."
fi

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
