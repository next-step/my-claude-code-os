# 무대(stage) 계약 — 촬영이 기대는 유일한 인프라

촬영·측정 스크립트가 대상 프로젝트에 요구하는 것의 전부다. 이 계약만 지키면 demo-app이 아니어도 동작한다.

## 이음새 1 — `.claude/visual.config.json`
무대 위치를 기술하는 유일한 설정. 스크립트는 demo-app을 하드코딩하지 않고 이걸 읽는다(로더: `.claude/scripts/visual-config.mjs`, cwd에서 위로 탐색).

| 키 | 뜻 | demo-app 값 |
|---|---|---|
| `baseUrl` | dev 서버 주소 | `http://localhost:5173` |
| `variantRoute` | 변형 고립 렌더 경로. `{target}` 치환 | `/gallery?c={target}` |

- **설정이 없으면 기본값 = demo-app 값** → 안 깨진다.
- 다른 무대(예: Storybook `/iframe.html?id={target}`)로 옮기려면 이 두 값만 바꾼다 = **연결**.

## 이음새 2 — DOM 컨벤션
무대 화면이 지켜야 할 마크업. 촬영 스크립트는 컴포넌트를 모르고 이것만 본다.

- 변형마다 래퍼에 `data-variant-id="<id>"` (촬영 대상 식별)
- 래퍼의 **첫 자식**이 컴포넌트 루트 (`:scope > *:first-child`를 찍음)
- 래퍼 직속 `<span>` = 라벨, `data-expected="ok|warn|error"` = 채점용 정답(판정 에이전트에겐 블라인드)

## dev 서버 소유권
- 이미 떠 있으면(UP) 그대로 쓰고 마커를 남기지 않는다 — 남의 서버는 안 건드림.
- 직접 띄우면 PID를 `.claude/.visual-dev-server.pid`에 남긴다 — SessionEnd 훅이 이것만 정리.

## 경계
- 무대가 없는 프로젝트에 무대를 **설치**하는 건 온보딩(OS.md 8단계, 미구현)의 몫. 스킬이 즉석에서 무대를 만들어내려 하지 않는다.
