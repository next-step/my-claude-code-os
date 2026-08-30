package com.reviewscheduler.domain;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 순수 단위 테스트: Spring 컨텍스트를 전혀 띄우지 않는다(@SpringBootTest 등 없음).
 * NextReviewDateCalculator는 org.springframework를 import하지 않는 순수 자바 클래스라서
 * 이렇게 new로 바로 만들어 검증할 수 있다.
 *
 * 검증 대상 수용 기준: "다음 복습일은 등록 시각보다 최소 1일 뒤여야 한다."
 */
class NextReviewDateCalculatorTest {

    private final NextReviewDateCalculator calculator = new NextReviewDateCalculator();

    @Test
    void 다음_복습일은_등록일보다_최소_1일_뒤다() {
        LocalDateTime registeredAt = LocalDateTime.of(2026, 8, 26, 10, 0);

        LocalDate nextReviewDate = calculator.calculateNextReviewDate(registeredAt);

        assertThat(nextReviewDate).isAfterOrEqualTo(registeredAt.toLocalDate().plusDays(1));
    }

    @ParameterizedTest
    @ValueSource(strings = {"00:00", "12:00", "23:59:59"})
    void 등록_시각이_하루_중_언제여도_다음_복습일은_최소_1일_뒤다(String time) {
        LocalDate registeredDate = LocalDate.of(2026, 8, 26);
        LocalDateTime registeredAt = LocalDateTime.of(registeredDate, LocalTime.parse(time));

        LocalDate nextReviewDate = calculator.calculateNextReviewDate(registeredAt);

        assertThat(nextReviewDate).isAfterOrEqualTo(registeredDate.plusDays(1));
    }

    @Test
    void 등록일이_null이면_예외를_던진다() {
        assertThatThrownBy(() -> calculator.calculateNextReviewDate(null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void 간격을_0으로_주면_생성_시점에_예외를_던진다() {
        assertThatThrownBy(() -> new NextReviewDateCalculator(0))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
