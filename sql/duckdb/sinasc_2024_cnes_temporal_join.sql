WITH cnes_any AS (
    SELECT DISTINCT codigo_cnes FROM fact_capacidade
), joined AS (
    SELECT
        CASE
            WHEN s.codigo_estabelecimento IS NULL OR s.codigo_estabelecimento = '' THEN 'missing_cnes_code'
            WHEN NOT regexp_full_match(s.codigo_estabelecimento, '[0-9]{7}') THEN 'invalid_cnes_format'
            WHEN s.data_nascimento IS NULL THEN 'missing_birth_date'
            WHEN f.codigo_cnes IS NOT NULL THEN 'matched_same_competence'
            WHEN a.codigo_cnes IS NOT NULL THEN 'cnes_seen_other_competence'
            ELSE 'not_in_hospital_beds_2024'
        END AS match_status
    FROM sinasc AS s
    LEFT JOIN fact_capacidade AS f
      ON strftime(s.data_nascimento, '%Y%m') = f.competencia
     AND s.codigo_estabelecimento = f.codigo_cnes
    LEFT JOIN cnes_any AS a
      ON s.codigo_estabelecimento = a.codigo_cnes
)
SELECT match_status, COUNT(*) AS registros
FROM joined
GROUP BY 1
ORDER BY registros DESC, match_status
