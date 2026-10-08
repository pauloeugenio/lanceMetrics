# Entrega do módulo Video Streaming

O módulo foi acrescentado ao projeto existente em `/home/paulo/lanceMetrics`. Iperf3 permanece em seu runner próprio. A interface mantém o logo, a navegação e o arquivo de experimentos existentes.

## Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/video_schemas.py` | Validação de Sender, Receiver, fila e anúncios de sessão |
| `backend/app/video_api.py` | Rotas autenticadas e WebSocket do preview |
| `backend/app/services/video_store.py` | VideoAsset, VideoSession, persistência e agregação |
| `backend/app/services/video_library.py` | Upload streaming com limites e biblioteca única |
| `backend/app/services/video_probe.py` | Metadata ffprobe e janelas reais de bitrate |
| `backend/app/services/video_command.py` | Argumentos FFmpeg sem shell |
| `backend/app/services/video_sender.py` | VideoTrafficGenerator, transmissão e fila |
| `backend/app/services/video_receiver.py` | Recepção UDP/RTP e sessões persistentes |
| `backend/app/services/video_network.py` | Contadores independentes, sequências RTP e jitter |
| `backend/app/services/video_preview.py` | Decodificação e quadros JPEG reais |
| `backend/app/services/video_peer.py` | Coordenação autorizada por token |
| `backend/app/services/video_tools.py` | Preferência por ferramentas do sistema e fallback local |
| `frontend/src/VideoStreaming.tsx` | VideoStreaming, VideoExecution, VideoResults e LivePreview |
| `backend/tests/test_video.py` | Testes de validação, métricas, persistência e fluxo real |
| `frontend/tests/video.spec.ts` | Upload de 20 arquivos e fluxo real no navegador |
| `docs/VIDEO_STREAMING.md` | Guia completo, APIs, métricas e limites |
| `docs/video-receiver.png`, `docs/video-results.png` | Evidências capturadas pelo navegador |

## Arquivos modificados

