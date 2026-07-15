# 작업환경

## 코드 위치
- 실제 운영 DAG는 `prod-airflow/dags/` (심링크 → ops repo). 여기가 **배포 타깃**이다.
- Glob/Grep은 심링크를 기본으로 안 따라감 → `find -L prod-airflow/dags -name "*.py"`로 찾거나 경로를 직접 Read.

## 구현 위치
- 새 DAG·수정은 `prod-airflow/dags/<서브경로>/`에 쓴다. 서브경로·네이밍·구조는 그 폴더의 유사 DAG 관례를 따른다.

## 테스트 위치
- 테스트 코드는 `prod-airflow/tests/`에 두고, `dags/`의 서브경로를 미러한다: `dags/<서브폴더>/x.py` → `tests/<서브폴더>/test_x.py`.
- **`dags/` 폴더 안에는 테스트 파일을 절대 두지 않는다.** Airflow DagBag이 그 폴더를 스캔해 모든 `.py`를 DAG로 파싱하므로, 테스트가 파싱 대상에 섞여 에러를 낸다.
- ops repo의 `tests/`는 **로컬 마이그레이션 검증용이며 커밋하지 않는다**(ops repo `.git/info/exclude`로 로컬 제외).
