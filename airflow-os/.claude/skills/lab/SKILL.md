---
name: lab
description: Airflow 3.2.2 로컬 테스트 환경(venv)을 구축·검증·유지보수하는 인프라 스킬. 사용자가 "로컬 환경 구축/재구축", "환경 검증", "DAG 파싱 테스트", "패키지/더미 값 추가"를 요청하거나, DAG 테스트 중 import 에러가 환경 문제로 의심될 때 사용.
---

# Airflow Local Test Environment

운영 서버와 동일한 **Airflow 3.2.2 / Python 3.12** 로컬 venv 환경.
도커 없이 DAG 파싱 검증·pytest 단위 테스트까지 커버한다.

**철학: 최소 세팅 + 점진 추가.** 기본은 Airflow 코어뿐이고, provider·라이브러리·더미 Variable/Connection은 **작업하는 DAG가 필요로 할 때 그때그때 추가**한다. 운영 DAG 전체를 로컬에서 파싱 가능하게 만드는 것은 목표가 아니다.

## 환경 정보

- 운영 Airflow 레포: `prod-airflow/` (운영 레포로 향하는 심링크 — 실제 절대경로는 `setup.sh`의 `PROD_AIRFLOW_REPO` 한 곳에만 있고, 심링크는 `.gitignore`로 커밋 제외)
- venv: `airflow-os/.venv` / AIRFLOW_HOME: `airflow-os/.airflow` (SQLite, 운영 DB에 붙지 않음)
- DAG 소스: `prod-airflow/dags/`를 경로로 참조 (심링크라 항상 운영 실시간, 복사하지 않음)

## 구축 / 재구축

```bash
bash .claude/skills/lab/scripts/setup.sh   # Airflow 코어만 설치
```

재구축은 `rm -rf .venv` 후 다시 실행. (재구축하면 그동안 추가한 패키지가 사라지므로, 추가한 패키지는 아래 '패키지 추가' 규칙대로 setup.sh에 기록해둘 것.)

## 검증 (작업 대상 DAG 파싱 체크)

```bash
bash .claude/skills/lab/scripts/verify.sh <DAG 파일|폴더>   # 2~3초
```

- **성공 기준: import error 0건.**
- 에러가 나면 원인 별 대응:
  - `ModuleNotFoundError` → 아래 '패키지 추가'
  - `Variable ... does not exist` / `conn_id ... isn't defined` → 아래 '더미 값 추가'
  - 그 외 → DAG 자체 버그. 코드 수정 대상으로 보고.

## 패키지 추가

```bash
# airflow 생태계 패키지는 반드시 constraint 적용
uv pip install --python .venv/bin/python \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.2.2/constraints-3.12.txt" \
  <package>
```

추가했으면 **setup.sh에도 한 줄 반영** (재구축 시 유실 방지). 버전은 운영 Airflow 레포의 `Dockerfile`에 명시된 것이 있으면 그걸 따른다.

## 더미 값 추가 (Variable / Connection)

DAG가 파싱 시점에 Variable/Connection을 조회하면 `local_variables.env`에 더미를 추가한다:

- Variable: `export AIRFLOW_VAR_<KEY>="dummy"` (JSON형은 코드가 참조하는 키 구조까지 맞출 것)
- Connection: `export AIRFLOW_CONN_<ID>="mysql://dummy:dummy@localhost:3306/dummy"`
- **실제 운영 값은 절대 넣지 않는다.** verify.sh가 이 파일을 자동으로 로드한다.

## 알려진 한계

- 사내 라이브러리 `dough`를 import하는 DAG는 파싱 시점에 **운영 메타DB에 직접 접속**한다(dough 내장 db.cfg, env로 우회 불가). 사내망이 안 닿으면 해당 DAG는 로컬 파싱 불가 — 환경 문제가 아니므로 시간 쓰지 말 것.
- 이 환경은 파싱·단위 테스트용. 태스크 실제 실행(통합 테스트)이 필요해지면 2단계 도커 환경을 별도 구축한다.
