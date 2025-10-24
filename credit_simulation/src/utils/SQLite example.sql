-- SQLite
--SELECT * FROM credit_fact_history where DPD_bucket != '0' limit 10;
select * from credit_fact_history where loan_id = 1 and mob > 13 limit 10;