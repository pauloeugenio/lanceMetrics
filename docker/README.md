# Docker · LANCE Metrics

A mesma aplicação serve como cliente ou servidor. Os arquivos de instalação
Docker ficam nesta pasta; backend/frontend ficam em `bare-metal/` e são usados pelo build Docker.
Para instalação sem containers, veja [bare-metal](../bare-metal/README.md).

## Início simples

Instale Docker Engine e o plugin Compose v2 em Linux, ou Docker Desktop em
macOS/Windows com Bash/WSL. Docker deve estar iniciado e acessível ao seu usuário.
O launcher verifica isso e informa como corrigir; não instala Docker nem altera
as permissões do host automaticamente.

Na raiz do projeto:

```bash
chmod +x lanceMetrics
./lanceMetrics
```

O comando abre um menu. Escolha **[1] Iniciar LANCE Metrics**. Na primeira inicialização, a imagem local é construída com as dependências e o
frontend atual. A aplicação sobe em segundo plano; o script aguarda o health
check e imprime `http://localhost:8080`. Terminais que reconhecem URLs permitem
clicar no endereço. `./lanceMetrics --open` também abre um navegador gráfico
quando disponível. Em SSH/servidores sem desktop, copie o endereço e substitua
`localhost` pelo IP do host para acessar de outra máquina.

Não é necessário token por padrão. O tutorial aparece no primeiro acesso e
pode ser repetido pelo botão Ajuda. Sair do menu ([0]) ou fechar o terminal/navegador não para o serviço.

```bash
./lanceMetrics status
./lanceMetrics logs       # Ctrl+C sai dos logs, mantendo a aplicação
./lanceMetrics stop       # preserva os volumes
./lanceMetrics start
./lanceMetrics restart
./lanceMetrics open
./lanceMetrics update     # build local ou pull da imagem publicada; recria
./lanceMetrics --help
```

`start` reutiliza a imagem existente. Após modificar o código, execute `update`
para reconstruir o frontend/backend na imagem. O launcher não publica imagens.
Se uma porta estiver ocupada, escolha outra; ele não encerra serviços externos.
A espera de saúde padrão é 120 segundos, configurável com `LANCE_START_TIMEOUT`.

## Teste All in one pelo menu

Execute `./lanceMetrics` e escolha **[4] Teste All in one**. O launcher inicia
os dois containers na mesma rede Docker e mostra os links após ambos ficarem
prontos. **[5] Parar Teste All in one** para somente essas duas instâncias,
preservando os volumes. A aplicação normal ([1]/[2]) é independente.

- Servidor: `http://localhost:8081`, iperf3 publicado em 5203, vídeo 7000–7018.
- Cliente: `http://localhost:8082`, iperf3 publicado em 5204, vídeo 6000–6018.
- No cliente, selecione o papel Cliente em Video Streaming e porta base 6000.
- No servidor, selecione Servidor, destino `lance-cliente`, porta 6000 e URL de
  coordenação `http://lance-cliente:8080`. Use o mesmo transporte nos dois lados.
- Para iperf3 entre os containers, o destino é `lance-servidor` e porta interna
  5201, com o servidor iniciado pela interface.

O launcher prepara as instâncias; carregar vídeos e iniciar transmissões/testes
continua sendo feito pela interface. As portas externas são diferentes; ambos
usam porta 8080 interna. Dados, logs e processos ficam separados. Sair do menu
mantém ambos rodando. Comandos diretos: `./lanceMetrics all-start` / `all-stop`.

O projeto padrão é `lancemetrics-all-in-one`. Para testes ou conflitos de portas,
configure `LANCE_ALL_PROJECT`, `LANCE_ALL_SERVER_HTTP_PORT`,
`LANCE_ALL_CLIENT_HTTP_PORT`, `LANCE_ALL_SERVER_IPERF_PORT`,
`LANCE_ALL_CLIENT_IPERF_PORT`, `LANCE_ALL_SERVER_VIDEO_PORTS` e
`LANCE_ALL_CLIENT_VIDEO_PORTS`. As faixas de vídeo externas mapeiam para as
faixas internas fixas acima. O arquivo é `docker-compose.all-in-one.yml`.

## Duas instâncias no mesmo computador

```bash
./lanceMetrics --name lance-servidor --port 8081 --iperf-port 5201 --video-ports 5000-5018
./lanceMetrics --name lance-cliente --port 8082 --iperf-port 5202 --video-ports 6000-6018
```

Cada nome cria containers/rede e volumes separados. As portas explícitas são
lembradas em `docker/.instances/<nome>.env` (ignorado pelo Git). Para retomar ou
parar, basta informar o nome:

```bash
./lanceMetrics start --name lance-cliente
./lanceMetrics stop --name lance-cliente
./lanceMetrics update --name lance-servidor
```

