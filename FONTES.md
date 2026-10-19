# Fontes e adaptação local

- `telemetry/`: https://github.com/Eletrometry-Project/telemetry-simulator
  commit `866a56ea07f48e18773d27288cc20ed97f90f4f1`.
- `consumer/`: https://github.com/Eletrometry-Project/sqs-consumer
  commit `038b257430c7fbad19cf0d42d7353a4f795eb5d3`.

O consumidor permanece igual ao commit. O simulador recebeu a opção local `--temperatura-intervalo`, mantendo 30s como padrão avulso. O adaptador EC2 passa 1s; `deploy/patch_simulator.py` aplica a mesma adaptação no bootstrap, verificando hashes. Os adaptadores de instalacao,
servico e verificacao ficam em `deploy/`. Nada foi enviado/alterado nos repositorios remotos.
