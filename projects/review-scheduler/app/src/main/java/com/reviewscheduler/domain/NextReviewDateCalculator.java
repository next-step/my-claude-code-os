package com.reviewscheduler.domain;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 노트 등록 시각으로부터 다음 복습일을 계산하는 순수 도메인 로직.
 *
 * Spring, JPA 등 어떤 프레임워크 클래스도 참조하지 않는다.
 * 그래서 이 클래스는 스프링 컨텍스트를 띄우지 않고도 순수 단위 테스트로 검증할 수 있다.
 *
 * 이번 범위에는 난이도 입력이나 복습 통과 처리가 없어서(문제 설명에 명시됨),
 * 등록 시점 하나에서 다음 복습일을 한 번만 계산하면 된다. 그래서 간격을
 * "등록일 + 고정 N일"이라는 가장 단순한 규칙으로 정했다. 나중에 난이도별
 * 간격이나 복습 이력에 따른 간격(에빙하우스식 스페이싱)이 필요해지면
 * 이 클래스 내부만 바꾸면 되고, 이 클래스를 사용하는 쪽(NoteService)은
 * 영향을 받지 않는다.
 */
public class NextReviewDateCalculator {

    /** 등록일로부터 최소 며칠 뒤에 복습해야 하는지. 기본값 1일. */
    private final int intervalDays;

    public NextReviewDateCalculator() {
        this(1);
    }

    public NextReviewDateCalculator(int intervalDays) {
        if (intervalDays < 1) {
            throw new IllegalArgumentException("intervalDays는 최소 1이어야 합니다: " + intervalDays);
        }
        this.intervalDays = intervalDays;
    }

    /**
     * 등록 시각을 받아 다음 복습일(날짜)을 계산한다.
     * 다음 복습일은 항상 등록 시각의 날짜보다 intervalDays일 이후다.
     */
    public LocalDate calculateNextReviewDate(LocalDateTime registeredAt) {
        if (registeredAt == null) {
            throw new IllegalArgumentException("registeredAt은 null일 수 없습니다");
        }
        return registeredAt.toLocalDate().plusDays(intervalDays);
    }
}
