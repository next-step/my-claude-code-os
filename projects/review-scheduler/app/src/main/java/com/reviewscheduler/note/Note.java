package com.reviewscheduler.note;

import com.reviewscheduler.domain.NoteDeletion;
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
 * 같은 이유로 "삭제된 상태인가"라는 판정도 NoteDeletion에 위임한다.
 *
 * 삭제는 행을 지우는 물리 삭제가 아니라 deleted_at 컬럼을 채우는 soft delete다.
 * 그래서 삭제된 노트도 행은 그대로 남아 있고, 되돌리기는 그 컬럼을 비우는 것으로 끝난다.
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

    /**
     * 삭제 시각. null이면 삭제되지 않은(=살아 있는) 노트다.
     *
     * nullable이어야 한다 — 이 컬럼이 생기기 전에 저장된 기존 노트들은 이 값이 비어 있고,
     * 그 상태가 곧 "삭제되지 않음"을 뜻한다.
     */
    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;

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

    public LocalDateTime getDeletedAt() {
        return deletedAt;
    }

    public boolean isDeleted() {
        return deletion().isDeleted();
    }

    /**
     * 주어진 시각에 삭제한다(soft delete). 행을 지우지 않고 삭제 시각만 기록한다.
     * 이미 삭제된 노트를 다시 삭제해도 최초 삭제 시각은 바뀌지 않는다(NoteDeletion의 규칙).
     */
    public void delete(LocalDateTime deletedAt) {
        this.deletedAt = deletion().delete(deletedAt).deletedAt();
    }

    /**
     * 삭제를 되돌린다. 삭제 시각만 비운다 — nextReviewDate와 registeredAt은 건드리지 않는다.
     *
     * 여기서 다음 복습일을 다시 계산하지 않는 것이 수용 기준이다: 되돌린 노트의 다음
     * 복습일은 삭제 전과 동일해야 한다. 삭제/되돌리기는 "복습 일정"을 바꾸는 조작이
     * 아니라 "목록에 보이는가"만 바꾸는 조작이다.
     */
    public void restore() {
        this.deletedAt = deletion().restore().deletedAt();
    }

    private NoteDeletion deletion() {
        return NoteDeletion.of(deletedAt);
    }
}
