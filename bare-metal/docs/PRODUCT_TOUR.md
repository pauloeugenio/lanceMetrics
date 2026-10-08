# Product Tour integrado

O LANCE Metrics usa Driver.js 1.9.0, instalado e fixado no package-lock. React 19, TypeScript e Vite carregam a biblioteca e os estilos localmente: não há CDN, serviços externos ou acesso à rede em runtime.

## Experiência

Após o primeiro carregamento bem-sucedido da aplicação e da autenticação opcional, a visão geral aparece automaticamente. Suas dez etapas apresentam Dashboard, novos experimentos, servidor iperf3, vídeo, perfis, histórico, relatórios, sistema e Ajuda. O tour não inicia/paralisa testes, transmite dados nem altera configurações.

**Ajuda**, no cabeçalho, permanece disponível no desktop e no celular. Seu menu oferece **Tutorial desta página** e **Visão geral da aplicação**. O guia contextual usa a página e o papel de vídeo atuais; não troca papéis ou páginas para demonstrar controles. Para aprender o cliente, selecione esse papel e reinicie o tutorial da página. Player e métricas ao vivo entram nas etapas quando existem na tela.

Botões: Anterior, Próximo, Pular tutorial e Concluir tutorial, com progresso. Esc e o botão de fechar registram uma decisão de pular. Setas navegam pelas etapas e Tab circula entre os controles; o foco volta ao botão de ajuda/elemento de origem. O overlay não avança nem fecha por um clique acidental no fundo. Controles destacados ficam protegidos de ações acidentais durante a explicação. Preferência por movimento reduzido desativa as animações.

A interface atual usa tema claro com navegação escura, sem seletor de dark mode. O tutorial respeita essa aparência. Estilos para `data-theme="dark"` ou `.dark` estão preparados caso um tema escuro seja introduzido; não há novo controle de tema.

## Persistência

`localStorage` registra status (`completed` ou `skipped`) e data para cada tour. A chave é `lance.metrics.tour.v1:<identidade>:<tour>`. A identidade é `guest` no modo sem autenticação ou uma impressão do token no modo autenticado; a credencial não é persistida. Web Crypto usa SHA-256; HTTP em LAN sem Web Crypto usa uma impressão opaca determinística. O servidor usa uma credencial compartilhada, não contas individuais: a separação acompanha as credenciais que efetivamente existem. Cada origem/porta e perfil de navegador têm armazenamento próprio.

Concluir ou pular a visão geral impede sua repetição automática. Os tours contextuais são manuais e podem ser repetidos sem apagar preferências. Falha do armazenamento mantém o tour funcional com memória da visita; não é possível persistir entre recargas se o navegador bloquear localStorage. A versão da chave é explícita: não aumentá-la em atualizações rotineiras evita reiniciar o onboarding dos usuários antigos.

## Arquivos e extensão

- `frontend/src/tour/steps.ts`: textos, definições da visão geral e registro `pageTours`.
- `useProductTour.ts`: espera pelo carregamento, execução, persistência de resultado, tratamento de elementos ausentes, limpeza em troca de página/autenticação e restauração do foco.
- `persistence.ts`: separação por identidade sem armazenar token.
- `TourHelp.tsx`: menu de ajuda acessível.
- `tour.css`: aparência, responsividade e movimento reduzido.
- `main.tsx` e `VideoStreaming.tsx`: anchors `data-tour`, hook e botão de ajuda; regras de negócio não são alteradas.

Para acrescentar uma etapa:

1. No componente real, coloque `data-tour="minha-funcionalidade"` no controle ou painel apropriado.
2. Em `steps.ts`, adicione `step('minha-funcionalidade', 'Título', 'Explicação')` ao tour correspondente, em ordem didática.
3. Para uma nova página, registre uma definição em `pageTours` com a mesma chave usada pelo estado de navegação do App e um ID estável.
4. Teste o elemento vazio, oculto ou ainda ausente e a visualização móvel. Não use CSS de posição, ações automáticas destrutivas ou conteúdo HTML vindo de dados externos.

Elementos ocultos/ausentes são omitidos na montagem. Etapas já registradas aguardam até 600 ms se seu elemento desaparecer antes da navegação; se continuar ausente, Driver.js pula a etapa. A remoção/ocultação do alvo atual avança ou encerra o tour. Mudança de página ou identidade encerra o overlay. A biblioteca reposiciona os popovers ao rolar/redimensionar.

## Validação

`product-tour.spec.ts` verifica primeira visita, voltar/avançar, pular/concluir, recarga, reinício, tours por módulo, responsividade, movimento reduzido, teclado, alvo removido, troca de página, identidades e armazenamento bloqueado. Os testes operacionais existentes dispensam o onboarding por seu botão real via `onboarding-helper.ts` para continuar focados nos fluxos originais.

```bash
npm run build --prefix frontend
cd frontend
npx playwright test product-tour.spec.ts auth-mode.spec.ts video-player.spec.ts
```

Para a suíte operacional contra backend de teste isolado, configure `LANCE_TEST_BASE_URL` e `LANCE_TEST_TOKEN_FILE`. Sem essas variáveis, os testes preservam seus caminhos anteriores. O teste opcional `video-network.spec.ts` exige os dois containers descritos nele e `LANCE_VIDEO_NETWORK_TEST=1`.
