# LanceMetrics com Docker e GitHub Actions

## Aplicação analisada

Os arquivos originais permanecem intactos. O terminal está em
`backend/app/terminal.py` (não existe `terminal.py` na raiz). Foram examinados
os scripts de instalação/inicialização/parada, imports e serviços do backend,
schemas, frontend, testes e documentação de arquitetura/vídeo.

Python mínimo: **3.10**; a imagem usa **Python 3.12 / Debian Bookworm**.
`python` e `python3` apontam para o ambiente `/app/.venv`, como esperado pelos
scripts. Todas as dependências são instaladas do `backend/requirements.txt`
original, incluindo FastAPI, Uvicorn, SQLAlchemy, Pydantic, psutil, websockets,
python-multipart, httpx e pytest, com `pip check` durante o build.

O frontend React/TypeScript/Vite/Plotly é compilado usando Node 22 e `npm ci`
com o lockfile original. Uvicorn entrega frontend, API e WebSockets na mesma
porta; não há um servidor Node separado. Node/npm permanecem disponíveis
para que `install.sh` e a opção Install/Update do menu continuem utilizáveis.
A reinstalação exige acesso aos repositórios de pacotes.

Pacotes Linux explícitos: **bash, iperf3, ffmpeg, tini, ca-certificates**.
O pacote ffmpeg inclui **ffprobe**, libx264, AAC e decodificação/preview JPEG.
`tail`, usado pelo terminal e pelo entrypoint, vem do coreutils da imagem base.
SQLite e bibliotecas padrão Python vêm da imagem Python. Não há uso de ping,
captura de pacotes ou configuração de interfaces; iproute2, iputils-ping,
net-tools, procps, curl, wget, tcpdump, ethtool e sudo não são necessários.

iperf3 executa clientes TCP/UDP, modo reverso e servidor sob demanda. A versão
Debian Bookworm pode não oferecer `--json-stream`: o código detecta isso e
usa JSON final (`-J`), com atualização de resultados ao fim do estágio.
FFmpeg/ffprobe executam como subprocessos com argumentos validados, sem shell.
Sockets Python fazem os relays UDP/RTP e contadores; psutil lista interfaces
do namespace de rede atual e verifica a identidade dos processos.

`start.sh` exige usuário comum, `.venv`, frontend compilado e `run/installed`,
e inicia o backend em segundo plano. O entrypoint adicional prepara diretórios
e esse marcador, chama o script original e supervisiona o backend; SIGTERM e
SIGINT chamam `stop.sh`. Tini coleta subprocessos órfãos. O botão de finalizar
o servidor e `docker exec ... ./stop.sh` encerram também o contêiner.
Não há reinício automático por padrão: use `docker compose start` para retomar.
CRLF e permissões executáveis são tratados apenas nas cópias dentro da imagem.

## Docker Hub e secrets

1. Crie no Docker Hub um repositório **lancemetrics** na sua conta. Use público
   se quiser permitir download em qualquer máquina sem autenticação.
