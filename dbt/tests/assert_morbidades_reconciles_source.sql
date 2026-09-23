select 1
where (select count(*) from {{ ref('mart_morbidades_territoriais') }})
   <> (select count(*) from {{ source('analytics', 'morbidades') }})
