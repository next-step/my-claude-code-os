#!/usr/bin/env bash
# Airflow 3.2.2 로컬 테스트 환경 구축 (운영 서버와 동일: Airflow 3.2.2 / Python 3.12)
# 철학: 최소 설치. provider·라이브러리는 작업할 DAG가 필요로 할 때 그때그때 추가한다.
set -euo pipefail

cd "$(dirname "$0")/../../../.."  # airflow-os 루트로 이동

PROD_AIRFLOW_REPO=/Users/yepark/Project/77-draft/airflow-v3  # 운영 레포 실제 위치 — 이동 시 이 줄만 수정 (유일한 절대경로 지점)
AIRFLOW_VERSION=3.2.2
PYTHON_VERSION=3.12
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

echo "── 운영 레포 심링크 (prod-airflow → 운영 레포, .gitignore로 커밋 제외)"
ln -sfn "$PROD_AIRFLOW_REPO" prod-airflow

echo "── 1. venv 생성 (.venv, python ${PYTHON_VERSION})"
uv venv .venv --python ${PYTHON_VERSION}

echo "── 2. Airflow 코어 설치 (constraint 적용)"
uv pip install --python .venv/bin/python --constraint "${CONSTRAINT_URL}" \
    "apache-airflow==${AIRFLOW_VERSION}"

echo "── 3. 단위 테스트 러너 (pytest, constraint 적용)"
uv pip install --python .venv/bin/python --constraint "${CONSTRAINT_URL}" pytest

echo "── 4. DAG별 추가 패키지 (작업하며 그때그때 추가된 것)"
# doris_game_silver_level_design: gspread(스프레드시트), google provider(GoogleBaseHook)
uv pip install --python .venv/bin/python --constraint "${CONSTRAINT_URL}" \
    gspread apache-airflow-providers-google

echo "── 완료. 패키지 추가는 SKILL.md의 '패키지 추가' 절 참고."
