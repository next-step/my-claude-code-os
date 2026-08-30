package com.reviewscheduler.note;

import com.reviewscheduler.AppApplication;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * "앱을 종료했다가 다시 실행해도 노트 값이 그대로 남아 있다"를 실제로 흉내 낸다:
 * 스프링 컨텍스트를 띄워 노트를 등록하고 컨텍스트를 close()해서 종료를 재현한 뒤,
 * 같은 파일 기반 H2 DB를 가리키는 새 컨텍스트를 다시 띄워 값을 읽어본다.
 *
 * @DataJpaTest를 쓰지 않은 이유: @DataJpaTest는 기본적으로 각 테스트를 트랜잭션으로
 * 감싸고 끝나면 롤백한다. 그러면 디스크에 실제로 커밋되는지를 검증할 수 없어서,
 * 여기서는 AppApplication을 실제로 두 번 기동/종료하는 방식을 쓴다.
 *
 * 검증 대상 수용 기준: "앱을 종료했다가 다시 실행해도 모든 노트의 등록 시각과
 * 다음 복습일 값은 이전과 동일하게 남아 있다."
 */
class NoteRestartPersistenceTest {

    @TempDir
    Path tempDir;

    @Test
    void 앱을_재시작해도_노트의_등록_시각과_다음_복습일이_그대로_남는다() {
        String jdbcUrl = "jdbc:h2:file:" + tempDir.resolve("review-scheduler");

        LocalDateTime registeredAtBeforeRestart;
        LocalDate nextReviewDateBeforeRestart;
        Long noteId;

        // 1차 실행: 노트를 등록하고 앱을 종료한다.
        try (ConfigurableApplicationContext firstRun = startApp(jdbcUrl)) {
            NoteService noteService = firstRun.getBean(NoteService.class);
            Note saved = noteService.registerNote("스프링 부트로 리뷰 스케줄러 만들기");

            noteId = saved.getId();
            registeredAtBeforeRestart = saved.getRegisteredAt();
            nextReviewDateBeforeRestart = saved.getNextReviewDate();
        }

        // 2차 실행: 같은 DB 파일을 가리키는 새 컨텍스트로 "재시작"한다.
        try (ConfigurableApplicationContext secondRun = startApp(jdbcUrl)) {
            NoteRepository noteRepository = secondRun.getBean(NoteRepository.class);
            Note reloaded = noteRepository.findById(noteId).orElseThrow();

            assertThat(reloaded.getRegisteredAt()).isEqualTo(registeredAtBeforeRestart);
            assertThat(reloaded.getNextReviewDate()).isEqualTo(nextReviewDateBeforeRestart);
        }
    }

    private ConfigurableApplicationContext startApp(String jdbcUrl) {
        // 주의: SpringApplicationBuilder#properties(...)는 "기본값(default properties)"으로
        // 등록되어 src/main/resources/application.properties보다 우선순위가 낮다. 그래서
        // 여기서는 명령줄 인자 형태(--key=value)로 run()에 넘긴다 — 이 방식이 가장 높은
        // 우선순위를 가져서 실제로 우리가 지정한 임시 DB 경로로 덮어써진다.
        return new SpringApplicationBuilder(AppApplication.class)
                .web(WebApplicationType.NONE)
                .run(
                        "--spring.datasource.url=" + jdbcUrl,
                        "--spring.datasource.driver-class-name=org.h2.Driver",
                        "--spring.jpa.hibernate.ddl-auto=update"
                );
    }
}
