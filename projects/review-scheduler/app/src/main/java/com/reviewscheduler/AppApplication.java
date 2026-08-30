package com.reviewscheduler;

import com.reviewscheduler.domain.NextReviewDateCalculator;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;

import java.time.Clock;

@SpringBootApplication
public class AppApplication {

	public static void main(String[] args) {
		// CommandLineRunner(NoteCliRunner)는 컨텍스트 기동 중에 이미 실행되고 끝난다.
		// 이 앱은 "한 번 실행해서 결과를 보고 끝내는" CLI라서, run() 이후 컨텍스트를
		// 명시적으로 close()해 커넥션 풀 등을 정리하고 프로세스가 확실히 종료되게 한다.
		ConfigurableApplicationContext context = SpringApplication.run(AppApplication.class, args);
		context.close();
	}

	/**
	 * NextReviewDateCalculator는 의도적으로 순수 자바 클래스로 남겨뒀다(Spring
	 * 애노테이션 없음). 그래서 이 빈 등록은 domain 패키지가 아니라 여기,
	 * 프레임워크 조립 계층에 둔다 — 도메인 계산 로직과 프레임워크 배선을 분리하기 위함.
	 */
	@Bean
	public NextReviewDateCalculator nextReviewDateCalculator() {
		return new NextReviewDateCalculator();
	}

	/**
	 * "지금이 언제인가"를 얻는 유일한 통로. NoteService가 LocalDateTime.now()를
	 * 직접 부르지 않고 이 Clock을 주입받게 해서, 테스트에서는 Clock.fixed(...)로
	 * 바꿔 끼워 특정 시각(자정 근처, 타임존 경계 등)을 결정적으로 재현할 수 있다.
	 * 운영 환경에서는 시스템 기본 시간대의 실제 시계를 쓴다.
	 */
	@Bean
	public Clock clock() {
		return Clock.systemDefaultZone();
	}

}
