SELECT sexo, COUNT(*) AS nascidos_vivos
FROM sinasc
GROUP BY sexo
ORDER BY sexo
