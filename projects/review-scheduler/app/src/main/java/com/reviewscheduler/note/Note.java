package com.reviewscheduler.note;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Objects;

/**
 * 학습 기록 한 건. "등록 시각"과 "다음 복습일"을 각각 하나씩 갖는다.
 *
 * 영속성(JPA)과 결합된 클래스라서 domain 패키지가 아니라 note 패키지에 둔다.
 * 실제 복습일 "계산" 로직은 여기 두지 않고 NextReviewDateCalculator에 위임한다 —
 * 그래야 계산 규칙만 따로 프레임워크 없이 테스트할 수 있다.
 */
@Entity
public class Note {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String content;

    @Column(nullable = false, updatable = false)
    private LocalDateTime registeredAt;

    @Column(nullable = false)
    private LocalDate nextReviewDate;

    protected Note() {
        // JPA 전용
    }

    public Note(String content, LocalDateTime registeredAt, LocalDate nextReviewDate) {
        this.content = Objects.requireNonNull(content, "content는 null일 수 없습니다");
        this.registeredAt = Objects.requireNonNull(registeredAt, "registeredAt은 null일 수 없습니다");
        this.nextReviewDate = Objects.requireNonNull(nextReviewDate, "nextReviewDate는 null일 수 없습니다");
    }

    public Long getId() {
        return id;
    }

    public String getContent() {
        return content;
    }

    public LocalDateTime getRegisteredAt() {
        return registeredAt;
    }

    public LocalDate getNextReviewDate() {
        return nextReviewDate;
    }
}
