# LANCE Metrics · Bare metal

Esta pasta contém a aplicação completa: `backend/`, `frontend/`, `examples/`,
`docs/` e os scripts nativos. O build Docker reutiliza estes mesmos fontes,
sem duplicar a aplicação. A raiz do repositório oferece o menu Docker.

Na raiz do projeto:

```bash
./bare-metal/install.sh
./bare-metal/start.sh
# Abra http://localhost:8080
./bare-metal/stop.sh
```

Ou entre nesta pasta e execute `./lanceMetrics` para usar o menu nativo original.
Requisitos: Ubuntu/Debian ou macOS, Python >=3.10, Node >=18, npm, iperf3 e
FFmpeg/ffprobe. O instalador usa sudo somente para dependências do sistema;
execute a aplicação como usuário comum. A instalação preserva os dados.

Ambiente e dados locais ficam nesta pasta: `.venv/`, `data/`, `logs/` e `run/`.
Esses arquivos são ignorados pelo Git e não fazem parte do download do projeto.
Os volumes Docker são independentes; dados nativos não são migrados para eles.

Outra porta: `LANCE_PORT=8081 ./bare-metal/start.sh`. Por padrão, a interface
abre sem token. Para exigir autenticação, use `LANCE_AUTH_ENABLED=true` ao
iniciar. Diagnósticos: `./bare-metal/lanceMetrics diagnostics`.

Verificações (a partir desta pasta):

```bash
.venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
cd frontend && npx playwright test
```

Documentação: [arquitetura](docs/ARCHITECTURE.md), [vídeo](docs/VIDEO_STREAMING.md)
e [tour interativo](docs/PRODUCT_TOUR.md). Docker: [guia](../docker/README.md).
