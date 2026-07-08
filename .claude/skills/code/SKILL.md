---
name: code
description: Locate and analyze the paper's implementation code (official repo or a faithful reference implementation) — map architecture, key modules, and how the method translates to code. Use after /analyzer when the user wants the implementation understood.
---

# /code — 구현 코드 분석 스킬

논문의 **구현 코드를 찾아 분석**하여, 방법론이 코드로 어떻게 대응되는지 설명합니다.

## 입력
- `output/01_analysis.md`(구현 단서/저장소 링크 참고). 없으면 논문 링크에서 직접 탐색.

## 절차
1. **저장소 탐색**: 분석 리포트의 "구현 단서" 또는 `WebSearch`로 공식 코드(`github.com/...`, Papers with Code) 검색. 공식이 없으면 신뢰도 높은 재현 구현을 고른다(반드시 공식/비공식 명시).
2. **구조 파악**: 레포의 README, 디렉토리 트리, 진입점(train/main), 모델 정의 파일을 식별.
3. **핵심 매핑**: 논문의 핵심 수식/모듈 ↔ 코드의 함수/클래스 대응표 작성.
4. **읽기**: 핵심 파일의 중요 함수를 인용·해설. 데이터 흐름(입력→전처리→모델→손실→출력) 추적.
5. `output/04_code.md`로 저장.
6. **실행 카드 분리 발행**: 위 본문과 별도로, `/code-run`이 필요로 하는 **사실만** 추린 소형 `output/04_runcard.md`(≤ 약 1,800자)를 함께 저장한다. code-run은 거대한 04_code.md 전체 대신 이 카드만 읽어(파이프라인 다운스트림 컨텍스트 절감) 실행을 준비한다.

## 출력 스키마 (`output/04_code.md`)
```markdown
# 구현 코드 분석: <제목>

- **저장소**: <url> (공식/비공식 명시)
- **언어 / 핵심 프레임워크**:
- **실행 진입점**: <파일:함수>

## 1. 디렉토리 구조 (핵심만)
## 2. 논문 ↔ 코드 매핑 표
| 논문 개념 | 코드 위치(파일:함수/클래스) | 설명 |
## 3. 데이터 흐름 추적
## 4. 핵심 코드 발췌 + 해설
## 5. 의존성 / 환경 요구사항 (실행에 필요한 것)
## 6. 최소 재현(Minimal Repro) 가능 여부와 경로
```

## 실행 카드 스키마 (`output/04_runcard.md` — code-run 전용, ≤ ~1,800자)
```markdown
# 실행 카드: <제목>
- **저장소**: <url> (공식/비공식) · **고정 커밋/태그**: <hash|없음>
- **언어/프레임워크**: · **진입점**: <파일:함수>
- **핵심 의존성**: <requirements 파일 경로 또는 3~6개 패키지>
- **최소 실행 경로**: <clone→env→install→run 을 한 줄 요약>
- **하드웨어/데이터**: <GPU·디스크·다운로드 용량/시간, 없으면 "CPU로 가능">
```

## 품질 기준
- 코드 인용은 실제 파일 경로 기반. 추측한 경로는 "추정"으로 표기.
- 논문↔코드 매핑 표는 최소 4개 행.
- 5·6장은 `/code-run`이 바로 쓸 수 있도록 의존성/실행법을 구체적으로.
- **분량 예산**: `04_code.md` 본문은 핵심 위주로 **~24,000자(약 300줄) 이내**로 밀도 있게. 코드 발췌는 대표 함수만 인용하고 전체 붙여넣기 금지. (이 파일은 이후 게이트·html이 반복 로딩하므로 짧고 밀도 높게 유지하는 것이 파이프라인 전체 컨텍스트를 줄인다.)
- 완료 후 `output/04_code.md` **및 `output/04_runcard.md`** 경로 보고.
