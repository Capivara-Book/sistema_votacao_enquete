# Diagramas de Classes

Os padrões de projeto aparecem em notas e na tabela de rastreabilidade (seção 4).

## 1. Servidor

```mermaid
classDiagram
    direction TB

    class PollType {
        <<enumeration>>
        SINGLE
        MULTIPLE
    }
    class PollStatus {
        <<enumeration>>
        OPEN
        CLOSED
    }
    class Vote {
        <<dataclass>>
        +int poll_id
        +str user
        +tuple options
        +datetime timestamp
    }

    %% ---------- Factory Method ----------
    class PollCreator {
        <<abstract>>
        +create(poll_id, title, options) Poll
        +make_poll(poll_id, title, options)* Poll
    }
    class SinglePollCreator {
        +make_poll(poll_id, title, options) Poll
    }
    class MultiplePollCreator {
        +make_poll(poll_id, title, options) Poll
    }

    %% ---------- Subject / Product ----------
    class Votable {
        <<interface>>
        +vote(user, options)* Vote
    }
    class Poll {
        <<abstract>>
        +int id
        +str title
        +list options
        +PollType type
        +PollStatus status
        +RLock lock
        +attach(observer)
        +detach(observer)
        +notify(vote)
        +has_voted(user) bool
        +is_open() bool
        +close()
        +vote(user, options) Vote
        +validate_choice(options)* void
    }
    class SinglePoll {
        +validate_choice(options) void
    }
    class MultiplePoll {
        +validate_choice(options) void
    }

    %% ---------- Proxy ----------
    class VotingProxy {
        -Poll poll
        +vote(user, options) Vote
        -check_payload(user, options)
        -check_open()
        -check_not_voted(user)
    }

    %% ---------- Observer ----------
    class VoteObserver {
        <<interface>>
        +update(poll, vote)*
    }
    class ResultsCounter {
        -dict counts
        -dict ballots
        +update(poll, vote)
        +results(poll) dict
    }
    class AuditLog {
        -list entries
        +update(poll, vote)
        +entries(poll_id) list
    }

    %% ---------- Aplicação ----------
    class PollRepository {
        -dict polls
        -int last_id
        +next_id() int
        +add(poll)
        +get(poll_id) Poll
        +list() list
    }
    class PollService {
        -PollRepository repository
        -ResultsCounter results_counter
        -AuditLog audit_log
        +create_poll(title, options, poll_type) Poll
        +list_polls() list
        +get_poll(poll_id) Poll
        +vote(poll_id, user, options) Vote
        +results(poll_id) dict
        +close_poll(poll_id) Poll
        +audit(poll_id) list
    }
    class Routes {
        <<blueprint>>
        POST /polls
        GET /polls
        GET /polls/id
        POST /polls/id/votes
        GET /polls/id/results
        POST /polls/id/close
        GET /polls/id/audit
    }

    %% ---------- Erros ----------
    class DomainError {
        <<exception>>
        +int status
        +str message
    }
    class PollNotFound { status 404 }
    class ValidationError { status 400 }
    class InvalidVote { status 422 }
    class Conflict { status 409 }

    PollCreator <|-- SinglePollCreator
    PollCreator <|-- MultiplePollCreator
    SinglePollCreator ..> SinglePoll : cria
    MultiplePollCreator ..> MultiplePoll : cria
    PollCreator ..> Poll : produto

    Votable <|.. Poll
    Votable <|.. VotingProxy
    Poll <|-- SinglePoll
    Poll <|-- MultiplePoll
    VotingProxy --> Poll : delega

    Poll o-- VoteObserver : observers
    VoteObserver <|.. ResultsCounter
    VoteObserver <|.. AuditLog
    Poll "1" *-- "0..*" Vote
    Poll --> PollType
    Poll --> PollStatus

    PollService --> PollRepository
    PollService --> PollCreator : escolhe pelo tipo
    PollService --> VotingProxy : todo voto passa aqui
    PollService --> ResultsCounter
    PollService --> AuditLog
    Routes --> PollService

    DomainError <|-- PollNotFound
    DomainError <|-- ValidationError
    DomainError <|-- InvalidVote
    DomainError <|-- Conflict

    note for PollCreator "FACTORY METHOD (criacional): make_poll() é o método fábrica; cada subclasse devolve o tipo de enquete com sua regra de validação."
    note for VotingProxy "PROXY (estrutural): valida usuário, enquete aberta e voto único antes de delegar ao Poll real."
    note for VoteObserver "OBSERVER (comportamental): Poll notifica ResultsCounter e AuditLog a cada voto aceito."
```

### Fluxo de um voto

