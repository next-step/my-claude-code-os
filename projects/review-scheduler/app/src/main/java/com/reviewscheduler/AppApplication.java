package com.reviewscheduler;

import com.reviewscheduler.domain.NextReviewDateCalculator;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

import java.time.Clock;

@SpringBootApplication
public class AppApplication {

	/**
	 * 이 앱의 유일한 진입점은 HTTP 서버다. 명령줄 배치 실행(등록 후 즉시 종료)은
	 * 없앴다 — 파일 기반 H2가 한 번에 한 프로세스만 열 수 있어서 "서버를 띄운 채로
	 * 명령줄도 함께 쓴다"는 전제가 애초에 성립하지 않았고, "무엇이 실제 명령인가"를
	 * 판단하는 규칙이 여기와 명령줄 러너 두 곳에 나뉘어 있어 서로 어긋날 위험도 있었다.
	 * 그래서 컨텍스트를 닫지 않고 계속 띄워두기만 한다(내장 톰캣의 비-데몬 스레드가
	 * 프로세스를 살려둔다). 예전 명령줄 동작이 다시 필요해지면 버전 관리 이력에서
	 * 되돌리면 된다.
	 */
	public static void main(String[] args) {
		SpringApplication.run(AppApplication.class, args);
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
