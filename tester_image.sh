#!/usr/bin/env bash
# Teste omd_prometheus_exporter dans l'image Odoo réelle, contre un PostgreSQL jetable.
# Usage : ./tester_image.sh <serie> [image]   (ex. ./tester_image.sh 19.0)
# Le module testé est la copie de travail du dépôt, pas une branche.
# MODULES_EN_PLUS=mail,website : installés avec lui (collecteurs de présence et de visiteurs).
set -u
SERIE=${1:?série Odoo attendue, ex. 19.0}
IMAGE=${2:-odoo:$SERIE}
REPO=$(cd "$(dirname "$0")" && pwd)
BASE=$(mktemp -d "${TMPDIR:-/tmp}/omd-exporter-$SERIE.XXXXXX")
RES=omd-exp-test-$(echo "$SERIE" | tr -d '.')-$$
nettoyer() { docker rm -f "$RES-odoo" "$RES-pg" >/dev/null 2>&1; docker network rm "$RES-net" >/dev/null 2>&1; }
trap nettoyer EXIT

mkdir -p "$BASE/addons/omd_prometheus_exporter"
(cd "$REPO" && tar -c --exclude=.git --exclude=__pycache__ .) | tar -x -C "$BASE/addons/omd_prometheus_exporter"
chmod -R a+rwX "$BASE"

docker network create "$RES-net" >/dev/null
docker run -d --name "$RES-pg" --network "$RES-net" \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres postgres:16 >/dev/null
for _ in $(seq 1 60); do docker exec "$RES-pg" pg_isready -U odoo >/dev/null 2>&1 && break; sleep 1; done

docker run --name "$RES-odoo" --network "$RES-net" \
  -e HOST="$RES-pg" -e USER=odoo -e PASSWORD=odoo \
  -v "$BASE/addons:/mnt/extra-addons" "$IMAGE" \
  -d testdb -i "omd_prometheus_exporter${MODULES_EN_PLUS:+,$MODULES_EN_PLUS}" --test-enable --test-tags omydoo --stop-after-init --log-level=info \
  > "$BASE/sortie.log" 2>&1
CODE=$?
echo "--- $SERIE sur $IMAGE, modules en plus : ${MODULES_EN_PLUS:-aucun} (sortie $CODE)"
grep -o -E "[0-9]+ failed, [0-9]+ error\(s\) of [0-9]+ tests" "$BASE/sortie.log" | tail -1
grep -E "FAIL: |ERROR: |Traceback|invalid manifest" "$BASE/sortie.log" | head -6
if [ "$CODE" = "0" ] && grep -q " 0 failed, 0 error(s)" "$BASE/sortie.log"; then
  echo "RESULTAT: VERT"
else
  echo "RESULTAT: ROUGE ($BASE/sortie.log)"
fi
