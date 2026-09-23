select 1
where (select count(*) from {{ ref('mart_nascimentos_territoriais') }})
   <> (select count(*) from {{ source('analytics', 'nascimentos') }})
