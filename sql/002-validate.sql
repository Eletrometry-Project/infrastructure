USE eletrometry;
-- Substituir pelo run_id exibido pelo simulador; nao misturar execucoes.
SET @run_id = 'SUBSTITUA_PELO_RUN_ID';
SELECT cabine_id, tipo, COUNT(*) AS mensagens,
       MIN(coletado_em) AS primeira, MAX(coletado_em) AS ultima
FROM leituras WHERE run_id = @run_id
GROUP BY cabine_id, tipo ORDER BY cabine_id, tipo;
SELECT COUNT(*) AS mensagens,
       COUNT(fase_a) + COUNT(fase_b) + COUNT(fase_c) AS valores_validos
FROM leituras WHERE run_id = @run_id;
SELECT event_id, COUNT(*) AS repeticoes
FROM leituras WHERE run_id = @run_id
GROUP BY event_id HAVING COUNT(*) > 1;
SHOW CREATE TABLE leituras;