- `backend/app/main.py`: integração do router, ciclo de vida, parada e exclusão de vídeo.
- `backend/app/database.py`: criação das tabelas novas sem substituir as antigas.
- `backend/app/lifecycle.py`: fallback de parada dos FFmpeg com identidade de processo verificada.
- `backend/app/terminal.py`: Diagnostics com FFmpeg/ffprobe e versões.
- `backend/app/services/process_manager.py`: ambiente de subprocesso e período de finalização configuráveis; padrões existentes preservados.
- `backend/app/services/traffic_generator.py`: extensão tipada para configurações dos diferentes geradores.
- `backend/app/services/export_service.py`: CSV específico de vídeo na exportação compartilhada.
- `frontend/src/main.tsx`: Experiment Type, sidebar, acompanhamento e resultados de vídeo; gráficos compartilhados com séries separadas por sessão.
- `frontend/src/style.css`: dataset, fila, progresso e preview dentro da identidade existente.
- `install.sh`: dependências FFmpeg/ffprobe em Ubuntu/Debian e macOS.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/METRICS.md`, `docs/ROADMAP.md`, `docs/VALIDATION.md`: documentação atualizada.
- `frontend/dist`: build atualizado da aplicação integrada.

## Banco e dependências

A migração é aditiva: `video_assets` e `video_sessions`. Experiment, Measurement e StoredProfile continuam existentes. As sessões de vídeo também aparecem no JSON do experimento. A chave estrangeira de sessão remove seus registros quando o experimento é excluído; os arquivos da biblioteca continuam disponíveis.

Antes de ativar, foi criado `data/pre-video-migration.sqlite` por backup SQLite. Dados e perfis existentes foram preservados. FFmpeg e ffprobe oficiais do Ubuntu foram instalados localmente em `.venv/video-tools` após a instalação com sudo exigir senha. Não houve alteração dos pacotes do sistema. Essa instalação local é específica desta máquina; o instalador normal continua usando apt/Homebrew nas outras máquinas.

## APIs e interface

As rotas novas ficam sob `/api/video`: status, library/upload/analyze, experiments/start/stop, receiver/start/stop, peer/ready/prepare/finish/complete e exportações. O preview usa `/ws/video/preview/{port}`. Todos reutilizam o token atual, e o WebSocket exige autenticação na primeira mensagem. A lista completa e os formatos de payload estão no [guia](VIDEO_STREAMING.md), seção APIs, e no `/docs` da aplicação.

Na interface, use **Video Streaming** ou **New Experiment → Experiment Type → Video Streaming**. Os componentes novos são VideoStreaming, VideoExecution, VideoResults e LivePreview. Os gráficos usam Plotly existente, inclusive PNG/SVG. Report/PDF utiliza impressão do navegador.

## Como reproduzir em duas máquinas

1. Na máquina B: **Video Streaming → Role: Video Receiver**, endereço `0.0.0.0`, porta `5000`, transporte UDP. Clique **START VIDEO RECEIVER**.
2. Na máquina A: **Video Sender → SELECT VIDEOS**, selecione vários arquivos juntos ou arraste o lote. Aguarde progresso e metadata da biblioteca.
3. Use **Select All**, ajuste ordem com Move Up/Down e remova itens da fila quando necessário.
4. Informe o IP da máquina B e a mesma porta/transporte. Escolha Real-time e **Sequential** para um vídeo após outro.
5. Escolha **Preserve Source** para remux sem bitrate artificial, ou **Controlled Bitrate** para H.264 e o target desejado.
6. Para nomes correlacionados e métricas RX na origem, abra Receiver Peer e informe URL/token do LANCE da máquina B. O Receiver deve estar iniciado. Sem peer, o destino recebe e mostra o vídeo, mas o Sender não presume dados RX e o destino não conhece os nomes originais.
7. Clique **Run Selected Videos / START EXPERIMENT**. A máquina B mostra os quadros realmente recebidos em LIVE VIDEO PREVIEW.
8. Para **Concurrent**, configure no Receiver a quantidade de streams selecionados; as portas são `5000, 5002, 5004…`. Escolha Concurrent no Sender.
9. Abra o experimento em Experiments para tabela por vídeo, agregados e exportações JSON/CSV. Selecione uma sessão para filtrar resultados e baixar Per-Video CSV. Source CSV exige análise temporal anterior ao início.
10. **STOP EXPERIMENT** preserva resultados parciais como ABORTED e avisa o Receiver quando coordenado. **STOP VIDEO RECEIVER** encerra sockets/decoders próprios. O servidor web continua sendo parado pelo script `./lanceMetrics → [3]`.

## Métricas e limites

Source é observado no arquivo, Target é solicitado ao encoder, TX é payload UDP submetido pelo Sender e RX é payload UDP recebido no destino. Bytes/datagramas são contados nos sockets, independentemente de ffprobe, progresso FFmpeg ou preview. Isso não equivale a medição física do fio/NIC.

Em UDP, perda e jitter são N/A. Em RTP, perda usa sequências observadas e jitter usa interarrival RFC3550 no Receiver; pacotes de controle RTCP não entram na contagem de mídia. A observação não identifica perda antes do primeiro/depois do último pacote, nem distingue perda no caminho de descarte no buffer do destino. Scheduling/carga do coletor podem influenciar o jitter em userspace.

RX na origem depende do peer autorizado. Combined Metrics CSV e one-way delay ficam indisponíveis sem sincronização de relógios validada. Preview é visual, até 8 fps e 640×360, sem áudio; seu atraso não mede latência de rede. PSNR/SSIM/VMAF, RTCP e sincronização NTP/chrony/PTP são próximos passos, sem valores simulados. Preserve Source pode rejeitar codecs/container incompatíveis; nesses casos use Controlled Bitrate e consulte o log real. A recepção manual divide sessões por silêncio e pode fragmentar um vídeo após uma interrupção longa.

A validação local não substitui testes nativos em macOS ou em duas máquinas físicas numa rede 5G/6G. O teste de duas instâncias usa serviços e bancos separados na mesma máquina.

## Validação realizada

**66 testes de backend e 6 fluxos de navegador passaram**, com build TypeScript/Vite e FFmpeg/ffprobe reais. O teste de navegador selecionou e enviou 20 arquivos e transmitiu dois streams concorrentes com preview real. A comparação do backup confirmou 55 experimentos e 10 perfis anteriores preservados. A matriz final e os resultados estão em [VALIDATION.md](VALIDATION.md). Os testes existentes foram executados antes e depois. Vídeos pequenos foram gerados temporariamente por FFmpeg; nenhum binário grande de teste foi adicionado ao código.

Evidências: [preview de dois streams recebidos](video-receiver.png), [resultados por vídeo e gráfico](video-results.png).