```mermaid
sequenceDiagram
    participant R as Routes
    participant S as PollService
    participant X as VotingProxy
    participant P as Poll
    participant C as ResultsCounter
    participant A as AuditLog

    R->>S: vote(poll_id, user, options)
    S->>X: VotingProxy(poll).vote(user, options)
    X->>X: usuário válido, enquete aberta, voto único
    X->>P: vote(user, options)
    P->>P: validate_choice(options)
    P-->>C: update(poll, vote)
    P-->>A: update(poll, vote)
    P-->>X: Vote
    X-->>S: Vote
    S-->>R: Vote (201)
```

### Ordem das verificações no Proxy
1. Usuário válido e formato das opções → senão `ValidationError` (400)
2. Enquete aberta → senão `Conflict` (409)
3. Usuário ainda não votou → senão `Conflict` (409)
4. Regra do tipo (`validate_choice`, dentro do `Poll`) → senão `InvalidVote` (422)

## 2. Contrato da API

| Método | Rota | Corpo | Sucesso | Erros |
|--------|------|-------|---------|-------|
| POST | `/polls` | `{title, options, type}` | 201 enquete | 400 |
| GET | `/polls` | n/a | 200 lista | n/a |
| GET | `/polls/<id>` | n/a | 200 enquete | 404 |
| POST | `/polls/<id>/votes` | `{user, options}` | 201 voto | 400, 404, 409, 422 |
| GET | `/polls/<id>/results` | n/a | 200 resultados | 404 |
| POST | `/polls/<id>/close` | n/a | 200 enquete | 404, 409 |
| GET | `/polls/<id>/audit` | n/a | 200 lista de entradas | 404 |

Formatos JSON:
- Enquete: `{id, title, type, status, options}`
- Resultados: `{poll_id, status, total_votes, results: {opção: contagem}}`
- Voto: `{poll_id, user, options}`
- Auditoria: `[{poll_id, user, options, timestamp}]`
- Erro: `{error: "mensagem"}`

## 3. Cliente

```mermaid
classDiagram
    direction TB

    class ApiError {
        <<exception>>
        +int status
        +str message
    }
    class ApiClient {
        -str base_url
        -Session session
        +list_polls() list
        +create_poll(title, options, poll_type) dict
        +get_poll(poll_id) dict
        +vote(poll_id, user, options) dict
        +results(poll_id) dict
        +close_poll(poll_id) dict
        +audit(poll_id) list
    }
    class ApiTask {
        <<QRunnable>>
        +TaskSignals signals
        +Callable fn
        +Callable on_done
        +Callable on_error
        +result
        +error
        +run()
    }
    class TaskSignals {
        <<QObject>>
        +finished(task)
    }
    class MainWindow {
        <<QMainWindow>>
        -ApiClient api
        -QThreadPool pool
        -QListWidget poll_list
        -VotePanel vote_panel
        -ResultsWidget results_widget
        +refresh_polls()
        +on_poll_selected(row)
        +on_new_poll()
        +on_vote(user, options)
        +on_close_poll()
        +run_async(fn, on_done)
        +is_busy() bool
    }
    class CreatePollDialog {
        <<QDialog>>
        +title_edit
        +options_edit
        +type_combo
        +values() dict
    }
    class VotePanel {
        <<QWidget>>
        +user_edit
        +submit_button
        +submitted(user, options)
        +set_poll(poll)
        +selected_options() list
        +reset()
    }
    class ResultsWidget {
        <<QWidget>>
        +rows
        +show_results(results)
        +clear()
    }

    ApiClient ..> ApiError : lança
    MainWindow --> ApiClient
    MainWindow --> ApiTask : dispara
    ApiTask --> TaskSignals
    ApiTask --> ApiClient : chama
    MainWindow *-- VotePanel
    MainWindow *-- ResultsWidget
    MainWindow ..> CreatePollDialog : abre

    note for ApiTask "Executa as requisições fora da thread da interface (RNF08)."
    note for VotePanel "Mostra radio buttons para single e checkboxes para multiple."
```

O cliente não implementa os três padrões obrigatórios. A comunicação entre
widgets usa signals e slots do Qt, que são o mecanismo nativo de observer do
framework.

## 4. Rastreabilidade dos padrões

| Padrão | Classes | Arquivo | Atende |
|--------|---------|---------|--------|
| Factory Method | `PollCreator`, `SinglePollCreator`, `MultiplePollCreator` | `server/factory.py` | RF05, RF06, CA17 |
| Proxy | `Votable`, `VotingProxy`, `Poll` | `server/proxy.py` | RF07 a RF09, CA18 |
| Observer | `VoteObserver`, `ResultsCounter`, `AuditLog` | `server/observers.py` | RF11, RF12, CA19 |
| Orquestração dos três padrões | `PollService` | `server/service.py` | RF04, RF11, RF12 |
