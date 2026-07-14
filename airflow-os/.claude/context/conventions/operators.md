# 오퍼레이터 · 작성 스타일

## TaskFlow 표준
- `@dag(...)` + `@task`로 구성한다(진입점은 `airflow.sdk`). 
- 파일 끝에서 `dag_fn()` 인스턴스화. 
- 클래식 `with DAG(...)`는 쓰지 않는다.

## 동적 그래프
- fan-out: `@task.expand()` / `.partial(...).expand(...)`
- 그룹화: 계정·앱별은 `with TaskGroup(group_id=f"...")`
- 같은 task 반복 인스턴스화는 `.override(task_id=...)`

## 선호 오퍼레이터
- 센서: `PythonSensor`/`@task.sensor`, `GCSObjectExistenceSensor`. 모드는 대기 길이로 — 짧으면(몇 분 이내) `poke`, 길면(수십 분 이상) `mode="reschedule"`(슬롯 놓아줌). 아주 길면 deferrable 고려.
- 흐름 제어: `@task.short_circuit`.
- 격리 실행: `@task.external_python`(별도 venv, airbyte), `DockerOperator`(컨테이너 실행).
- 클래식 `BranchPythonOperator`/`PythonOperator` 직접 사용은 피한다(계보용 emit 등 불가피한 곳만).

## 로깅
- `logger = logging.getLogger("airflow.task")`. `print()` 디버깅은 지양.
