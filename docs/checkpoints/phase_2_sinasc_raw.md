# Checkpoint - Fase 2 SINASC RAW

Status: CONCLUIDA

Objetivo: obter e validar um arquivo nacional real do SINASC, preservar o RAW
e registrar sua procedencia de forma auditavel.

Implementado:

- ingestao em `src/nascente_brasil/ingestion/sinasc.py` com timeout, retry,
  download em fluxo e arquivo temporario;
- validacao de tamanho, assinatura ZIP, CRC, CSV, colunas basicas e contagem;
- SHA-256 calculado sobre os bytes originais;
- arquivo local imutavel com nome derivado do checksum;
- manifesto com URL, periodo, data, ETag, Last-Modified, tamanho, checksum,
  contagem, fingerprint do header e status;
- deteccao de versao remota sem novo download quando inalterada;
- novo download quando o arquivo local esta ausente apos clone, sem duplicar
  a linha existente no manifesto;
- validacao local independente em `scripts/validate_phase_2.py`.

Fonte: Ministerio da Saude, recurso e detalhes em `docs/sources/sinasc_2024.md`.
Arquivo RAW: `data/raw/sinasc/original/SINASC_2024_csv_27e55de6359e.zip`.
Tamanho: 92.289.354 bytes.
Registros: 2.389.325.
Checksum SHA-256: `27e55de6359e1b1914301dc1d752d78e9535a7a52cc0640931dd94876aca6027`.

Validacoes executadas:

- `.\.venv\Scripts\python.exe -m pytest`: 11 testes aprovados;
- `.\.venv\Scripts\python.exe scripts/ingest_sinasc_raw.py`: download real aprovado;
- `.\.venv\Scripts\python.exe scripts/validate_phase_2.py`: integridade local aprovada;
- segunda execucao da ingestao: `already current`, sem novo download e sem
  nova linha no manifesto;
- `.\.venv\Scripts\python.exe -m pip check`: sem conflitos.

Problema encontrado: rede do sandbox bloqueou a primeira tentativa.
Correcao: execucao autorizada com acesso a rede; download oficial concluido.
Pendencias da Fase 2: nenhuma. Extracao do CSV, tipagem e Silver sao Fase 3.
