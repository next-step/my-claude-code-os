# airflow-os

## 코드 위치
- 실제 운영 DAG는 `prod-airflow/dags/` (심링크 → ops repo). 로컬 `dags/`엔 샘플뿐.
- Glob/Grep은 심링크를 기본으로 안 따라감 → `find -L prod-airflow/dags -name "*.py"`로 찾거나 경로를 직접 Read.

## 작업 라우팅
- DAG 작업은 파일부터 열지 말고 스킬로 라우팅: 
	- 리팩터·개선·리뷰 → dag-audit
	- 신규 → interview
	- 전 과정 → airflow-pipeline
- OS 전체 설계·파이프라인 구조는 OS.md 참고.
