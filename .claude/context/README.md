# .claude/context — 정본(Single Source of Truth) 컨텍스트

이 폴더는 **여러 스킬·서브에이전트가 공통으로 참조하는 "사실"을 한 곳에 모은 정본**이다.
같은 지식이 스킬·에이전트·셸 스크립트에 복붙되어 "하나 바꾸면 전부 손봐야 하는" 문제를
없애기 위해 존재한다.

## 폴더 성격 구분

이 프로젝트의 `.claude` 하위는 성격으로 나뉜다. 헷갈리지 않게 정리한다.

| 폴더 | 성격 | 예 |
|------|------|-----|
| `skills/_shared/*.sh` | **실행되는 것** (코드) | `classify.sh`가 돌아감 |
| `skills/_shared/*.md` | **호출되는 것** (에이전트 프롬프트) | `classifier-agent.md`를 Agent 도구가 prompt로 씀 |
| **`context/*.md`** | **읽히는 것** (참조 사실) | `data-model.md`를 스킬이 Read해서 참고 |

## 정본 목록

| 파일 | 담는 것 | 로딩 |
|------|---------|------|
| [`data-model.md`](./data-model.md) | todos 스키마 + 저장 구조(캐시·outbox·자격증명 경로) | Lazy |
| [`categories.md`](./categories.md) | 카테고리 6종 정의 + 분류 규칙 | Lazy |
| [`status-lifecycle.md`](./status-lifecycle.md) | 상태 전이(draft→planned→done) + 스킬별 담당 | Lazy |
| [`design-principles.md`](./design-principles.md) | 오케스트레이터 패턴·로컬우선동기 등 설계 어휘 | Lazy |
| [`security.md`](./security.md) | 비밀값 취급 규칙 + 민감 파일 목록 | **Eager** |

## 연결 방식 (하이브리드 — Lazy 기본 + 안전 정본만 Eager)

정본은 두 방식으로 주입된다. 파일 성격에 따라 나뉜다.

### Lazy (기본) — 필요할 때만 Read

대부분의 정본은 **각 스킬/서브에이전트가 필요할 때 Read**한다. CLAUDE.md에 항상 주입하지
않으므로, 해당 스킬을 실행할 때만 로드되어 평상시 토큰 비용이 없다. 단, 로드 트리거가
모델의 지시 준수라 100% 보장은 아니다(모델 주도 Lazy 로딩).

각 SKILL.md / 서브에이전트 프롬프트 상단에는 아래처럼 참조가 걸려 있다.

```markdown
> **참조 정본**: 이 스킬은 아래 정본을 따른다. 관련 판단 시 먼저 Read한다.
> - `.claude/context/data-model.md`
> - `.claude/context/status-lifecycle.md`
```

### Eager (안전 정본) — CLAUDE.md로 상시 주입

`security.md`처럼 **"안 읽으면 사고"가 나는, 무조건 보장이 필요한** 정본은 프로젝트
`CLAUDE.md`에서 `@import`로 매 세션 항상 로드한다. 특정 스킬 실행과 무관하게 컨텍스트에
있으므로, 각 스킬은 이를 별도 Read하지 않는다.

```markdown
<!-- 프로젝트 CLAUDE.md -->
@.claude/context/security.md
```

> **승격/강등 기준**: "빈도가 높다"만으로 Eager로 올리지 않는다(길면 매 세션 토큰 낭비).
> "안 읽었을 때의 리스크가 크고 + 파일이 짧다"가 Eager의 조건이다.

## 규칙

- 정본을 바꿀 때는 **이 폴더의 파일을 먼저** 고친다. 그다음 그 정본의 "코드 표현"
  (예: `classify.sh`)이나 요약이 어긋났으면 최소 diff로 맞춘다.
- 새 정본을 추가하면 이 README의 목록과, 참조하는 스킬의 상단 블록을 함께 갱신한다.
