#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
project=${LANCE_ALL_PROJECT:-lancemetrics-all-in-one}
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo 'Nome do projeto All in one inválido.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Instale Docker Engine/Desktop e Compose v2.' >&2; exit 1; }
docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1 || { echo 'Inicie o Docker e confira o acesso ao Compose v2.' >&2; exit 1; }
compose() { docker compose --project-name "$project" --project-directory "$ROOT/docker" -f "$ROOT/docker/docker-compose.all-in-one.yml" "$@"; }
compose config --quiet
if [[ "${1:-}" == all-stop ]]; then
    compose stop
    printf '\nTeste All in one parado. Os dados do servidor e do cliente foram preservados.\n'
    exit 0
fi
[[ "${1:-}" == all-start ]] || { echo 'Use all-start ou all-stop.' >&2; exit 1; }
image=$(compose config --images | head -n 1)
if ! docker image inspect "$image" >/dev/null 2>&1; then
    if [[ "$image" == lancemetrics:local ]]; then
        printf 'Preparando a imagem do Teste All in one...\n'
        compose build lance-servidor
    else
        compose pull
    fi
fi
compose up -d --no-build
printf 'Aguardando servidor e cliente ficarem prontos...\n'
for service in lance-servidor lance-cliente; do
    container=$(compose ps --all --quiet "$service")
    [[ -n "$container" ]] || { printf 'Container %s não encontrado.\n' "$service" >&2; exit 1; }
    attempts=${LANCE_START_TIMEOUT:-120}
    [[ "$attempts" =~ ^[1-9][0-9]{0,3}$ ]] || { echo 'LANCE_START_TIMEOUT inválido.' >&2; exit 1; }
    ready=false
    while ((attempts-- > 0)); do
        state=$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container")
        case "$state" in
            'running healthy') ready=true; break ;;
            exited*|dead*|*unhealthy) break ;;
        esac
        sleep 1
    done
    if ! $ready; then
        compose logs --tail 30 "$service"
        printf '\n%s não ficou pronto. Use [5] para parar o teste e confira as portas disponíveis.\n' "$service" >&2
        exit 1
    fi
done
link() {
    local published
    published=$(compose port "$1" 8080)
    [[ "$published" =~ :([0-9]+)$ ]] || return 1
    printf 'http://localhost:%s' "${BASH_REMATCH[1]}"
}
server_url=$(link lance-servidor)
client_url=$(link lance-cliente)
printf '\nTeste All in one pronto. Clique nos links para acessar:\n'
printf '  Servidor: %s\n' "$server_url"
printf '  Cliente:  %s\n\n' "$client_url"
printf 'Para testar vídeo:\n'
printf '  Cliente → Video Streaming → Cliente: endereço 0.0.0.0, porta 6000.\n'
printf '  Servidor → Video Streaming → Servidor: destino lance-cliente, porta 6000.\n'
printf '  URL do cliente para coordenação: http://lance-cliente:8080\n'
printf '  Escolha o mesmo transporte nos dois lados; carregue e envie um vídeo.\n'
printf '\nUse [5] Parar Teste All in one para parar as duas instâncias.\n'
