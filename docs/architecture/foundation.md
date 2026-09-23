# Fundacao da Arquitetura

O NASCENTE BRASIL sera desenvolvido por fases. A fundacao estabelece os contratos minimos para as proximas etapas:

- configuracao centralizada em `src/nascente_brasil/config.py`;
- logging estruturado em JSON por `src/nascente_brasil/logging_config.py`;
- manifesto de ingestao em `data/metadata/ingestion_manifest.csv`;
- testes automatizados em `tests/`;
- script de validacao operacional em `scripts/validate_phase_1.py`.
- `docker-compose.yml` inicial para PostgreSQL local, a ser exercitado nas fases de banco/Docker.

Nesta fase nao ha ingestao de dados reais. Downloads, conversoes e transformacoes comecam na Fase 2, apos a base estar importavel, testada e documentada.

## Principios

- Dados RAW serao imutaveis.
- Toda fonte devera registrar origem, periodo, checksum e status no manifesto.
- Falhas criticas devem interromper a pipeline e gerar log com contexto.
- Dados grandes nao serao versionados.
