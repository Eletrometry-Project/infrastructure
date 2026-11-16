# Aprendendo transpiladores com o Eletrometry

## 1. O problema antes do nome técnico

O analista conhece a cabine: “temperatura de uma fase acima de 90 por dez segundos é crítica”. O banco entende SQL. Nosso programa faz a tradução entre essas duas formas de escrever a mesma intenção.

Um transpilador traduz código-fonte para código-fonte. Um compilador é uma categoria mais ampla de tradutores; um interpretador executa diretamente a representação do programa. Aqui o resultado é SQL, portanto estamos construindo um transpilador.

Python é a linguagem em que o tradutor foi implementado. ELT é a linguagem de entrada. SQL é a linguagem de saída. AWS é onde esse programa pode rodar — não é uma linguagem.

## 2. Léxico: quais são as peças?

QUANDO TEMPERATURA >= 90 C vira palavras, operador e número. O lexer percorre todo o texto, registra linha/coluna e rejeita qualquer caractere que não reconhece. Ele não apenas procura trechos válidos ignorando o restante.

Token é uma peça com tipo e valor: NUMBER/90, OP/>=, WORD/TEMPERATURA.

Experimento: use ! no lugar de >=. O lexer não reconhece esse operador e informa sua posição.

## 3. Sintaxe: como montar as peças?

O parser exige uma sequência definida:
REGRA nome CABINE identificador FASE fase QUANDO grandeza operador número unidade DURANTE número SEGUNDOS LACUNA_MAXIMA número SEGUNDOS CLASSIFICAR severidade FIM.

Ele usa descida recursiva no sentido de funções que reconhecem produções; esta gramática simples usa principalmente um laço de regras e uma produção sequencial, sem expressões aninhadas. Não precisamos adicionar recursão artificial.

A gramática simplificada:
programa = regra { regra };
regra = "REGRA" string "CABINE" string "FASE" palavra
        "QUANDO" palavra operador numero palavra
        "DURANTE" numero "SEGUNDOS"
        "LACUNA_MAXIMA" numero "SEGUNDOS"
        "CLASSIFICAR" palavra "FIM";

Experimento: apague FIM. Os tokens continuam reconhecíveis, mas a montagem fica incompleta.

## 4. AST: qual é a intenção organizada?

A árvore sintática abstrata elimina espaços e comentários e preserva os campos importantes. Na v1, programa é uma lista de nós Rule. Cada Rule contém cabine, fase, condição, duração, lacuna e classificação. Uma AST não precisa ser uma grande árvore desenhada; uma linguagem simples pode ter nós rasos.

Use --explain e encontre ast em compilacao.json. Compare seus campos com a regra original.

## 5. Semântica: a frase faz sentido?

TEMPERATURA >= 90 A é reconhecível e está na estrutura correta. Mas a unidade A pertence à corrente, não à temperatura. É um erro de significado.

A mesma etapa verifica cabine cadastrada, fase, classificação, duração e nomes duplicados. Erros semânticos apontam o início da regra; erros léxicos/sintáticos apontam o token correspondente. Melhorar a precisão semântica por campo é uma evolução possível.

## 6. Geração de SQL: como expressar o mesmo significado?

O gerador usa somente operações conhecidas e campos fixos. Não executa eval nem aceita SQL livre.

As CTEs:
- raw: seleciona cabine, grandeza e janela.
- phases: transforma colunas A/B/C em linhas por fase.
- samples: consolida leituras simultâneas.
- previous: obtém a leitura anterior da mesma fase com LAG.
- boundaries: encontra o começo de uma sequência.
- grouped: numera as sequências.
- runs: calcula o primeiro instante de cada sequência.
- SELECT final: mantém sequências com confirmação temporal.

Veja um exemplo a cada 5 segundos:
tempo 0: 95 C; tempo 5: 96 C; tempo 10: 94 C.
A condição ficou observada por 10 segundos, com lacunas permitidas: confirma no tempo 10.

Se a leitura no tempo 5 for 40 C, a sequência é interrompida.
Se a próxima leitura depois do tempo 5 só vier no tempo 11, uma lacuna máxima de 5 segundos também interrompe.
Se A estiver alta no tempo 0 e B estiver alta depois, elas não se juntam.

Isso não prova fisicamente o que ocorreu entre amostras: é uma interpretação explícita dos dados observados.

## 7. Execução e implantação são outros assuntos

O compilador termina ao gerar SQL. O MySQL executa a consulta. O Grafana apresenta o resultado. A Lambda executa o compilador quando o S3 entrega um evento. Publicar uma regra é decidir que uma saída validada deve passar a ser usada.

Misturar essas etapas torna difícil testar ou explicar o sistema. Nosso núcleo roda sem AWS e é o mesmo importado pela Lambda.

## 8. Exercícios com respostas

1. Troque 90 C por 90 A. Resultado: erro semântico.
2. Apague CLASSIFICAR. Resultado: erro sintático.
3. Escreva @ no meio da regra. Resultado: erro léxico.
4. Troque FASE QUALQUER por FASE B. SQL deve selecionar apenas B.
5. Use DURANTE 0 SEGUNDOS. Uma amostra válida pode confirmar.
6. Envie duas regras com mesmo nome. Resultado: erro semântico.
7. Aumente a lacuna de 5 para 30. Você passa a aceitar espaços maiores entre leituras; não é apenas uma mudança visual.
8. Compile sem executar SQL. Nenhum alerta real é consultado: só o código é produzido.

## 9. Como apresentar

“Criamos uma linguagem específica para regras de monitoramento. Nosso lexer transforma o texto em tokens, o parser constrói uma representação da regra, a análise semântica verifica significado e o gerador produz SQL MySQL 8. Testamos o código gerado com medições controladas. O mesmo núcleo pode executar localmente ou numa Lambda acionada por arquivos versionados no S3.”

Dominar esses passos, justificar as regras temporais e saber diferenciar erro de linguagem de falha da AWS é uma base prática sólida. As próximas etapas de estudo são expressões booleanas, precedência, ASTs aninhadas, recuperação de múltiplos erros e otimização.
