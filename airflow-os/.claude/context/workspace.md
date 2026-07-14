# 작업환경

## 코드 위치
- 실제 운영 DAG는 `prod-airflow/dags/` (심링크 → ops repo). 로컬 `dags/`엔 샘플뿐.
- Glob/Grep은 심링크를 기본으로 안 따라감 → `find -L prod-airflow/dags -name "*.py"`로 찾거나 경로를 직접 Read.
