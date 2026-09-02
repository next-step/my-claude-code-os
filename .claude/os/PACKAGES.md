# 패키지 목록

이 OS는 여섯 패키지로 나뉜다. 패키지를 가르는 기준은 두 개뿐이다.

1. **함께 바뀌는가** — 하나를 고칠 때 늘 같이 고치는 것들은 한 패키지다.
2. **따로 쓰일 수 있는가** — 다른 맥락에서 혼자 쓰이면 별도 패키지다.

| 패키지 | 사는 곳 | 한 문장 |
|---|---|---|
| [engine](engine/package.md) | `.claude/os/engine/` | 속성이 무엇인지 모른 채 사이클을 돌리는 공통 코어 |
| [bag-category-gender](attributes/bag-category-gender/package.md) | `.claude/os/attributes/bag-category-gender/` | 가방 상품의 대상 고객 성별만 아는 **속성 팩의 첫 인스턴스** |
| [accessories-category-gender](attributes/accessories-category-gender/package.md) | `.claude/os/attributes/accessories-category-gender/` | 잡화 상품의 대상 고객 성별 골든셋과 근거 이미지만 아는 속성 팩. 아직 가져오기 한 단계뿐이다 |
| [review](review/package.md) | `.claude/os/review/` | 엔진이 낸 run 하나를 심사한다 — 이 결과로 사람이 판정을 시작해도 되는가 |
| [interview](interview/package.md) | `.claude/os/interview/` | 모호한 요구를 판정 가능한 문장으로 바꾸는 절차 |
| [dev-workflow](dev-workflow/package.md) | `.claude/os/dev-workflow/` | 엔진·속성·인터뷰와 무관한 개발 워크플로우 — GitHub 절차와 요청 횟수 훅 |

여섯 줄이 같은 종류는 아니다. `engine`·`review`·`interview`·`dev-workflow`는 **역할** 이름이라 늘어나지
않고, `attributes/` 아래는 속성이 늘 때마다 옆으로 늘어나는 **인스턴스**다. 그래서 새 속성을
추가하는 일은 이 표에 줄을 하나 더 붙이는 일이지, 구조를 바꾸는 일이 아니다.

## 의존 방향

```
bag-category-gender  ──▶  engine        (속성은 엔진을 안다)
bag-category-gender  ──▶  review        (run.sh가 사이클 뒤에 심사를 잇는다)
interview   ──▶  engine        (프로필 해석기를 그대로 쓴다)
review      ──▶  runs/<프로필ID>/run-summary.json   (코드가 아니라 산출물만 안다)
engine      ──✗  bag-category-gender    (엔진은 속성을 모른다)
engine      ──✗  interview     (엔진은 인터뷰를 모른다)
engine      ──✗  review        (엔진은 심사를 모른다)
review      ──✗  engine · attributes    (import하지 않고 프로필도 읽지 않는다)
dev-workflow ──✗ 전부           (독립)
```

`review`만 화살표가 패키지가 아니라 **파일**을 가리킨다. 심사가 엔진 코드를 부르면
엔진의 오해가 심사에도 그대로 들어가서, 다시 세는 의미가 없어지기 때문이다.
계약은 [handoff.md](review/contracts/handoff.md)에 있다.

`interview`가 속성이 아니라 별도 패키지인 이유는 시점이다. 엔진은 데이터가 있어야 돌지만
인터뷰는 데이터가 없어도 돈다 — 오히려 데이터를 만들기 전에 도는 것이 정상이다.

화살표가 한쪽으로만 간다는 것이 이 구조의 전부다. 엔진이 속성을 알기 시작하면
속성을 하나 추가할 때마다 엔진을 고쳐야 하고, 그 순간 패키지는 이름만 남는다.

## 합격 기준

**속성 패키지를 통째로 지워도 엔진이 그대로 돈다.**

사람이 매번 확인할 수 없으므로 [test_package_boundary.py](engine/tests/test_package_boundary.py)가
확인한다. 이 테스트는 네 가지를 본다.

| 검사 | 막는 것 |
|---|---|
| 엔진 코드에 도메인 어휘가 없다 | `가방`·`MALE`·`29CM`이 공통 코어에 스며드는 것 |
| 선언된 누수가 실제로 존재한다 | 고쳐 놓고 선언만 남아 목록이 거짓말이 되는 것 |
| 엔진이 `attributes/` 경로를 가리키지 않는다 | 특정 속성에 대한 하드코딩 |
| 낯선 속성 하나로 사이클 후반부가 돈다 | 엔진이 가방 데이터에 의존하는 것 |

## 아직 남은 누수

엔진에 남아 있는 도메인 지식은 [declared-leaks.json](engine/contracts/declared-leaks.json)에
이유와 후속 조치까지 함께 선언한다. 선언되지 않은 누수는 테스트가 막는다.

정책 레이어의 `acknowledges`와 같은 원리다 — **누수 자체보다, 아무도 모르는 누수가 문제다.**

## 스킬·에이전트·훅은 어디에 있는가

Claude Code 하네스는 스킬을 `.claude/skills/<이름>/SKILL.md`에서, 에이전트를
`.claude/agents/`에서, 훅을 `.claude/settings.json`이 가리키는 경로에서만 읽는다. 그 밖의 경로는
자동으로 읽히지 않는다. 그래서 **실체는 각 패키지의 `skills/`·`agents/`·`hooks/`에 두고, 하네스가
읽는 자리에는 심볼릭 링크만 둔다.** 문서가 링크를 지원하고, 실험으로도 확인했다.
**모든 패키지가 같은 규칙을 따른다.** `.claude/skills/`·`.claude/agents/`·`.claude/hooks/` 아래에
실체는 하나도 없다.

