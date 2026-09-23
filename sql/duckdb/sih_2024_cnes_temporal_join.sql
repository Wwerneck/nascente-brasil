WITH cnes_any AS (
    SELECT DISTINCT codigo_cnes FROM capacidade
), classified AS (
    SELECT CASE
        WHEN s.codigo_cnes IS NULL OR s.codigo_cnes = '' THEN 'missing_cnes_code'
        WHEN NOT regexp_full_match(s.codigo_cnes, '[0-9]{7}') THEN 'invalid_cnes_format'
        WHEN c.codigo_cnes IS NOT NULL THEN 'matched_same_competence'
        WHEN a.codigo_cnes IS NOT NULL THEN 'cnes_seen_other_competence'
        ELSE 'not_in_hospital_beds_2024'
    END AS match_status
    FROM sih AS s
    LEFT JOIN capacidade AS c
      ON s.competencia = c.competencia AND s.codigo_cnes = c.codigo_cnes
    LEFT JOIN cnes_any AS a ON s.codigo_cnes = a.codigo_cnes
)
SELECT match_status, COUNT(*) AS registros
FROM classified
GROUP BY 1
ORDER BY registros DESC, match_status
