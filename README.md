# Sistema de Votação para Enquetes

Projeto de Paradigmas de Programação (CC5AN) · Prof. Alex Carneiro

Aplicação cliente-servidor para criar enquetes, votar e acompanhar resultados.
Servidor **Flask** (API REST) e cliente desktop **Qt (PySide6)**. Os dados ficam
em memória: sem banco de dados, APIs de terceiros ou serviços de nuvem.

## Executar

Requer Python 3.10 ou superior.

```bash
pip install -r requirements.txt
python -m server.run      # terminal 1: servidor em http://127.0.0.1:5050
python -m client.main     # terminal 2: interface gráfica
```

Em alguns sistemas o comando é `python3` e `pip3`.

Para apontar o cliente a outro servidor:

```bash
ENQUETES_API_URL=http://192.168.0.10:5050 python -m client.main    # Windows (PowerShell): $env:ENQUETES_API_URL="..."
```

## Testes

```bash
pytest
```

Não é preciso subir o servidor: os testes de cliente iniciam o servidor real em
uma thread, em porta livre, e o Qt roda em modo offscreen (sem janelas).

| Arquivo | O que valida |
|---------|--------------|
| `tests/test_ambiente.py` | Fixtures: isolamento por teste, usuários, espiões do Proxy e do Observer, servidor em thread |
| `tests/server/test_factory.py` | Factory Method: criação por tipo, validação e regra de voto de cada tipo |
| `tests/server/test_proxy.py` | Proxy: usuário válido, enquete aberta, voto único, ordem das verificações, atomicidade |
| `tests/server/test_observers.py` | Observer: notificação, contagem de resultados, log de auditoria |
| `tests/server/test_api.py` | Todos os endpoints e códigos HTTP (CA01 a CA16) |
| `tests/client/test_api_client.py` | `ApiClient` contra o servidor real e cenários de falha de rede |
| `tests/client/test_tasks.py` | Execução assíncrona das chamadas |
| `tests/client/test_views.py` | Telas Qt: fluxos de uso, erros e servidor fora do ar (CA20 a CA22) |

## Padrões de projeto

| Tipo | Padrão | Onde | Papel no sistema |
|------|--------|------|------------------|
| Criacional | **Factory Method** | `server/factory.py` | `PollCreator.make_poll()` é implementado por `SinglePollCreator` e `MultiplePollCreator`, que criam a enquete do tipo certo, cada uma com sua regra de validação de voto |
| Estrutural | **Proxy** | `server/proxy.py` | `VotingProxy` controla o acesso ao voto (usuário válido, enquete aberta, voto único) antes de delegar ao `Poll` real |
| Comportamental | **Observer** | `server/observers.py` | `Poll` notifica `ResultsCounter` (contagem) e `AuditLog` (auditoria) a cada voto aceito |

`server/service.py` une os três: escolhe a fábrica pelo tipo, anexa os observers
a cada enquete criada e faz todo voto passar pelo proxy.

## API REST

| Método | Rota | Corpo | Sucesso | Erros |
|--------|------|-------|---------|-------|
| POST | `/polls` | `{title, options, type}` | 201 | 400 |
| GET | `/polls` | n/a | 200 | n/a |
| GET | `/polls/<id>` | n/a | 200 | 404 |
| POST | `/polls/<id>/votes` | `{user, options}` | 201 | 400, 404, 409, 422 |
| GET | `/polls/<id>/results` | n/a | 200 | 404 |
| POST | `/polls/<id>/close` | n/a | 200 | 404, 409 |
| GET | `/polls/<id>/audit` | n/a | 200 | 404 |

`type` é `single` ou `multiple`. Erros sempre no formato `{"error": "mensagem"}`.

## Estrutura

```
server/    Flask: app.py (create_app), routes.py, service.py, models.py,
           factory.py, proxy.py, observers.py, repository.py, errors.py, run.py
client/    Qt: main.py, api_client.py, tasks.py, views/
tests/     pytest (server/ e client/) e conftest.py
docs/      requisitos.md, diagramas.md, demonstracao.md
```

## Documentação

- [Requisitos funcionais, não funcionais e condições de aceitação](docs/requisitos.md)
- [Diagramas de classes do servidor e do cliente](docs/diagramas.md)
- [Roteiro da demonstração final](docs/demonstracao.md)

## Observações

- **Porta 5050:** evita conflito da porta 5000 com o AirPlay Receiver do macOS.
- **Estado em memória:** reiniciar o servidor apaga todas as enquetes.
- **Linux sem ambiente gráfico (ou contêiner):** o PySide6 pode exigir bibliotecas
  do sistema, por exemplo `sudo apt install libegl1 libgl1 libxkbcommon0`.
- **Sem autenticação:** o usuário é um nome de 1 a 30 caracteres, sem diferenciar
  maiúsculas de minúsculas (regra RN01 e RN05 em `docs/requisitos.md`).
