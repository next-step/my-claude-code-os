1. 클로드 OS 관련 모든 파일(예. .claude 하위 md)은 반드시 프로젝트 안에 만들 것
2. 클로드 OS 만들기 실습 중이기 때문에 대화 과정에서 AI와의 협업을 배울 수 있도록 양질의 설명 제공할 것
3. 모든 산출물(문서·노트·답변)은 `.claude/guides/writing-style.md`를 따를 것
4. 안전 가드레일 — 아래는 절대 하지 않는다(git force push·main 직접 push는 hook이 강제 차단):
   - main/master에 직접 push 금지. 브랜치에서 작업하고 PR로 올린다.
   - force push 금지(필요하면 `--force-with-lease` 또는 사용자 확인).
   - 비밀값(토큰·키·비밀번호)을 커밋하지 않는다.
   - 프로덕션 데이터·환경을 건드리지 않는다.
5. 작업 방식은 `.claude/guides/work-principles.md`를 따를 것(가급적 묻고, 시킨 것만)

## 컨텍스트 자동 주입

이 OS의 컨텍스트 체계는 레지스트리가 관리한다: `.claude/context/INDEX.md`(카탈로그 +
주입 매트릭스). 아래 4개 컨텍스트는 세션 시작 시 이 CLAUDE.md를 통해 메인 컨텍스트에
자동 주입된다(경로는 이 파일 기준 상대 경로).

@context/user.md
@context/project.md
@guides/writing-style.md
@guides/work-principles.md