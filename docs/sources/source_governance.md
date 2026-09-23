# Governanca das Fontes

Cada arquivo ingerido deve ser registrado em `data/metadata/ingestion_manifest.csv` com os campos:

- `source_name`;
- `organization`;
- `dataset_name`;
- `source_url`;
- `download_url`;
- `reference_period`;
- `extraction_date`;
- `file_format`;
- `file_name`;
- `file_size_bytes`;
- `checksum`;
- `records`;
- `schema_version`;
- `ingestion_status`;
- `processing_status`.
- `source_etag`;
- `source_last_modified`.

Um HTTP 200 nao sera aceito como prova suficiente de download correto. Validacoes de extensao, tamanho, abertura, conteudo esperado e checksum serao obrigatorias nas fases de ingestao.

O ETag e usado para verificar se a versao remota mudou; ele nao substitui o
checksum SHA-256 calculado sobre o arquivo baixado.
