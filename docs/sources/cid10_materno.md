# CID-10 para morbidades maternas

Fonte RAW oficial: FTP DATASUS, diretorio
`ftp://ftp.datasus.gov.br/dissemin/publicos/SIM/CID10/TABELAS/`.

Arquivos preservados sem alteracao em `data/raw/cid/original/`:

- `CID10.DBF`: 14.257 codigos, 841.389 bytes, SHA-256
  `5c755bcdabc5396cfa1eff2aa3f6189aa7256b01eb10ce6ca890be0dda4dd717`;
- `CIDCAP10.DBF`: 22 capitulos, 1.594 bytes, SHA-256
  `8dea0a2454b775123c92bfa6eef0c4b0a0a9a4656a7d84ae8f7528bf38555684`.

Ambos foram abertos como DBF, validados por tamanho, schema, contagem e
checksum, e registrados no manifesto de ingestao. O capitulo XV da
[CID-10 da OMS](https://iris.who.int/bitstream/handle/10665/246208/9789241549165-V1-eng.pdf?sequence=1)
abrange gravidez, parto e puerperio (`O00-O99`). O catalogo nacional fornece
as descricoes em portugues; a regra que converte codigos em grupos analiticos
e versionada separadamente em `src/nascente_brasil/transformation/maternal_cid.py`.

O endpoint historico `CID10CSV.zip` do DATASUS nao respondeu durante a fase;
nenhum espelho de terceiros foi usado. A fonte escolhida permanece oficial,
local e reproduzivel pelo FTP.
