SELECT
    CAST(DATE_TRUNC('month', data_nascimento) AS DATE) AS mes,
    COUNT(*) AS nascidos_vivos,
    COUNT(*) FILTER (WHERE tipo_parto IN ('1', '2')) AS partos_tipo_conhecido,
    COUNT(*) FILTER (WHERE tipo_parto = '2') AS partos_cesareos,
    COUNT(*) FILTER (WHERE peso_nascimento_g BETWEEN 200 AND 7000) AS peso_valido,
    COUNT(*) FILTER (WHERE peso_nascimento_g BETWEEN 200 AND 2499) AS baixo_peso,
    COUNT(*) FILTER (WHERE semanas_gestacao BETWEEN 20 AND 45) AS gestacao_valida,
    COUNT(*) FILTER (WHERE semanas_gestacao BETWEEN 20 AND 36) AS prematuros,
    COUNT(*) FILTER (WHERE consultas_prenatal_numero BETWEEN 0 AND 50) AS prenatal_valido,
    COUNT(*) FILTER (WHERE consultas_prenatal_numero BETWEEN 7 AND 50) AS prenatal_7_mais
FROM sinasc
GROUP BY 1
ORDER BY 1
