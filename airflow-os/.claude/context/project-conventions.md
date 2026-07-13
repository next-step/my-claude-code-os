# 프로젝트 컨벤션

운영 레포(`prod-airflow`) 기준.

## 코드 위치
- 실제 운영 DAG는 `prod-airflow/dags/` (심링크 → ops repo). 로컬 `dags/`엔 샘플뿐.
- Glob/Grep은 심링크를 기본으로 안 따라감 → `find -L prod-airflow/dags -name "*.py"`로 찾거나 경로를 직접 Read.

## Airflow 3 · TaskFlow
- `from airflow.sdk import dag, task`, `@dag`/`@task`, 파일 끝에서 `dag_fn()` 인스턴스화.

## 네이밍
- dag_id = `<destination>_<schema>_<table>`
	- 예: `doris.game_silver.session` 적재 → `doris_game_silver_session`
- 파일명 ≈ dag_id.

## dbt·airbyte는 손코딩 금지
- dbt DAG는 코드가 아니라 Variable `dbt_metadata_config`(JSON)로 정의
	- 팩토리 `dbt_transformation.py`(+`dbt_lib/`)가 순회해 생성
	- 고칠 땐 코드 아니라 이 변수를
- airbyte도 동일 — Variable `airbyte_metadata_config`

## 재사용
- 적재·날짜·Asset 헬퍼는 `_common/`을 먼저 확인해 재사용
	- 새로 만들지 말 것

## 알림
- 개별 DAG는 email 끔 (`email_on_failure=False`)
	- 실패 알림은 `alert/` DAG + Slack이 담당
