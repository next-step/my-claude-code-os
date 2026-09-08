# `.claude/knowledge/` — 시스템·벤더별 사실

`.claude/context/` 가 **팀 전체 집계·정책**을 담는다면, 여기는 **특정 대상의 사실**을 담는다.

| 폴더 | 담는 것 | 읽는 쪽 |
| --- | --- | --- |
| `systems/<시스템>.md` | 그 시스템의 관리주체·담당 외주사·스택·과거 작업 | `classifier` (`classification-policy.md` §1② 수행 주체 확인) |
| `vendors/<업체>.md` | 그 외주사와의 계약 범위·전담 시스템 | `classifier` (§0 "특정 벤더 전담" 선판정, §2 캐파) |

## 왜 `context/` 와 나눴나

`team-capability.md` 는 "우리 팀이 뭘 할 수 있나" 라는 **집계**다. "정산시스템 A는 회사 A가 전담" 같은
**개별 시스템의 사실**을 거기 섞으면 파일이 시스템 수만큼 커진다. 성격(집계 vs 개별)과 변경 주기가
다르므로 분리한다 — `OS.md` §5 원칙 2.

## 현재 파일

- `systems/board.md` — `sandbox/board` (내부 관리, 벤더 없음). classifier A/B 가 이 파일 부재로
  관리주체를 추측하던 것을 채운 것.
- `vendors/` — 아직 없음. 벤더가 있는 시스템이 생기면 추가.
