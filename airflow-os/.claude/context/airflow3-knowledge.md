# Airflow 3 지식 (버전 종속 · 닳음 주의)

> Airflow 3.x 기준. 버전 올릴 때 이 파일을 갱신한다.

## 진입점 · import 경로
- TaskFlow·Asset 등 진입점은 `airflow.sdk`에서: `from airflow.sdk import dag, task, Asset, ...`.
- 대체된 import(구 → 신):
	- `airflow.operators.python` → `airflow.providers.standard.operators.python` (`PythonOperator`)
	- `airflow.operators.empty` → `airflow.providers.standard.operators.empty` (`EmptyOperator`)
	- `airflow.models.dagbag` → `airflow.dag_processing` (`DagBag`)
	- `airflow.datasets` → `airflow.sdk` (`Asset`)
	- XCom base: `from airflow.sdk.bases.xcom import BaseXCom`
- context 키·이벤트 변경: `execution_date` → `logical_date`, `triggering_dataset_events` → `triggering_asset_events`.

## cron 발사 모델 (v2와 다름)
- v3는 cron을 트리거 시각에 발사 → `data_interval_start` = 발사 시각(v2의 interval lag 없음). ETL은 1시간, dbt는 n_days_ago만큼 수동 보정한다.

## 워커 · 메타DB
- 워커는 메타DB 직접 조회 불가 → REST `/api/v2` 사용. `POST /auth/token`(Simple Auth Manager JWT) → Bearer. datetime 필터는 `_gte`/`_lte`만(반열림은 1μs 빼서).
- `RuntimeTaskInstance`에 `get_dagrun()` 없음 → 필요한 집계는 XCom 등으로 우회.
