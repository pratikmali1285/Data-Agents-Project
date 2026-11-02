-- STAGING: each restaurant with its city name (raw restaurants only have a city_id).

select
    r.restaurant_id,
    r.restaurant_name,
    r.cuisine,
    r.rating,
    c.city_name,
    c.state
from {{ source('raw', 'restaurants') }} r
join {{ source('raw', 'cities') }} c using (city_id)
