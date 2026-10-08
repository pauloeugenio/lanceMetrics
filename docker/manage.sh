#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
command_name=start
project=${LANCE_PROJECT:-lancemetrics}
open_browser=false
usage() {
    cat <<'HELP'
LANCE Metrics · Docker

Uso: ./lanceMetrics [comando] [opções]
  start     Iniciar em segundo plano (padrão); preparar imagem se necessário
  stop      Parar a aplicação, preservando os dados
  restart   Reiniciar e mostrar o endereço
  status    Mostrar o estado e o endereço da aplicação
  logs      Acompanhar logs; Ctrl+C sai sem parar a aplicação
  update    Reconstruir/baixar a imagem e recriar a aplicação
  open      Abrir a aplicação já iniciada no navegador
  all-start Iniciar servidor e cliente do Teste All in one
  all-stop  Parar os dois containers do Teste All in one

Opções:
  --name NOME          Instância/volumes independentes (padrão: lancemetrics)
  --port PORTA         Porta da interface (padrão: 8080)
  --iperf-port PORTA   Porta TCP/UDP do iperf3 (padrão: 5201)
  --video-ports FAIXA  Portas UDP de vídeo (padrão: 5000-5018)
  --open              Abrir o navegador após iniciar
  --help              Mostrar esta ajuda

Configuração persistente opcional: docker/.env (veja docker/.env.example).
Servidor e cliente usam o mesmo comando; escolha o papel na interface.
HELP
}
fail() { printf 'Erro: %s\n' "$*" >&2; exit 1; }
port_valid() { [[ "$1" =~ ^[0-9]{1,5}$ ]] && ((10#$1 >= 1024 && 10#$1 <= 65535)); }
while (($#)); do
    case "$1" in
        start|stop|restart|status|logs|update|open|all-start|all-stop) command_name=$1; shift ;;
        --help|-h) usage; exit 0 ;;
        --open) open_browser=true; shift ;;
        --name|--port|--iperf-port|--video-ports)
            option=$1; (($# >= 2)) || fail "Falta o valor de $option."
            case "$option" in
                --name) project=$2 ;;
                --port) port_valid "$2" || fail 'Porta HTTP inválida (1024–65535).'; export LANCE_HTTP_PORT=$2 ;;
                --iperf-port) port_valid "$2" || fail 'Porta iperf3 inválida (1024–65535).'; export LANCE_IPERF_PORT=$2 ;;
                --video-ports)
                    [[ "$2" =~ ^([0-9]{1,5})(-([0-9]{1,5}))?$ ]] || fail 'Use uma porta ou uma faixa de vídeo, como 5000-5018.'
                    first=${BASH_REMATCH[1]}; last=${BASH_REMATCH[3]:-$first}
                    port_valid "$first" && port_valid "$last" && ((10#$first <= 10#$last)) || fail 'Faixa de vídeo inválida (1024–65535).'
                    export LANCE_VIDEO_PORT_RANGE=$2 ;;
            esac
            shift 2 ;;
        *) fail "Opção desconhecida: $1. Use --help." ;;
    esac
done
if [[ "$command_name" == all-start || "$command_name" == all-stop ]]; then
    exec bash "$ROOT/docker/all-in-one.sh" "$command_name"
fi
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || fail 'O nome deve usar letras minúsculas, números, hífen ou sublinhado.'
# Remember explicit ports for each instance, without sourcing executable files.
settings="$ROOT/docker/.instances/$project.env"
if [[ -f "$settings" ]]; then
    while IFS='=' read -r key value; do
        case "$key" in
            LANCE_HTTP_PORT|LANCE_IPERF_PORT|LANCE_VIDEO_PORT_RANGE)
                if [[ -z "${!key:-}" ]]; then export "$key=$value"; fi ;;
        esac
    done < "$settings"
