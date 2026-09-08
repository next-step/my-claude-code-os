# accessories-category-gender

잡화(표준 카테고리 대분류 `잡화`) 상품의 대상 고객 성별 골든셋만 아는 속성 팩.
아직 **가져오기 한 단계만** 있다 — 정책·감사·심판 어댑터는 없다. 이 폴더를 지우면
잡화 스냅샷이 사라지고, 엔진과 다른 속성은 그대로 돈다.

## 소유

| 종류 | 파일 |
|---|---|
| 선언 | `profile.json` — 라벨·가져오기 어댑터 경로. 정책 블록과 신호 정의는 아직 없다 |
| 어댑터 | `adapters/import_accessories_category_gender_sources.py` |
| 산출물 | `.claude/os/runs/accessories-category-gender/` (재생성 가능, 소유가 아니라 출력) |

## 왜 이미지 바이트까지 복사하는가

`bag-category-gender`의 가져오기는 이미지를 복사하지 않는다. 가방 감사는 정책 문장과
GT 라벨, 근거 장면 ID만으로 돌기 때문이다. 잡화는 다르다 — 판정 근거가 상세 타일 이미지
자체에 있어서, 원본 저장소가 `work/`를 비우면 왜 그렇게 판정했는지 다시 볼 수 없다.
그래서 여기서는 참조된 파일을 실제로 가져온다.

이미지 바이트는 `runs/accessories-category-gender/asset/`에 들어가고, 1GB가 넘어 git이
추적하지 않는다(`.gitignore`). 텍스트 원장인 `golden/`과 무거운 바이너리인 `asset/`을 나눈
이유가 이것이다 — 추적하는 것과 추적하지 않는 것이 한 폴더에 섞이지 않는다.

대신 **어떤 파일이 어느 상품의 몇 번째 근거였는지**는 `golden/accessories-image-index.jsonl`이
추적한다. 바이트는 재현물이고, 색인이 기록이다.

색인에는 **asset으로 실제 들어온 파일만** 적는다. 원본에 파일이 없어 가져오지 못한 참조는
색인에서 빠지고 `manifest.json`의 `droppedImageReferences`에 남는다. 없는 근거를 있는 것처럼
세지 않으면서도, 무엇이 빠졌는지는 보이게 하기 위해서다.

## 실행

```bash
python3 .claude/os/attributes/accessories-category-gender/adapters/import_accessories_category_gender_sources.py
```

같은 파일이 이미 같은 크기로 있으면 다시 복사하지 않는다. `--skip-asset`을 주면 GT와
색인만 갱신한다. 건수·용량은 실행이 끝나며 찍히는 `manifest.json`을 본다.