Abra `http://localhost:8081` e `http://localhost:8082`. Escolha os papéis em
**Video Streaming**. O cliente escuta em `0.0.0.0`, porta base `6000`; o servidor
envia para o IP de rede deste computador, porta `6000`, com o mesmo transporte.
Para coordenação, use `http://IP_DO_COMPUTADOR:8082`, deixando token vazio.
Dentro do container, `localhost` aponta para o próprio container, não o host
nem o outro cliente. Para um servidor iperf3 na segunda instância, configure
`5202` na interface: a publicação preserva o número da porta dentro do container.

Em duas máquinas, use o comando padrão em ambas. O servidor envia para o IP
real do cliente e porta `5000`; a URL do cliente é `http://IP_DO_CLIENTE:8080`.
Inicie o receptor antes do envio, ou configure a coordenação com o cliente.
O launcher inicia a interface; os testes/transmissões são iniciados pela UI.
Veja [vídeo](../bare-metal/docs/VIDEO_STREAMING.md) e [tour](../bare-metal/docs/PRODUCT_TOUR.md).

## Configuração e execução direta

Copie `.env.example` para `.env` nesta pasta para guardar portas, autenticação e
imagem. Não é necessário fazer isso para usar os padrões. Opções de linha de
comando e variáveis exportadas têm prioridade; portas salvas de uma instância
têm prioridade sobre `.env`. Edite/remova seu arquivo `.instances/<nome>.env`
para voltar aos padrões. Dados dos experimentos ficam nos volumes, não nesses
arquivos de configuração.

```bash
# Build direto: o contexto deve ser a raiz do projeto
docker build -f docker/Dockerfile -t lancemetrics:local .
# Compose direto: sempre use o arquivo desta pasta
docker compose -p lancemetrics -f docker/docker-compose.yml up -d
docker compose -p lancemetrics -f docker/docker-compose.yml stop
```

Para usar uma imagem publicada em vez de compilar, configure em `docker/.env`:

```dotenv
LANCE_IMAGE=USUARIO/lancemetrics:latest
```

O launcher baixa essa imagem quando ausente; `update` faz pull e recria o
serviço. Imagens privadas exigem `docker login` prévio. Não são coletadas ou
salvas credenciais Docker pelo script.

## Portas, dados e segurança

- HTTP/API/WebSockets: `8080/TCP`, configurável por `--port`.
- iperf3: `5201/TCP+UDP`, configurável por `--iperf-port`; use a mesma porta na UI.
- Vídeo: `5000–5018/UDP`, configurável por `--video-ports`; streams usam base+2.
- Bind do backend: `0.0.0.0:8080` dentro do container.

Permita as portas usadas no firewall. Bridge é o modo padrão; os IPs/interfaces
exibidos na UI pertencem ao container. As métricas refletem o ambiente container.
Cada projeto Compose possui volumes `lance-data`, `lance-logs` e `lance-run`
com prefixo do projeto. `stop`, `restart` e `update` preservam esses volumes.
Não use `docker compose down -v` se quiser manter experimentos, vídeos e logs.
Os dados bare metal ficam em `bare-metal/data` e não são migrados automaticamente.

O processo roda como UID/GID 10001, sem capabilities e sem privilégios extras.
SIGTERM encerra os processos gerenciados; há 60 segundos de tolerância.
Não há reinício automático, preservando a parada intencional pela aplicação.
Autenticação é opcional: `LANCE_AUTH_ENABLED=true` em `.env` e `update` para
recriar. O token então pode ser obtido com
`docker compose -p lancemetrics -f docker/docker-compose.yml exec lancemetrics cat /app/run/access.token`.
Em modo sem autenticação, use uma rede de laboratório confiável.

## Organização e publicação

- `Dockerfile`: build Node 22 e runtime Python 3.12, iperf3, FFmpeg, tini.
- `docker-compose.yml`: serviço, portas, volumes e isolamento por projeto.
- `docker-entrypoint.sh`: supervisiona o backend e encaminha a parada.
- `.env.example`: opções de instalação.
- `Dockerfile.dockerignore`: filtro do contexto na raiz, exclui dependências locais/dados/segredos.
- `../lanceMetrics`: launcher Docker do host.
- `../bare-metal/`: aplicação completa e scripts nativos, reutilizados no build Docker.

A automação continua em `.github/workflows/docker-publish.yml`, como exigido
pelo GitHub. Ambos os builds usam `docker/Dockerfile` com contexto na raiz.
Cadastre os secrets `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN` (token Docker Hub
com leitura/escrita). Push em `main`, tags `v*` ou execução manual validam
AMD64 e publicam AMD64/ARM64; só `main` atualiza `latest`.
Atualizar containers continua sendo explícito com `./lanceMetrics update`.
Nenhuma publicação é feita pelo launcher local.
