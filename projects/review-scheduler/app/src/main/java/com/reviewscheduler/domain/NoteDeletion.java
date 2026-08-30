package com.reviewscheduler.domain;

import java.time.LocalDateTime;
import java.util.Objects;

/**
 * 노트가 "삭제된 상태인가"를 나타내는 순수 도메인 값. 삭제·되돌리기의 상태 전이 규칙이
 * 여기 한 곳에만 있다.
 *
 * NextReviewDateCalculator와 같은 이유로 domain 패키지에 둔다 — Spring, JPA 등 어떤
 * 프레임워크 클래스도 참조하지 않으므로 스프링 컨텍스트를 띄우지 않고 new로 바로 검증할
 * 수 있다. Note는 JPA 엔티티라 프레임워크와 묶여 있으므로, "삭제 상태 판정"이라는 계산은
 * 엔티티 안에 흩어놓지 않고 이 클래스에 위임한다.
 *
 * 삭제는 물리 삭제가 아니라 soft delete다: 지운다는 것은 행을 없애는 것이 아니라
 * "삭제 시각"을 기록하는 것이고, 되돌린다는 것은 그 시각을 지우는 것이다.
 * 그래서 이 값은 {@code deletedAt} 하나로 표현된다 — null이면 살아 있는 상태다.
 *
 * 불변(immutable)이다. 상태를 바꾸는 메서드는 자기 자신을 고치지 않고 새 값을 돌려준다.
 */
public final class NoteDeletion {

    /** 삭제되지 않은 상태. deletedAt이 없다는 것이 곧 살아 있다는 뜻이다. */
    private static final NoteDeletion ALIVE = new NoteDeletion(null);

    private final LocalDateTime deletedAt;

    private NoteDeletion(LocalDateTime deletedAt) {
        this.deletedAt = deletedAt;
    }

    public static NoteDeletion alive() {
        return ALIVE;
    }

    /** 저장된 deleted_at 값으로부터 상태를 복원한다. null이면 살아 있는 상태다. */
    public static NoteDeletion of(LocalDateTime deletedAt) {
        return deletedAt == null ? ALIVE : new NoteDeletion(deletedAt);
    }

    public boolean isDeleted() {
        return deletedAt != null;
    }

    /** 삭제 시각. 삭제되지 않았으면 null이다. */
    public LocalDateTime deletedAt() {
        return deletedAt;
    }

    /**
     * 주어진 시각에 삭제한다.
     *
     * 이미 삭제된 것을 또 삭제해도 최초 삭제 시각을 덮어쓰지 않는다. 덮어쓰면 같은 요청을
     * 두 번 보냈다는 이유만으로 "언제 지웠는가"라는 기록이 바뀌기 때문이다.
     */
    public NoteDeletion delete(LocalDateTime now) {
        Objects.requireNonNull(now, "삭제 시각은 null일 수 없습니다");
        return isDeleted() ? this : new NoteDeletion(now);
    }

    /**
     * 삭제를 되돌린다. 되돌린 결과는 삭제 시각이 없는 상태 하나뿐이다.
     *
     * 이 값은 삭제 여부만 안다 — 복습일이나 등록 시각은 애초에 담고 있지 않으므로
     * 되돌리기가 그 값들을 건드릴 수 있는 경로 자체가 없다.
     */
    public NoteDeletion restore() {
        return ALIVE;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof NoteDeletion that)) {
            return false;
        }
        return Objects.equals(deletedAt, that.deletedAt);
    }

    @Override
    public int hashCode() {
        return Objects.hash(deletedAt);
    }

    @Override
    public String toString() {
        return isDeleted() ? "NoteDeletion[deletedAt=" + deletedAt + "]" : "NoteDeletion[alive]";
    }
}
