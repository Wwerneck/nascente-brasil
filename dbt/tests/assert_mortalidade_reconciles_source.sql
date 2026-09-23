select 1
where (select count(*) from {{ ref('mart_mortalidade_territorial') }})
   <> (select count(*) from {{ source('analytics', 'mortalidade') }})
