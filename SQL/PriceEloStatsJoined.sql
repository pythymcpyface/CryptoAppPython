with `d` as (
with `c` as (

  with `a` as (
    select  `crypto_db`.`elo`.`end_time` AS `end_time`,
            (sum(`crypto_db`.`elo`.`elo_rating`) / count(`crypto_db`.`elo`.`elo_rating`)) AS `average_elo`,
            `crypto_db`.`constants`.`minutes` AS `minutes`,
            `crypto_db`.`constants`.`standard_deviations` AS `standard_deviations`
    from (`crypto_db`.`elo` join `crypto_db`.`constants`)
    group by `crypto_db`.`elo`.`end_time`
    )
    
  select  `b`.`idelo` AS `idelo`,
          `b`.`coin` AS `coin`,
          `b`.`start_time` AS `start_time`,
          `b`.`elo_rating` AS `elo_rating`,
          `b`.`end_time` AS `end_time`,
          `a`.`average_elo` AS `average_elo`,
          `a`.`standard_deviations` AS `standard_deviations`,
          sqrt((sum(pow((`b`.`elo_rating` - `a`.`average_elo`),2)) / count(`b`.`end_time`))) AS `std_dev`
  from (`crypto_db`.`elo` `b` join `a` on((`a`.`end_time` = `b`.`end_time`)))
  group by `b`.`end_time`
  )

select  `d`.`idelo` AS `idelo`,
        `d`.`coin` AS `coin`,
        `d`.`start_time` AS `start_time`,
        `d`.`elo_rating` AS `elo_rating`,
        `d`.`end_time` AS `end_time`,
        `c`.`average_elo` AS `average_elo`,
        `c`.`std_dev` AS `std_dev`,
        (`c`.`average_elo` - (`c`.`standard_deviations` * `c`.`std_dev`)) AS `lower_limit`,
        (`c`.`average_elo` + (`c`.`standard_deviations` * `c`.`std_dev`)) AS `upper_limit`, 
		(round((unix_timestamp(curtime(4)) * 1000),0) - `d`.`end_time`) / 60000 as `minutes_ago`
from (`c` join `crypto_db`.`elo` `d` on((`c`.`end_time` = `d`.`end_time`)))
order by `d`.`idelo` desc
)

SELECT DISTINCT `coin`,
				`elo_rating`,
				`d`.`end_time`,
				`average_elo`,
				`std_dev`,
				`lower_limit`,
				`upper_limit`, 
				`minutes_ago`,
                `open_price`,
                `close_price`
FROM `d`
INNER JOIN `crypto_db`.`price` `b` ON `d`.`end_time` = `b`.`end_time` + 1
AND SUBSTRING_INDEX(`b`.`pair`, '-', 1) = `d`.`coin`