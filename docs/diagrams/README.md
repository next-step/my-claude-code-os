# 다이어그램 소스

`OS.md` 10장에 들어가는 다이어그램의 원본입니다. `.mmd`(Mermaid 소스)가 원본이고 `.svg`는 거기서 생성한 결과물이므로, **고칠 때는 항상 `.mmd`를 고치고 다시 생성**합니다.

| 파일 | OS.md 위치 | 내용 |
|---|---|---|
| `01-pipeline-spec` | 10.3 | 스펙 합의 구간 01~04 (승인 게이트 이전) |
| `02-pipeline-build` | 10.3 | 구현 구간 05~07 (승인 게이트 이후) |
| `03-orchestration` | 10.4 | 지휘자의 실제 호출 순서 (시퀀스) |
| `04-shared-agents` | 10.5 | 공유 서브에이전트 재사용 관계 |
| `05-data-flow` | 10.6 | 훅이 쓰고 스킬이 읽는 데이터 흐름 |

## 다시 생성하기

```bash
cd docs/diagrams
for f in 01-pipeline-spec 02-pipeline-build 03-orchestration 04-shared-agents 05-data-flow; do
  npx -y @mermaid-js/mermaid-cli@11 -i "$f.mmd" -o "$f.svg" -c mermaid-config.json -b white
done
```

## 옵션이 왜 이렇게 정해졌는가

이 세 가지를 빼면 GitHub에서 다이어그램이 깨집니다. 실제로 한 번씩 겪고 고친 것들입니다.

| 설정 | 이유 |
|---|---|
| `mermaid-config.json`의 `"htmlLabels": false` | 기본값으로 뽑으면 라벨이 `<foreignObject>`(SVG 안의 HTML)로 들어가는데, GitHub이 마크다운 이미지를 `<img>`로 렌더링할 때 이 안의 HTML은 실행되지 않아 **글자가 통째로 사라진다.** `false`로 두면 일반 `<text>`로 출력된다 |
| `-b white` | 배경을 비워 두면 GitHub 다크모드에서 검은 글씨가 검은 배경에 얹혀 안 보인다 |
| `fontFamily`에 한글 폰트 명시 | 렌더링은 headless Chromium에서 일어나므로 한글 폰트를 지정하지 않으면 글자가 깨지거나 폭이 어긋난다 |

생성된 SVG에 `foreignObject`가 남아 있지 않은지는 이렇게 확인합니다:

```bash
grep -c foreignObject *.svg   # 전부 0이어야 정상
```

## 색 규칙

다섯 개 다이어그램이 같은 색 언어를 씁니다.

| 색 | 의미 |
|---|---|
| 🟡 노랑 | 사람이 개입하는 지점 |
| 🟢 초록 | 스킬 (`.claude/skills/`) |
| 🔵 파랑 | 서브에이전트 (`.claude/agents/`) |
| 🔴 빨강 | 훅 (`.claude/hooks/`) |
| ⚪ 회색 | 데이터 파일 · 시작/종료 지점 |