fi
save_ports() {
    local key
    mkdir -p -- "$ROOT/docker/.instances"
    (umask 077; : > "$settings")
    for key in LANCE_HTTP_PORT LANCE_IPERF_PORT LANCE_VIDEO_PORT_RANGE; do
        if [[ -n "${!key:-}" ]]; then printf '%s=%s\n' "$key" "${!key}" >> "$settings"; fi
    done
}
command -v docker >/dev/null || fail 'Instale Docker Engine/Desktop e Docker Compose antes de iniciar (docker/README.md).'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 indisponível. Instale o plugin Compose ou Docker Desktop.'
docker info >/dev/null 2>&1 || fail 'Docker não está acessível. Inicie Docker Engine/Desktop e confira as permissões do seu usuário.'
compose() { docker compose --project-name "$project" --project-directory "$ROOT/docker" -f "$ROOT/docker/docker-compose.yml" "$@"; }
compose config --quiet
image=$(compose config --images)

show_url() {
    local published
    published=$(compose port lancemetrics 8080 2>/dev/null) || return 1
    [[ "$published" =~ :([0-9]+)$ ]] || return 1
    url="http://localhost:${BASH_REMATCH[1]}"
    printf '\nLANCE Metrics disponível em:\n  %s\n\n' "$url"
    printf 'Clique no link acima ou copie-o para o navegador.\n'
    printf 'Em outra máquina da rede, substitua localhost pelo IP deste computador.\n'
    printf 'Parar: ./lanceMetrics stop --name %s\n' "$project"
}
browser() {
    # Remote/headless terminals keep the URL usable without requiring a GUI.
    if [[ "$(uname -s)" == Darwin ]] && command -v open >/dev/null; then
        open "$url" >/dev/null 2>&1 || printf 'Abra manualmente: %s\n' "$url"
    elif [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v xdg-open >/dev/null; then
        (xdg-open "$url" >/dev/null 2>&1 || true) &
    else
        printf 'Navegador gráfico indisponível nesta sessão. Abra manualmente: %s\n' "$url"
    fi
}
wait_ready() {
    local container state attempts=${LANCE_START_TIMEOUT:-120}
    [[ "$attempts" =~ ^[1-9][0-9]{0,3}$ ]] || fail 'LANCE_START_TIMEOUT deve ser um número positivo de segundos (até 9999).'
    container=$(compose ps --all --quiet lancemetrics)
    [[ -n "$container" ]] || fail 'Container não encontrado após a inicialização.'
    printf 'Aguardando a aplicação ficar pronta...\n'
    while ((attempts-- > 0)); do
        state=$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container")
        case "$state" in
            'running healthy') show_url || fail 'Não foi possível descobrir a porta publicada.'; return 0 ;;
            exited*|dead*|*unhealthy) compose logs --tail 30; fail 'A aplicação não iniciou corretamente. Consulte os logs acima.' ;;
        esac
        sleep 1
    done
    compose logs --tail 30
    fail "A aplicação ainda não ficou pronta. Confira ./lanceMetrics logs --name $project."
}
prepare_image() {
    if [[ "$image" == 'lancemetrics:local' ]]; then
        printf 'Preparando a imagem local (a primeira execução pode demorar)...\n'
        compose build lancemetrics
    else
        printf 'Baixando a imagem %s...\n' "$image"
        compose pull lancemetrics
    fi
}
case "$command_name" in
    start)
        docker image inspect "$image" >/dev/null 2>&1 || prepare_image
        compose up -d --no-build
        save_ports
        wait_ready
        $open_browser && browser ;;
    update)
        prepare_image
        compose up -d --no-build --force-recreate
        save_ports
        wait_ready
        $open_browser && browser ;;
    restart) compose restart; wait_ready; $open_browser && browser ;;
    stop) compose stop; printf '\nAplicação parada. Os dados foram preservados.\n' ;;
    status) compose ps --all; show_url || printf '\nAplicação parada; use ./lanceMetrics start --name %s.\n' "$project" ;;
    logs) compose logs --follow --tail 100 ;;
    open) show_url || fail 'Inicie a aplicação antes de abrir o navegador.'; browser ;;
esac
exit 0
