with `c` as (
	with `a` as (
		select 	`elo`.`end_time` AS `end_time`,
				(sum(`elo`.`elo_rating`) / count(`elo`.`elo_rating`)) AS `average_elo`,
				(SELECT `minutes` FROM `constants` ORDER BY `idconstants` DESC LIMIT 1) AS `minutes`,
				(SELECT `standard_deviations` FROM `constants` ORDER BY `idconstants` DESC LIMIT 1) AS `standard_deviations`
	from `elo`
    group by `elo`.`end_time`
    )
select 	`b`.`idelo` AS `idelo`,
		`b`.`coin` AS `coin`,
        `b`.`start_time` AS `start_time`,
        `b`.`elo_rating` AS `elo_rating`,
        `b`.`end_time` AS `end_time`,
        `a`.`average_elo` AS `average_elo`,
        `a`.`standard_deviations` AS `standard_deviations`,
        sqrt((sum(pow((`b`.`elo_rating` - `a`.`average_elo`),2)) / count(`b`.`end_time`))) AS `std_dev`
from (`elo` `b` join `a` on((`a`.`end_time` = `b`.`end_time`)))
group by `b`.`end_time`
)

select 	`d`.`idelo` AS `idelo`,
		`d`.`coin` AS `coin`,
        `d`.`start_time` AS `start_time`,
        `d`.`elo_rating` AS `elo_rating`,
        `d`.`end_time` AS `end_time`,
        `c`.`average_elo` AS `average_elo`,
        `c`.`std_dev` AS `std_dev`,
(`c`.`average_elo` - (`c`.`standard_deviations` * `c`.`std_dev`)) AS `lower_limit`,
(`c`.`average_elo` + (`c`.`standard_deviations` * `c`.`std_dev`)) AS `upper_limit`
from (`c` join `elo` `d` on((`c`.`end_time` = `d`.`end_time`)))
where `c`.`end_time` = (select `end_time` from `elo` order by `end_time` desc limit 1)
order by `d`.`idelo` desc