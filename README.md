# Bot Resenhudo

Bot de Discord em Python com comandos de barra, embeds, economia e RPG político com dados salvos em JSON.

## Requisitos

- Python 3.10 ou superior
- Uma aplicação e um bot criados no [Discord Developer Portal](https://discord.com/developers/applications)

## Instalação

No PowerShell, dentro desta pasta:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Preencha TOKEN= no arquivo .env
python bot.py
```

No Developer Portal, habilite o bot e convide-o ao servidor com os escopos `bot` e `applications.commands`. A permissão `Send Messages` é suficiente para as respostas públicas dos comandos. Não compartilhe o token nem o envie para o Git.

Os comandos globais podem levar alguns minutos para aparecer depois da primeira sincronização.

## Comandos

- `/menu`: abre a central interativa com carteira, loja, PIX, profissões, hospital e ajuda.
- `/cargo`: sorteia cargo corporativo e adiciona a recompensa ao saldo.
- `/politica`: sorteia cargo político e adiciona a recompensa ao saldo.
- `/partido`: sorteia a filiação partidária, sem recompensa.
- `/alinhamento`: sorteia o alinhamento da alma, sem recompensa.
- `/carteira`: consulta o saldo acumulado.
- `/folha`: consulta os salários dos cargos que você tem no servidor, do contrato profissional ativo e a previsão do próximo depósito automático.
- `/sincronizar_cargos`: administrador aplica no servidor os cargos corporativo, político e partidário salvos no perfil de um membro.
- `/campanha`: durante uma eleição aberta, permite registrar candidatura (com partido), publicar até 3 propostas, organizar eventos e consultar o painel eleitoral.
- `/noticias`: mostra os últimos acontecimentos registrados no RPG.
- `/eleicao`: a administração abre e encerra as eleições; a popularidade da campanha desempata candidaturas com o mesmo número de votos.
- `/rachadinha`: políticos podem contratar, consultar ou encerrar assessores; qualquer membro pode denunciar um contrato ativo.
- `/lavajato denunciar`: registra uma denúncia; Polícia (com contrato Policial ativo ou cargo policial no servidor), STF/administração podem investigar cada caso uma vez a cada 6 horas por investigador. `/lavajato operacao` exige pelo menos 2 provas e continua exclusiva do STF/administração; `/lavajato painel` mostra os casos em aberto.
- `/petrolao denunciar` e `/petrolao balanco`: registram denúncias sobre a estatal e mostram seu caixa, preço de referência, acionistas e casos abertos.
- `/emprego profissao`: trabalhadores podem assinar contrato como Guarda, Mecânico, Advogado, Médico ou Policial. A profissão e cada cargo salarial no servidor são pagos automaticamente a cada 48 horas; `/emprego pedir_demissao` encerra sem multa e `/emprego quebrar_contrato` desconta 10% do saldo positivo.
- Crimes tentados ou concluídos pelo `/crime` criam ocorrências investigáveis. Policiais com contrato ativo ou cargo policial no servidor podem usar `/lavajato investigar`; operações e julgamentos seguem restritos ao STF/administração.

Na loja e na tela de profissões, selecione uma opção e confirme. O PIX permite selecionar o destinatário e informar o valor. Os comandos de barra existentes continuam disponíveis; os sorteios de cargo e política não mudaram.

Não existe saque manual de salário: a folha deposita automaticamente a cada 48 horas. Os pagamentos de cargos diferentes se acumulam; uma profissão também é paga quando há contrato ativo. Use `/folha` para conferir sua estimativa. O primeiro pagamento acontece 48 horas após a inicialização da folha.

Eventos de campanha podem ser realizados uma vez a cada 12 horas: comícios custam R$ 1.000, voluntariado custa R$ 250 e debates são gratuitos. Cada evento aumenta a popularidade até o limite de 100. O arquivo `dados_bot.json` guarda os dados entre reinicializações locais; em hospedagens como Render, configure armazenamento persistente para não perder esse arquivo em novos deploys.

Ao atribuir cargos, o bot reutiliza os existentes mesmo quando seus nomes têm emojis ou enfeites; se não encontrar um equivalente, cria o cargo necessário. Isso exige a permissão `Manage Roles` e que o cargo mais alto do bot fique acima dos cargos gerenciados.

As denúncias, investigações e operações são mecânicas fictícias do RPG. Uma operação autorizada confisca metade dos saldos e envia o alvo à Papuda por 30 minutos; o STF pode julgá-lo depois.

As repetições nas listas de sorteio definem os pesos relativos das opções. Os GIFs são carregados de URLs externas do GIPHY.