WITH codes AS (
    SELECT 'residencia' AS tipo_codigo, codigo_municipio_residencia AS codigo_sinasc, COUNT(*) AS registros
    FROM sinasc GROUP BY 2
    UNION ALL
    SELECT 'ocorrencia' AS tipo_codigo, codigo_municipio_nascimento AS codigo_sinasc, COUNT(*) AS registros
    FROM sinasc GROUP BY 2
)
SELECT
    c.tipo_codigo,
    c.codigo_sinasc,
    c.registros,
    CASE
        WHEN d.codigo_ibge IS NOT NULL THEN 'matched'
        WHEN c.codigo_sinasc IS NULL OR c.codigo_sinasc = '' THEN 'missing_code'
        WHEN NOT regexp_full_match(c.codigo_sinasc, '[0-9]{6}') THEN 'invalid_format'
        WHEN u.codigo_uf IS NULL THEN 'unknown_uf'
        ELSE 'municipality_not_in_dtb'
    END AS match_status,
    d.codigo_ibge,
    d.municipio,
    d.codigo_uf,
    d.uf,
    d.nome_uf,
    d.codigo_regiao,
    d.regiao,
    u.codigo_uf AS codigo_uf_prefixo,
    u.uf AS uf_prefixo
FROM codes AS c
LEFT JOIN dim_municipio AS d ON c.codigo_sinasc = d.codigo_sinasc_6
LEFT JOIN dim_estado AS u ON left(c.codigo_sinasc, 2) = u.codigo_uf
ORDER BY c.tipo_codigo, c.registros DESC, c.codigo_sinasc
