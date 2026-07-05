# 컨벤션

프로젝트 전반에서 재사용되는 규칙 모음. 스킬 실행 중 관련 컨텍스트가 필요하면 이 파일을 참고한다.

---

## 커밋 메시지

[Conventional Commits](https://www.conventionalcommits.org/) 형식으로 작성합니다.

```
<type>(<scope>): <subject>

<body>  ← 선택사항. 왜 변경했는지 설명할 때만 추가
```

### scope 결정 기준

`<scope>`는 컴포넌트/파일명이 아니라 **현재 브랜치 이름**에서 파생합니다.

- 브랜치 이름의 **마지막 `/` 뒤 세그먼트**를 scope로 사용
  - `feature/add-button` → `add-button`
  - `feature/team/add-button` → `add-button` (마지막 세그먼트만)
- 브랜치 이름에 `/`가 없으면(`main`, `step1` 등) scope를 생략하고
  `<type>: <subject>` 형식으로 작성
- 같은 브랜치에서 나온 커밋은 type이 달라도 scope가 동일합니다:
  ```
  feat(add-button): 버튼 컴포넌트 추가
  style(add-button): 버튼 hover 스타일 조정
  ```

### 타입 선택 기준

| 타입 | 사용 상황 |
|------|-----------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서(README, 주석 등) 변경 |
| `style` | 기능 변화 없는 포맷 변경 (들여쓰기, 세미콜론 등) |
| `refactor` | 기능 변화 없는 코드 구조 개선 |
| `test` | 테스트 코드 추가 / 수정 |
| `chore` | 빌드 설정, 패키지, 기타 유지보수 |

### 좋은 subject 작성법

- 50자 이내로 간결하게
- 명령형 동사로 시작 — "추가", "수정", "제거", "개선" 등
- "무엇을" 했는지보다 **"왜" 했는지**를 담을 것
- 변경된 파일명 나열 금지 — 의도와 맥락을 담을 것
- 항상 한국어로 작성

### 예시

브랜치 `feature/add-button`에서 `Button.tsx`에 disabled 상태 추가:

```
feat(add-button): disabled 상태 추가
```

같은 브랜치에서 스타일만 수정:

```
style(add-button): disabled 상태 회색 스타일 추가
```

브랜치 `main`에서 직접 문서만 수정 (scope 없음):

```
docs: README 오타 수정
```