2. Entre em [Docker Home](https://app.docker.com/), avatar → **Account settings**
   → **Personal access tokens** → **Generate new token**. Informe descrição,
   expiração e permissão de leitura/escrita (Read & Write); Delete não é
   necessário. Copie o token apresentado uma única vez.
3. No GitHub: **Repository → Settings → Secrets and variables → Actions →
   New repository secret**. Cadastre:
   - `DOCKERHUB_USERNAME`: nome de usuário da sua conta Docker Hub.
   - `DOCKERHUB_TOKEN`: Personal Access Token, nunca sua senha normal.
4. Habilite GitHub Actions e permita as actions oficiais usadas no workflow.

Referência: [Personal access tokens](https://docs.docker.com/security/access-tokens/personal-access-tokens/).
Nenhuma credencial é embutida na imagem ou nos arquivos. O username passado ao
Compose não é senha e não substitui os secrets do GitHub.

## Desenvolvimento e automação

Após revisar os novos arquivos, seu fluxo diário será:

```bash
git add Dockerfile .dockerignore docker-entrypoint.sh docker-compose.yml DOCKER.md .github/workflows/docker-publish.yml
git commit -m "Configura Docker e publicação multi-arquitetura"
git push origin main
```

Para alterações posteriores de código:

```bash
git add .
git commit -m "Nova funcionalidade"
git push
```

O repositório atual usa `main`. `.github/workflows/docker-publish.yml` responde
a push nessa branch, push de tags `v*` e **Actions → Docker publish → Run
workflow**. A execução manual permite selecionar uma referência; apenas
`main` atualiza `latest`. Tags de release não sobrescrevem `latest`.

O workflow faz checkout, configura QEMU/Buildx, constrói uma imagem AMD64 local,
verifica `/health`, frontend, diagnostics, todos os testes backend existentes e
parada pelo script original. Só depois autentica no Docker Hub, gera metadata
e constrói/publica **linux/amd64 + linux/arm64** em um manifest multi-arquitetura.
O Dockerfile também valida dependências/ferramentas em cada arquitetura.
Falha de validação ou build impede a publicação das tags. A validação runtime
completa ARM64 ocorre em hardware ARM ou emulação; o CI faz runtime AMD64.

Cache: `type=gha`, exportação `mode=max`. Permissão GitHub: `contents: read`.
Publicações da mesma referência são serializadas. Para renomear a imagem,
altere `env.IMAGE_NAME` no workflow e `IMAGE_NAME` no ambiente do Compose.
Actions oficiais consultadas: [checkout](https://github.com/actions/checkout),
[QEMU](https://github.com/docker/setup-qemu-action),
[Buildx](https://github.com/docker/setup-buildx-action),
[login](https://github.com/docker/login-action),
[metadata](https://github.com/docker/metadata-action) e
[build/push](https://github.com/docker/build-push-action).

Esta automação publica imagens; atualizar servidores em execução continua sendo
uma operação explícita com pull e recriação do contêiner.

## Executar a imagem publicada

Substitua `USUARIO` pelo username Docker Hub. Após a primeira publicação:

```bash
docker pull USUARIO/lancemetrics:latest
docker run -d --name lancemetrics --stop-timeout 60 \
  --cap-drop ALL --security-opt no-new-privileges:true \
  -p 8080:8080/tcp -p 5201:5201/tcp -p 5201:5201/udp -p 5000:5000/udp \
  -v lance-data:/app/data -v lance-logs:/app/logs -v lance-run:/app/run \
  USUARIO/lancemetrics:latest
docker exec lancemetrics cat /app/run/access.token
```

Abra `http://localhost:8080` e informe o token da aplicação. Os logs de startup
do script original também exibem esse token; trate o acesso aos logs como
acesso à credencial da aplicação. API em `/docs`; saúde em `/health`.
O token é criado localmente, nunca copiado de `run/` do desenvolvedor.

Com Compose:

```bash
export DOCKERHUB_USERNAME=USUARIO
docker compose pull
docker compose up -d
docker compose exec lancemetrics cat /app/run/access.token
docker compose stop
docker compose start
```

Para receber a nova publicação: `docker compose pull` e `docker compose up -d`.
Para menu interativo no serviço ativo: `docker compose exec lancemetrics
./lanceMetrics`. Para reinstalar: `docker compose exec lancemetrics ./install.sh`.
Para um menu em contêiner independente, use `docker run --rm -it
USUARIO/lancemetrics:latest ./lanceMetrics`; nesse modo o menu é o processo
principal e sair do menu encerra o contêiner.

## Portas, interfaces e capabilities

| Uso | Padrão | Observação |
| --- | --- | --- |
| HTTP/API/WebSockets | 8080/TCP | `LANCE_PORT`; `LANCE_BIND=0.0.0.0` |
| iperf3 | 5201/TCP e UDP | UDP também precisa do canal de controle TCP |
| Vídeo MPEG-TS UDP ou RTP/UDP | 5000/UDP | Streams concorrentes: 5000, 5002, 5004, … |
| Relays FFmpeg/preview | Portas locais dinâmicas | Loopback interno; não publicar |

Servidores iperf e vídeo são armados pela aplicação, não automaticamente pelo
Docker. As portas são configuráveis nos formulários (1024–65535); publique as
portas escolhidas no Compose/run e permita-as no firewall. O Compose publica
um stream de vídeo; acrescente, por exemplo, `5002:5002/udp` e `5004:5004/udp`
para três streams. O espaçamento +2 reserva espaço para RTCP futuro; não há
necessidade atual de publicar a porta ímpar adjacente.

**NET_RAW, NET_ADMIN e --privileged não são necessários.** O Compose remove
todas as capabilities. O processo roda como UID/GID **10001**, com portas
acima de 1023. A aplicação não modifica interfaces, rotas, buffers globais ou
firewall. Usa sockets normais e FFmpeg/iperf sem privilégios adicionais.

Bridge funciona para a aplicação e é o padrão portátil do Compose. Nesse
modo, as interfaces e IPs exibidos são os do contêiner; configure receptores
com `0.0.0.0`, destinos remotos com IP real/DNS e forneça ao remetente externo
o IP do host. NAT e a virtualização podem afetar as medições.

Em **Linux**, host networking é recomendado quando precisar observar as
interfaces reais do host ou minimizar a interferência do NAT:

```bash
docker run -d --name lancemetrics --network host --stop-timeout 60 \
  --cap-drop ALL --security-opt no-new-privileges:true \
  -v lance-data:/app/data -v lance-logs:/app/logs -v lance-run:/app/run \
  USUARIO/lancemetrics:latest
```

Nesse caso não use `-p`. Para Compose, adicione `network_mode: host` ao serviço
e remova `ports`. Verifique conflitos com as portas já ocupadas no host.

Em **Apple Silicon M4**, Docker seleciona ARM64 automaticamente, sem forçar
`--platform linux/amd64`. Docker Desktop executa Linux numa VM: mesmo com host
networking, não fornece acesso direto às interfaces macOS. Host networking
exige Docker Desktop ≥4.34 e habilitação em Settings → Resources → Network →
Enable host networking; suporta TCP/UDP e tem limitações de bind às interfaces
do host. Para medições físicas de interfaces Mac, use execução nativa; para
medição em servidor Linux, compare com execução nativa no mesmo servidor.
Referência: [Host network driver e limitações](https://docs.docker.com/engine/network/drivers/host/).

## Volumes e variáveis

| Caminho | Conteúdo |
| --- | --- |
| `/app/data` | SQLite (incluindo WAL/SHM), perfis, experimentos, biblioteca de vídeos |
| `/app/logs` | Logs da aplicação, backend e iperf |
| `/app/run` | Token, marcador de instalação e metadados de processos |

Volumes nomeados são inicializados com propriedade UID/GID 10001. Bind mounts
devem ser graváveis por esse usuário. Não monte o projeto inteiro sobre
`/app`, nem copie `.venv`/`node_modules` de outra máquina. Não compartilhe os
mesmos volumes entre instâncias concorrentes. `run` deve ser exclusivo por
instância, pois contém identidades de processos. Os dados existentes locais
não são migrados automaticamente. Para backups SQLite, pare o serviço e copie
o volume inteiro, preservando experimentos e vídeos. Rollback de imagem não
desfaz migrações de banco: mantenha um backup antes de mudar de versão.

Variáveis suportadas: `LANCE_PORT` (8080), `LANCE_BIND` (0.0.0.0),
`LANCE_VIDEO_MAX_BYTES` (2147483648, 2 GiB/arquivo),
`LANCE_VIDEO_LIBRARY_BYTES` (53687091200, 50 GiB/biblioteca).
Se mudar a porta, ajuste também o mapeamento; o healthcheck segue `LANCE_PORT`.
`LANCE_ROOT` existe no código, mas reloca também caminhos de frontend e estado,
enquanto o terminal usa a raiz do código: no Docker mantenha `/app` e monte
os três subdiretórios indicados. O diretório `/tmp` é usado pelos testes e
temporários. Não há variável de senha/token Docker Hub para a aplicação.

## Testar localmente

```bash
docker build -t lancemetrics:local .
docker run -d --name lance-local --stop-timeout 60 --cap-drop ALL \
  --security-opt no-new-privileges:true -p 8080:8080 lancemetrics:local
docker exec lance-local python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"
docker exec lance-local ./lanceMetrics diagnostics
docker exec lance-local python -m pytest backend/tests -q -p no:cacheprovider
docker exec lance-local ./stop.sh
docker wait lance-local
docker rm lance-local
```

Diagnostics com backend ativo avisa que 8080 está ocupada, o que é esperado.
O healthcheck e a resposta HTTP confirmam que é o serviço esperado.
Os testes usam diretórios temporários, sem alterar o código original.
Valide também envio/recepção em duas máquinas e vídeo nas portas publicadas
antes de usar resultados como medições de rede física.

Build multi-arquitetura local (Docker Desktop inclui emulação):

```bash
docker buildx create --name lance-builder --driver docker-container --use
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64,linux/arm64 \
  --output type=oci,dest=/tmp/lancemetrics-multiarch.tar .
```

Em Linux, ARM64 emulado precisa de binfmt/QEMU configurado no host; o workflow
faz isso com a action oficial. Para carregar uma imagem no daemon local, use
uma plataforma por vez com `--load`. O arquivo OCI permite validar build das
duas plataformas sem publicar no Docker Hub.

## Versões e rollback

| Tag | Origem |
| --- | --- |
| `latest` | Push/execução manual em `main` |
| `sha-<SHA completo>` | Commit da execução, 40 caracteres para evitar colisões |
| `1.0.0`, `1.0`, `1` | Tag Git estável `v1.0.0` |

`metadata-action` mantém prereleases com sufixo em vez de aliases estáveis.
Para versões 0.x, omitimos o alias amplo `0`. Tags Git `v*` sem versão SemVer
válida ainda geram a tag SHA, mas não aliases de versão.

Para publicar uma release após revisão:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Descubra o commit em **GitHub → Actions → execução → commit**, nos labels OCI
`org.opencontainers.image.revision`, nas tags do Docker Hub ou com:

```bash
git log --format='%H %s' -10
docker buildx imagetools inspect USUARIO/lancemetrics:latest
```

Rollback com Compose, preservando os volumes:

```bash
export DOCKERHUB_USERNAME=USUARIO
export IMAGE_TAG=sha-COLE_AQUI_O_SHA_COMPLETO
docker pull "$DOCKERHUB_USERNAME/lancemetrics:$IMAGE_TAG"
docker compose up -d
```

Para voltar à versão atual, use `export IMAGE_TAG=latest`, `docker compose pull`
e `docker compose up -d`. Tags antigas precisam permanecer no Docker Hub;
não as exclua se quiser manter o rollback disponível.

## Revisão dos arquivos

Novos arquivos: `Dockerfile`, `.dockerignore`, `docker-entrypoint.sh`,
`docker-compose.yml`, `DOCKER.md`, `.github/workflows/docker-publish.yml`.
Nenhum arquivo original foi modificado. Nenhum commit ou push foi feito.
`git diff` não mostra arquivos novos ainda não adicionados ao índice;
`git status --short` os lista com `??`.

Validação local desta entrega: build Docker **linux/amd64** concluído, `pip
check` e diagnostics aprovados; **70 testes backend passaram** (dois avisos
das dependências/runtime). HTTP `/health`, frontend, UID 10001, `stop.sh`,
reinicialização e SIGTERM passaram dentro do contêiner sem capabilities.
Compose e sintaxe Bash/YAML foram validados. Build/runtime ARM64 não foram
executados neste host, que não tem QEMU/binfmt configurado; o workflow está
preparado para construir ambas as arquiteturas. Publicação no Docker Hub e
execução no GitHub ainda dependem de configurar os secrets e enviar os arquivos.
