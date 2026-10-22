# Sistema de Votação para Enquetes — Requisitos

Disciplina: Paradigmas de Programação (CC5AN) · Prof. Alex Carneiro

## 1. Escopo
Aplicação cliente-servidor para criar enquetes, votar e acompanhar resultados.
Servidor Flask (API REST) e cliente desktop Qt. Dados somente em memória,
sem banco de dados, APIs de terceiros ou serviços de nuvem.

## 2. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF01 | Criar enquete informando título, lista de opções e tipo (`single` ou `multiple`). |
| RF02 | Listar todas as enquetes com id, título, tipo e status (aberta/encerrada). |
| RF03 | Consultar os detalhes de uma enquete (título, opções, tipo, status). |
| RF04 | Votar em uma enquete informando o usuário e a(s) opção(ões) escolhida(s). |
| RF05 | Em enquete `single`, aceitar exatamente uma opção por voto. |
| RF06 | Em enquete `multiple`, aceitar uma ou mais opções distintas por voto. |
| RF07 | Rejeitar voto em enquete encerrada. |
| RF08 | Rejeitar voto de usuário inválido (identificador vazio ou fora das regras de RN01). |
| RF09 | Permitir no máximo um voto por usuário em cada enquete. |
| RF10 | Exibir resultados (contagem por opção e total de votos) de uma enquete. |
| RF11 | Atualizar a contagem de resultados a cada novo voto (Observer). |
| RF12 | Registrar log de auditoria de cada voto aceito (Observer) e permitir consultá-lo. |
| RF13 | Encerrar uma enquete; após isso ela não aceita novos votos, mas mantém os resultados. |
| RF14 | O cliente Qt deve oferecer telas/ações para RF01, RF02, RF04, RF10 e RF13. |

## 3. Regras de Negócio

- **RN01 — Usuário válido:** não há autenticação; o usuário é um nome de 1 a 30
  caracteres (após `strip`), sem ser vazio.
- **RN02 — Título:** de 1 a 120 caracteres.
- **RN03 — Opções:** mínimo de 2 e máximo de 10 opções, textos não vazios e sem duplicatas
  (comparação sem diferenciar maiúsculas/minúsculas).
- **RN04 — Tipo:** apenas `single` ou `multiple`.
- **RN05 — Voto único:** o usuário é identificado pelo nome (sem diferenciar maiúsculas/minúsculas).
- **RN06 — Encerramento:** irreversível; encerrar uma enquete já encerrada retorna conflito.

## 4. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF01 | **Execução simples:** `pip install -r requirements.txt` + um comando para o servidor + um para o cliente, sem outras instalações. |
| RNF02 | **Restrições:** sem banco de dados, APIs de terceiros, serviços de nuvem ou IA; apenas Flask, Qt (PySide6) e pytest. |
| RNF03 | **Persistência:** dados em memória; reiniciar o servidor limpa o estado. |
| RNF04 | **Testabilidade:** repositório injetado via `create_app(repository)`, sem estado global. |
| RNF05 | **Arquitetura:** Factory Method, Proxy e Observer claramente identificáveis no código e nos diagramas. |
| RNF06 | **Interoperabilidade:** API REST com JSON; códigos HTTP coerentes (200, 201, 400, 404, 409, 422). |
| RNF07 | **Consistência:** operação de voto atômica por enquete (lock), evitando voto duplicado em requisições concorrentes. |
| RNF08 | **Usabilidade:** o cliente mostra mensagens de erro claras e não trava a interface durante as requisições. |
| RNF09 | **Desempenho:** respostas locais em menos de 500 ms para até 1.000 votos por enquete. |
| RNF10 | **Manutenibilidade:** separação em camadas (rotas, serviço, domínio, repositório); cliente separado em API client e views. |
| RNF11 | **Documentação:** diagramas de classes (Mermaid), requisitos e condições de aceitação versionados em `docs/`. |

## 5. Condições de Aceitação

Formato: Dado / Quando / Então.

### Enquetes
- **CA01** Dado dados válidos, quando crio uma enquete `single`, então recebo 201 com id,
  status `open` e tipo `single`.
- **CA02** Dado dados válidos, quando crio uma enquete `multiple`, então recebo 201 com tipo `multiple`.
- **CA03** Dado título vazio, menos de 2 opções, opções duplicadas ou tipo desconhecido,
  quando crio a enquete, então recebo 400 e nada é criado.
- **CA04** Dado que existem enquetes, quando listo, então recebo todas com id, título, tipo e status.
- **CA05** Dado um id inexistente, quando consulto, voto, vejo resultados ou encerro,
  então recebo 404.

### Votação
- **CA06** Dada uma enquete `single` aberta, quando um usuário vota em uma opção válida,
  então recebo 201 e a contagem dessa opção aumenta em 1.
- **CA07** Dada uma enquete `single`, quando o voto traz 0 ou 2+ opções, então recebo 422 e nada é contabilizado.
- **CA08** Dada uma enquete `multiple`, quando o voto traz 2 opções válidas e distintas,
  então recebo 201 e ambas aumentam em 1.
- **CA09** Dada uma enquete `multiple`, quando o voto traz opção inexistente ou repetida,
  então recebo 422 e nada é contabilizado.
- **CA10** Dado um usuário que já votou, quando tenta votar de novo na mesma enquete,
  então recebo 409 e os resultados não mudam.
- **CA11** Dado usuário vazio ou com mais de 30 caracteres, quando vota, então recebo 400.
- **CA12** Dada uma enquete encerrada, quando alguém vota, então recebo 409.

### Resultados, encerramento e auditoria
- **CA13** Dada uma enquete com votos, quando consulto os resultados, então recebo a contagem por opção
  e o total de votos.
- **CA14** Dada uma enquete aberta, quando a encerro, então o status muda para `closed`
  e os resultados continuam acessíveis.
- **CA15** Dada uma enquete já encerrada, quando tento encerrar novamente, então recebo 409.
- **CA16** Dado cada voto aceito, então o log de auditoria ganha uma entrada com enquete, usuário,
  opções e horário; votos rejeitados não geram entrada.

### Padrões de projeto
- **CA17** O código contém uma fábrica de enquetes que decide a regra de validação pelo tipo (Factory Method).
- **CA18** Todo voto passa pelo proxy antes de chegar à enquete real (Proxy).
- **CA19** A enquete notifica os observers de contagem e de auditoria sem conhecer suas classes
  concretas (Observer).

### Cliente Qt
- **CA20** Com o servidor ativo, o cliente lista as enquetes, cria uma nova e ela aparece na lista.
- **CA21** O cliente envia um voto e mostra os resultados atualizados.
- **CA22** Com o servidor fora do ar ou diante de erro da API, o cliente mostra uma mensagem
  amigável sem encerrar a aplicação.

### Entrega
- **CA23** Em máquina limpa com Python 3.10+, `pip install -r requirements.txt` seguido dos
  comandos do README executa servidor e cliente.
- **CA24** `pytest` passa sem falhas, sem precisar do servidor rodando.
- **CA25** O repositório é público e contém código, testes e a documentação exigida.
