# 스케줄

## cron
- 5-field cron 문자열. 모듈 상단 상수 `SCHEDULE`로 뺀다. 값은 `@dag(schedule=...)`로 전달.

## catchup · max_active_runs
- `catchup=False` 기본. 순차 백필이 필요한 시계열 적재만 `True`.
- `max_active_runs` 명시: 직렬 적재는 1, 백필 허용은 3.

## CronPartitionTimetable (cron 소스 적재 표준)
- cron 기반 소스 적재는 단순 cron 대신:
	`CronPartitionTimetable(SCHEDULE, timezone="Asia/Seoul", key_format="%Y-%m-%d", run_offset=cron_run_offset(SCHEDULE, N_DAYS_AGO))`
- run마다 `partition_key`=처리날짜를 고정. `N_DAYS_AGO`(모듈 상수)로 지연 데이터 보정.

## Asset(데이터셋) 스케줄
- 시간이 아니라 업스트림 데이터가 준비되면 트리거: `schedule=[<ASSET>]`.
- dbt의 asset 스케줄은 팩토리가 처리한다.
