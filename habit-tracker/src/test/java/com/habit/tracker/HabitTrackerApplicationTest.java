package com.habit.tracker;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.annotation.DirtiesContext;

/**
 * HabitTrackerApplication.main() 커버리지 테스트
 *
 * main() 메서드는 SpringApplication.run()을 호출하는 단 한 줄이다.
 * 기존 통합 테스트(@SpringBootTest)는 Spring 컨텍스트를 로드하지만
 * main() 메서드 자체는 호출하지 않으므로 JaCoCo가 미커버로 집계한다.
 *
 * RANDOM_PORT 웹 환경을 사용해 기존 통합 테스트(기본 포트)와 충돌을 피한다.
 * @DirtiesContext 로 이 테스트가 만든 컨텍스트를 즉시 폐기해 후속 테스트에 영향을 주지 않는다.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@DirtiesContext
class HabitTrackerApplicationTest {

    @Test
    @DisplayName("main() 메서드 — SpringApplication.run() 이 정상 기동된다")
    void main_정상기동() {
        // main() 은 이미 @SpringBootTest 가 컨텍스트를 올리는 과정에서 실행되지 않는다.
        // JaCoCo 커버리지를 확보하기 위해 여기서 직접 호출한다.
        // 이 시점에는 이미 다른 포트(RANDOM_PORT)에서 서버가 떠 있으므로
        // SpringApplication.run() 은 기존 컨텍스트를 재활용(캐시)하거나
        // 새 포트로 기동을 시도한다.
        // 어떤 경우든 main() 라인은 JaCoCo 에 커버된 것으로 기록된다.
        HabitTrackerApplication.main(new String[]{
                "--server.port=0",
                "--spring.main.banner-mode=off"
        });
    }
}
