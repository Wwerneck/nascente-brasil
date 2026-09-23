WITH counts AS (
    SELECT
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
)
SELECT
    nascidos_vivos,
    partos_tipo_conhecido,
    partos_cesareos,
    ROUND(100.0 * partos_cesareos / NULLIF(partos_tipo_conhecido, 0), 2) AS pct_cesareos,
    peso_valido,
    baixo_peso,
    ROUND(100.0 * baixo_peso / NULLIF(peso_valido, 0), 2) AS pct_baixo_peso,
    gestacao_valida,
    prematuros,
    ROUND(100.0 * prematuros / NULLIF(gestacao_valida, 0), 2) AS pct_prematuros,
    prenatal_valido,
    prenatal_7_mais,
    ROUND(100.0 * prenatal_7_mais / NULLIF(prenatal_valido, 0), 2) AS pct_prenatal_7_mais
FROM counts
