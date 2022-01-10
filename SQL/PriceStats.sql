WITH B AS (
	WITH A AS (
		SELECT `pair`,
				`start_time`,
				`end_time`,
				`open_price`,
				`close_price`,
				(SELECT `close_price`
				FROM `crypto_db`.`price`
				WHERE `pair` = "{0}-USDT"
				ORDER BY `end_time` DESC
				LIMIT 1) AS `current_price`
		FROM `crypto_db`.`price`
		WHERE `pair` = "{0}-USDT"
		ORDER BY `end_time` DESC)

	SELECT 	`pair`,
			`start_time`,
			`end_time`,
			`open_price`,
			`close_price` AS `original_price`,
			`current_price`,
			(100 / `close_price`) * (`current_price` - `close_price`) as `price_change_percent`,
			(round((unix_timestamp(curtime(4)) * 1000),0) - `end_time`) / 60000 as `minutes_ago`
	FROM A)

SELECT 	`pair`,
		`start_time`,
		`end_time`,
		`original_price`,
		`current_price`,
        `price_change_percent`,
        `minutes_ago`
FROM B 
WHERE `minutes_ago` <= {1}
ORDER BY `end_time` ASC
LIMIT 1