```
.claude/os/engine/skills/catalog-data-os/SKILL.md                     ← 실체
.claude/skills/catalog-data-os -> ../os/engine/skills/catalog-data-os       ← 링크
.claude/os/engine/agents/catalog-golden-adjudicator.md                ← 실체
.claude/agents/engine/catalog-golden-adjudicator.md -> ../../os/engine/…    ← 링크
.claude/os/dev-workflow/hooks/count-prompt.sh                         ← 실체
.claude/hooks/count-prompt.sh -> ../os/dev-workflow/hooks/count-prompt.sh   ← 링크 (settings.json이 이 경로를 가리킨다)
```

훅은 에이전트처럼 패키지 폴더로 나누지 않는다. 훅의 진짜 진입점은 폴더가 아니라 `settings.json`의
경로이고, 그 경로를 바꾸면 하네스가 침묵하므로 평평하게 둔다. 대신 훅은 스크립트 위치에서
프로젝트 루트를 역산할 때 폴더 깊이를 세지 않는다 — 링크로 불리든 실체로 불리든 같은 파일에 써야 한다.

## 에이전트는 `.claude/os/`의 패키지 경로를 그대로 옮긴다

하네스는 `.claude/agents/`를 **재귀로** 읽고, 에이전트의 정체는 폴더가 아니라 `name`
프론트매터가 정한다. 그래서 폴더를 나눠도 호출 이름은 그대로이고, 대신 **어느 패키지가
이 에이전트를 소유하는지가 목록에서 바로 보인다.**

```
.claude/agents/engine/                       ← 역할. 한 겹
.claude/agents/interview/                    ← 역할. 한 겹
.claude/agents/attributes/<프로필ID>/         ← 인스턴스. 두 겹. 지금은 비어 있다
```

**깊이가 다른 것이 실수가 아니라 요점이다.** 셋을 같은 층에 늘어놓으면 역할과 사례가
대등해 보이고, 속성을 하나 추가할 때마다 목록 맨 위가 흔들린다. 속성 전용 에이전트는
지금 하나도 없지만, 생기면 갈 자리는 이미 정해져 있다. `.claude/os/`가 이미
그렇게 나뉘어 있으므로 진입점도 같은 모양을 쓴다 — 두 곳의 모양이 다르면 어느 쪽이
진짜 구조인지 다음 사람이 알 수 없다.

스킬은 `.claude/skills/<이름>/SKILL.md`가 하네스 규격이라 나눌 수 없어 평평하게 둔다.
그 자리에서는 접두사(`catalog-` · `bag-`)가 소속을 대신 말한다.

| 패키지 | 에이전트 | 무엇을 판단하나 |
|---|---|---|
| engine | `catalog-golden-adjudicator` | 큐의 **한 건**이 정책 공백인가 GT 오류인가 실행 오류인가 |
| review | `catalog-run-reviewer` | run **하나**가 사람 판정의 근거가 될 수 있는가. 상품은 판정하지 않는다 |
| interview | `catalog-source-curator` | 자료 더미에서 무엇을 참조로 넣을 것인가 |
| interview | `catalog-interviewer` | 비어 있는 슬롯에 무엇을 물을 것인가 |

셋뿐이고, **셋 다 부르는 스킬이 있다.** 나누는 기준은 패키지와 같다 — 함께 바뀌는가.
큐레이터와 인터뷰어가 갈라진 이유는 보는 것이 다르기 때문이다. 큐레이터는 자료가 말한 것을
슬롯 옆에 놓고, 인터뷰어는 그러고도 비어 있는 자리를 묻는다. 판정관이 따로인 이유는 단위다 —
저 둘은 정의를 다루고 판정관은 데이터가 만든 모호함을 다룬다.

**부르는 스킬이 없는 에이전트는 두지 않는다.** 정의만 있고 호출되지 않는 에이전트는
하네스 목록에는 뜨므로 있는 것처럼 보이고, 그래서 다음 사람이 그 역할을 이미 누가 한다고 믿는다.
역할이 필요해지면 그때 그 역할을 부르는 스킬과 함께 만든다.

에이전트는 전부 `Read`·`Grep`·`Glob`만 쓴다. **판단은 하되 기록하지 않는다** — 확정은 사람이
하고 파일은 스킬의 스크립트가 쓴다. 이 경계가 무너지면 AI 추천과 사람 결정을 셀 수 없게 된다.

소속은 폴더가 말한다. 접두사(`catalog-` · `bag-`)는 이름 충돌을 막는 용도로만 남는다.
새 스킬은 패키지 `skills/`에 쓰고 `.claude/skills/`에 링크를 걸고, 새 에이전트는 패키지
`agents/`에 쓰고 `.claude/agents/<패키지>/`에 링크를 건다. 링크가 끊기면 스킬도 에이전트도 아무
경고 없이 사라지므로 [test_entry_points.py](engine/tests/test_entry_points.py)가 실체와 링크의
쌍을, 그리고 에이전트 링크가 자기 패키지 폴더에 있는지를 매번 검사한다.

새 훅은 패키지 `hooks/`에 쓰고 `.claude/hooks/`에 링크를 걸고 `settings.json`에 그 경로를 적는다.
훅의 세 겹(settings → 링크 → 실체)도 같은 테스트가 검사한다.

플러그인은 여전히 선택지다. 플러그인은 자기 `skills/`·`agents/`를 링크 없이 직접 선언하지만,
스킬 이름에 네임스페이스가 붙고 마켓플레이스 등록이 필요하다. 속성이 둘 이상이 되면 그때 검토한다.
