# Testes de aceite na conta

Executar depois do plano revisado e da configuração da aplicação. Guardar hora, run_id, contagens e resultado de cada teste. Não incluir senhas ou tokens na evidência.

| Teste | Como verificar | Critério de aceite |
|---|---|---|
| Conta e plano | `aws sts get-caller-identity`, revisão do plan | Conta/região certas; primeiro plano contém criações, sem importações/exclusões/substituições. |
| Perfil EC2 | Conferir instance profile e logs da aplicação | Consumo usa credenciais da role; nenhuma chave estática instalada. |
| IoT→SQS | Publicar com simulador, observar fila e métricas da regra | Publicação aceita e mensagens entregues; aceite no IoT isoladamente não prova entrega. |
| MySQL/TLS | Logs e sessão de verificação na EC2 | Certificado e hostname verificados; usuário da aplicação alcança o RDS privado. |
| 120 segundos | Três cabines, execução sem falhas injetadas; usar `sql/002-validate.sql` | Referência do MD: até 360 mensagens de corrente e 12 de temperatura, 372 linhas, 1.116 valores se todos válidos. Comparar com total realmente emitido/aceito pelo simulador, não apenas duração do relógio. |
| Idempotência real | Republicar uma mensagem válida com mesmo event_id de um run de teste | Continua uma linha para aquele event_id; mensagem repetida é confirmada. |
| Falha de DB | Em teste controlado, interromper acesso ao banco e depois restaurar | Mensagem não é apagada sem commit; volta ao consumo ou chega à DLQ conforme número de tentativas. Não usar parada destrutiva do RDS. |
| Mensagem inválida | Publicar uma mensagem de teste identificada que não siga o contrato | Mensagens válidas continuam; inválida chega à DLQ após recebimentos configurados. Com visibilidade 120 s, aguardar vários ciclos. |
| Reinício | `sudo systemctl restart eletrometry-consumer` | Serviço volta a consumir sem pedir senha; reentregas não duplicam leituras. |
| Reboot | Reiniciar EC2 em janela de teste e acompanhar | Unit habilitada volta a operar; pode haver mudança de IPv4 público. |
| Estabilidade do Terraform | Após mudanças pendentes do RDS concluírem, fixar versões e rodar novo plan | Ausência de alterações inesperadas. Mudanças automáticas de versão precisam de revisão. |

Não executar teste de falha em uma apresentação ou durante medições importantes. Usar um run_id próprio e restaurar o acesso logo após a observação. Investigar a DLQ antes de reenviar; não executar purge. Métricas SQS são aproximadas, não substituem a contagem por run_id no banco.

## Diagnóstico

- **Credenciais expiradas no computador:** reiniciar/renovar sessão do Learner Lab e atualizar o perfil local. Não copiar esse perfil para a EC2.
- **AccessDenied IoT/SQS:** conferir a ação, recurso/ARN, confiança da role e permissões permitidas pelo laboratório; não criar política global como atalho.
- **Timeout no SQS:** verificar rota de saída ou endpoint, DNS e SG. RDS acessível não comprova acesso à API do SQS.
- **Timeout MySQL:** conferir endpoint, VPC, rota, SG e porta. Se usam o mesmo SG, conferir autorreferência para 3306.
- **Access denied MySQL:** conferir usuário/senha, `REQUIRE SSL` e privilégios; `ON DUPLICATE KEY UPDATE` precisa de UPDATE(event_id) além de INSERT/SELECT.
- **Serviço skipped:** verificar se `setup_database.py` instalou o arquivo de credencial. Não editar user-data para inserir a senha.
- **Falha TLS:** atualizar CA oficial, conferir endpoint real (não IP) e horário; não desligar verificação de certificado.
- **DLQ com mensagens válidas:** corrigir banco/contrato antes do redrive controlado. O envio de volta não é automático neste pacote.
- **Contagem menor:** filtrar pelo run_id correto, considerar falhas simuladas, mensagens em voo, DLQ e consumidores antigos competindo.
