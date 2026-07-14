# 네이밍

## dag_id
- `<db엔진>_<스키마>_<테이블>` — 최종 적재 대상 기준. 예: `doris_game_silver_session`.
- 한 DAG가 여러 대상을 처리하면 테이블 자리에 그걸 아우르는 공통 이름을 쓴다.
- `idb`는 회사 MariaDB의 별칭 → MariaDB로 적재하면 `idb_` 접두.
- `vpn_`·`alert_`는 예외: 데이터 ETL이 아니라 크론잡류.
- `_dag` 접미는 붙이지 않는다.

## task_id
- 동사 스네이크. 공통 단계는 표준 이름을 재사용: `initialize_date`, `extract`, `transform`, `load`, `emit_outlets`.

## 파일명
- 1파일 = 1 DAG면 파일명 = dag_id. 팩토리(`airbyte_el`, `dbt_transformation`)는 1파일 = N DAG.

## 동적 식별자 sanitize
- 동적 id는 `[^A-Za-z0-9_.-]` → `_` 치환(`dbt_lib/utils.py`의 `safe()`). appid의 `.`은 `-`로.

## Connection
- conn_id: 스네이크. 대체로 `_conn` 접미(`doris_conn`, `idb_conn`), 예외 있음(`airflow_api`, `ftp`).
- Variable dict/list 값은 `Variable.get(key, deserialize_json=True, default_var=...)`.
