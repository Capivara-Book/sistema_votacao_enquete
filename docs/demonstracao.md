# Roteiro de Demonstração Final

Duração estimada: 8 a 10 minutos. Cada passo traz o resultado esperado e a
condição de aceitação (CA) que ele comprova.

## Preparação

```bash
pip install -r requirements.txt
pytest                       # todos os testes devem passar (CA24)
python -m server.run         # terminal 1
python -m client.main        # terminal 2
```

Esperado: janela "Sistema de Votação" vazia, com "Selecione uma enquete" (CA20).

## Roteiro

| # | Ação | Resultado esperado | CA |
|---|------|--------------------|----|
| 1 | Clicar em **Nova enquete**. Título "Almoço?", opções (uma por linha) "Pizza", "Sushi", "Salada", tipo **Múltipla escolha**. OK | Enquete aparece na lista, já selecionada, com checkboxes e "Total de votos: 0"; barra de status "Enquete criada" | CA02, CA20 |
| 2 | **Nova enquete**: título "Café?", opções "Sim" e "Não", tipo **Escolha única**. OK | Segunda enquete na lista; painel com radio buttons | CA01 |
| 3 | **Nova enquete** com título vazio e OK | Banner vermelho "Título é obrigatório"; nada é criado | CA03 |
| 4 | Selecionar "Almoço?". Nome "Ana", marcar Pizza e Sushi, **Votar** | "Voto registrado"; barras Pizza 1, Sushi 1, Salada 0; Total de votos: 1; campos limpos | CA08, CA21 |
| 5 | Nome "Bia", marcar apenas Sushi, **Votar** | Pizza 1, Sushi 2, Salada 0; Total de votos: 2 | CA13 |
| 6 | Nome "ana" (minúsculo), marcar Salada, **Votar** | Banner "Usuário já votou nesta enquete"; resultados inalterados | CA10 |
| 7 | Nome vazio, marcar Pizza, **Votar** | Banner "Usuário é obrigatório" | CA11 |
| 8 | Selecionar "Café?". Nome "Ana", sem marcar nada, **Votar** | Banner "Enquete de escolha única exige exatamente uma opção" | CA07 |
| 9 | Marcar "Sim" e **Votar** | Sim 1, Não 0; Total de votos: 1 | CA06 |
| 10 | Clicar em **Encerrar enquete**, confirmar com **Sim** | Item da lista muda para "encerrada"; painel mostra "Enquete encerrada: votação indisponível", controles desabilitados; resultados continuam visíveis | CA14 |
| 11 | Ver o botão **Encerrar enquete** | Desabilitado (não é possível encerrar de novo pela interface) | CA15 |
| 12 | Clicar em **Atualizar** | Lista recarregada; seleção preservada | CA04 |
| 13 | Em um terceiro terminal: `curl http://127.0.0.1:5050/polls/1/audit` | JSON com as entradas de Ana e Bia, em ordem, com `poll_id`, `user`, `options` e `timestamp`; os votos rejeitados dos passos 6 e 7 não aparecem | CA16 |
| 14 | `curl -X POST http://127.0.0.1:5050/polls/2/close` | HTTP 409 `{"error": "Enquete já está encerrada"}` | CA15 |
| 15 | `curl http://127.0.0.1:5050/polls/999` | HTTP 404 `{"error": "Enquete 999 não encontrada"}` | CA05 |
| 16 | Parar o servidor (Ctrl+C) e clicar em **Atualizar** | Banner "Não foi possível conectar ao servidor em http://127.0.0.1:5050..."; a janela continua responsiva | CA22 |
| 17 | Subir o servidor de novo e clicar em **Atualizar** | Banner some; a lista volta vazia (dados em memória) | RNF03 |

## Pontos a destacar na apresentação

1. **Factory Method:** abrir `server/factory.py`. `make_poll()` é o método fábrica e
   cada subclasse devolve a enquete do tipo, com a sua regra de voto
   (passos 1, 2, 8 e 9).
2. **Proxy:** abrir `server/proxy.py`. As verificações de usuário, enquete aberta
   e voto único acontecem antes de o `Poll` real ser chamado (passos 6, 7 e 10).
3. **Observer:** abrir `server/observers.py`. A contagem das barras e o log do
   passo 13 vêm de observers que o `Poll` notifica sem conhecer suas classes.
4. **Testes:** mostrar `pytest -v` e o mapa de arquivos de teste no README.
5. **Documentação:** mostrar `docs/requisitos.md` e `docs/diagramas.md`.
