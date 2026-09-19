#!/usr/bin/env bash
# Despliegue de la API con respaldo previo (RNF-18).
#
# Respalda la base, construye la imagen, levanta la version nueva y
# espera a que responda. Si no responde, deja impreso el comando exacto
# para volver atras. La migracion la corre el contenedor al arrancar: si
# falla, el contenedor no levanta y la version anterior sigue sirviendo.
#
# Uso, en el servidor y desde la raiz del repositorio:
#   ./deploy/desplegar.sh

set -euo pipefail

CONTENEDOR_DE_LA_BASE="${CONTENEDOR_DE_LA_BASE:-data-center-db-1}"
BASE="${BASE:-stockarg}"
USUARIO_DE_LA_BASE="${USUARIO_DE_LA_BASE:-stockarg}"
CARPETA_DE_RESPALDOS="${CARPETA_DE_RESPALDOS:-${HOME}/backups/stockarg}"
COMPOSE="deploy/docker-compose.prod.yml"
ESPERA_MAXIMA="${ESPERA_MAXIMA:-90}"

marca="$(date +%Y%m%d-%H%M%S)"
respaldo="${CARPETA_DE_RESPALDOS}/stockarg-${marca}.sql.gz"
version_nueva="$(git rev-parse --short HEAD)"
# La version que esta sirviendo ahora no es la del checkout: el pull ya
# lo movio. Se guarda aparte en cada despliegue exitoso.
archivo_de_version="${CARPETA_DE_RESPALDOS}/version-desplegada"
version_anterior="$(cat "${archivo_de_version}" 2>/dev/null || echo "${version_nueva}")"

echo "==> 1/4 Respaldando ${BASE}"
mkdir -p "${CARPETA_DE_RESPALDOS}"
docker exec "${CONTENEDOR_DE_LA_BASE}" \
    pg_dump -U "${USUARIO_DE_LA_BASE}" -d "${BASE}" | gzip >"${respaldo}"
echo "    respaldo: ${respaldo} ($(du -h "${respaldo}" | cut -f1))"

volver_atras() {
    cat <<FIN

Para volver atras:

  git checkout ${version_anterior}
  docker compose -f ${COMPOSE} up -d --build

Y si hace falta restaurar la base:

  gunzip -c ${respaldo} \\
    | docker exec -i ${CONTENEDOR_DE_LA_BASE} \\
        psql -U ${USUARIO_DE_LA_BASE} -d ${BASE}
FIN
}

echo "==> 2/4 Construyendo la imagen"
docker compose -f "${COMPOSE}" build

echo "==> 3/4 Levantando la version nueva"
docker compose -f "${COMPOSE}" up -d

echo "==> 4/4 Esperando a que la API responda"
for _ in $(seq 1 "${ESPERA_MAXIMA}"); do
    estado="$(docker inspect -f '{{.State.Health.Status}}' stockarg-api 2>/dev/null || echo sin_datos)"
    if [ "${estado}" = "healthy" ]; then
        echo "    la API responde"
        volver_atras
        echo
        echo "${version_nueva}" >"${archivo_de_version}"
        echo "Despliegue terminado: ${version_nueva}. Version anterior: ${version_anterior}"
        exit 0
    fi
    if [ "${estado}" = "unhealthy" ]; then
        break
    fi
    sleep 1
done

echo "ERROR: la API no quedo sana. Ultimas lineas del contenedor:" >&2
docker compose -f "${COMPOSE}" logs --tail 40 api >&2
volver_atras
exit 1
