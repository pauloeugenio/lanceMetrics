/** Texts and stable anchors only; tours never execute application actions. */
export type TourStep = {target:string; title:string; description:string};
export type TourDefinition = {id:string; label:string; steps:TourStep[]};
const step=(target:string,title:string,description:string):TourStep=>({target,title,description});
export const tourText={next:'Próximo',previous:'Anterior',skip:'Pular tutorial',done:'Concluir tutorial',progress:'Etapa {{current}} de {{total}}',close:'Pular tutorial e fechar',help:'Ajuda',page:'Tutorial desta página',overview:'Visão geral da aplicação'};
export const overview:TourDefinition={id:'overview',label:'Visão geral',steps:[
 step('page-title','Bem-vindo ao LANCE Metrics','Este guia apresenta os caminhos para medir tráfego de rede, transmitir vídeos e consultar resultados. Use Próximo e Anterior; saia quando quiser com Pular tutorial ou Esc.'),
 step('nav-dashboard','Dashboard: seu ponto de partida','Consulte o estado da aplicação, os experimentos ativos, as interfaces detectadas e os resultados recentes.'),
 step('nav-new-experiment','Crie um experimento','Configure um teste TCP/UDP com iperf3, escolha um perfil de tráfego ou use a transmissão de vídeo.'),
 step('nav-server','Receba testes de rede','Este módulo inicia o servidor iperf3 na máquina de destino. Ele é separado do receptor de vídeo.'),
 step('nav-video-streaming','Transmita e assista a vídeos','A mesma aplicação pode enviar vídeo como servidor ou recebê-lo como cliente. Prepare o cliente antes de iniciar o envio.'),
 step('nav-traffic-profiles','Reproduza variações de tráfego','Crie ou importe perfis com estágios de duração e banda diferentes. Salve um perfil antes de executá-lo.'),
 step('nav-experiments','Consulte o histórico','Busque experimentos, abra seus resultados e consulte configuração, métricas e evidências. Excluir um experimento remove seus resultados.'),
 step('nav-reports','Exporte os resultados','Selecione um experimento para baixar CSV/JSON, exportar gráficos e imprimir o relatório em PDF pelo navegador.'),
 step('nav-system','Confira o ambiente','Veja informações da máquina e instruções para controlar o serviço pelo terminal. Fechar o navegador não encerra o backend.'),
 step('help','Ajuda sempre à mão','Abra Ajuda no cabeçalho para repetir esta visão geral ou seguir o tutorial da página atual. Nenhum teste foi iniciado por este guia.'),
]};
const videoSteps=[
 step('video-role','Escolha servidor ou cliente','Servidor envia vídeo; cliente recebe e exibe o fluxo. Servidor + cliente permite testar na mesma instância. Este guia respeita o papel que você selecionou.'),
 step('video-upload','Carregue os vídeos','Selecione arquivos ou arraste-os para a biblioteca. O upload prepara a mídia para os experimentos, sem iniciar a transmissão.'),
 step('video-library','Selecione os arquivos','Marque os vídeos que deseja executar. A tabela mostra duração, resolução, codec e bitrate; a análise temporal calcula o bitrate ao longo do conteúdo.'),
 step('video-queue','Organize a fila','Ajuste a ordem e mantenha selecionados os vídeos desejados. Remover da fila não exclui o arquivo da biblioteca.'),
 step('video-send-config','Configure o envio','Informe o IP/DNS do cliente, porta e transporte. RTP permite medir perda e jitter. Real-time acompanha a duração do vídeo; Controlled Bitrate libera resolução, FPS e outros ajustes do encoder.'),
 step('video-peer','Associe as métricas do cliente','Informe a URL HTTP do cliente para preparar sessões e recuperar RX ao finalizar cada vídeo. Token só é necessário quando a autenticação estiver ativada no cliente.'),
 step('video-run','Inicie quando estiver pronto','Primeiro inicie o receptor no destino. Depois use este botão para transmitir os vídeos selecionados. O tutorial apenas explica o botão e não inicia o experimento.'),
 step('video-receive-config','Prepare a recepção','Em Docker, escute em 0.0.0.0. Porta base, transporte e quantidade de streams precisam corresponder ao servidor e às portas disponíveis na rede.'),
 step('video-receive-actions','Inicie o cliente antes do servidor','START VIDEO RECEIVER deixa o cliente aguardando vídeo; STOP VIDEO RECEIVER encerra a escuta. O guia não aciona esses controles.'),
 step('video-live-metrics','Acompanhe o tráfego recebido','Confira vazão, bytes e pacotes. Perda e jitter dependem de RTP; métricas indisponíveis permanecem N/A.'),
 step('video-player','Assista ao fluxo recebido','Play retorna ao vivo; Pausar congela apenas a imagem, mantendo transmissão e medições. O preview atual é de até 8 FPS e sem áudio. Tela cheia amplia a visualização.'),
];
export const pageTours:Record<string,TourDefinition>={
 Dashboard:{id:'dashboard',label:'Dashboard',steps:[
  step('dashboard-intro','Comece pelo Dashboard','Este painel reúne o estado da aplicação e os caminhos para configurar um novo experimento.'),
  step('dashboard-status','Verifique o estado','Veja a versão, a disponibilidade do iperf3, o estado do servidor e a quantidade de experimentos registrados.'),
  step('dashboard-active','Acompanhe execuções','Os testes em andamento aparecem aqui. Abra os detalhes para acompanhar métricas; interrompa somente quando desejar encerrar um teste real.'),
  step('dashboard-interfaces','Identifique a rede','Consulte os endereços detectados nesta máquina. Em Docker, as interfaces pertencem ao namespace do container.'),
  step('dashboard-quick-actions','Prepare servidor e perfis','Estes atalhos abrem o servidor iperf3 e o editor de perfis de tráfego.'),
  step('experiment-table','Abra um resultado','Clique em uma linha para consultar o experimento. Um histórico vazio indica que ainda não há testes registrados.'),
 ]},
 'New Experiment':{id:'new-experiment',label:'Novo experimento',steps:[
  step('experiment-type','Escolha o tipo de teste','Tráfego sintético usa iperf3; Traffic Profile aplica um perfil salvo; Video Streaming abre a configuração de vídeo. Dataset Replay ainda está indisponível.'),
  step('experiment-config','Configure destino e tráfego','Informe o endereço do servidor, porta, protocolo e duração. No UDP, a banda configurada vale para cada stream paralelo. Reverse mode faz o servidor enviar.'),
  step('experiment-start','Execute o teste','Prepare o servidor de destino antes de iniciar. O teste gera tráfego real e registra resultados; este tutorial não executa essa ação.'),
  ...videoSteps,
 ]},
 Server:{id:'server',label:'Servidor iperf3',steps:[
  step('iperf-server-config','Configure o servidor iperf3','Defina o endereço de escuta e a porta para receber testes TCP/UDP. O servidor de vídeo é configurado em Video Streaming.'),
  step('iperf-server-actions','Controle a escuta','START SERVER inicia a recepção; STOP SERVER encerra o servidor iperf3. Client mode abre a configuração de um novo experimento.'),
  step('iperf-server-output','Consulte as evidências','O log mostra o resultado observado no destino. Versões sem JSON streaming disponibilizam os dados estruturados ao final de cada sessão.'),
 ]},
 'Video Streaming':{id:'video',label:'Transmissão de vídeo',steps:videoSteps},
 'Traffic Profiles':{id:'profiles',label:'Perfis de tráfego',steps:[
  step('profile-editor','Crie ou importe um perfil','Defina nome e protocolo ou importe um arquivo JSON. Cada estágio representa uma duração e uma banda alvo.'),
  step('profile-stages','Organize os estágios','Edite duração e banda. Use os controles para mover, duplicar ou excluir estágios. A execução usa sessões iperf3 separadas.'),
  step('profile-actions','Visualize e salve','Adicione estágios, visualize a curva alvo, salve o perfil ou exporte o JSON. Salvar não inicia tráfego.'),
  step('profile-preview','Configure o destino depois de salvar','RUN PROFILE abre o formulário de execução com o perfil salvo. O botão depende de um perfil persistido.'),
  step('profile-saved','Reutilize seus perfis','Abra um perfil salvo para consultar, editar e usar suas etapas em novos testes.'),
 ]},
 Experiments:{id:'experiments',label:'Histórico',steps:[
  step('experiment-filters','Encontre um experimento','Busque por nome, UUID ou destino e filtre por protocolo.'),
  step('experiment-table','Abra os detalhes','Clique em uma linha para ver métricas, configuração, ambiente e exportações do experimento.'),
  step('experiment-selection','Selecione com cuidado','A seleção permite excluir resultados. Testes em execução precisam ser interrompidos antes da exclusão; o tutorial não exclui dados.'),
 ]},
 Reports:{id:'reports',label:'Relatórios',steps:[
  step('experiment-filters','Localize o resultado','Use busca e protocolo para encontrar o experimento que deseja documentar.'),
  step('experiment-table','Selecione um relatório','Abra um resultado para baixar CSV/JSON, salvar gráficos ou imprimir em PDF. Não há relatório disponível sem um experimento registrado.'),
 ]},
 'Experiment details':{id:'results',label:'Resultados do experimento',steps:[
  step('result-summary','Interprete o resultado','Confira estado, configuração e métricas. Valores N/A representam dados indisponíveis; não são medições de zero.'),
  step('result-exports','Exporte as evidências','Baixe dados do experimento e métricas. A opção Report / PDF usa a impressão do navegador.'),
  step('result-sessions','Compare os vídeos','Selecione uma sessão para filtrar métricas e examinar o resultado de cada vídeo.'),
  step('result-charts','Explore as curvas','Os gráficos mostram medições disponíveis; exporte PNG ou SVG. TX e RX podem ter disponibilidade e tempos diferentes.'),
  step('video-player','Veja a recepção local','Durante uma recepção local, o player exibe quadros recebidos. A pausa da imagem não interrompe a transmissão.'),
 ]},
 System:{id:'system',label:'Sistema',steps:[
  step('system-controls','Controle o serviço pelo terminal','Use ./lanceMetrics ou stop-web para encerrar o serviço web. Fechar a aba não encerra o backend.'),
  step('system-info','Confira o ambiente detectado','Consulte sistema operacional, arquitetura, interfaces e capacidades do iperf3. Essas informações também acompanham os registros dos experimentos.'),
 ]},
};
