package com.reviewscheduler.domain;

import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 순수 단위 테스트: Spring 컨텍스트를 전혀 띄우지 않는다(@SpringBootTest, @DataJpaTest 없음).
 * NoteDeletion은 프레임워크를 import하지 않는 순수 자바 클래스라서 new로 바로 검증할 수 있다.
 *
 * 여기서 잡는 것은 "삭제/되돌리기의 상태 전이 규칙"이다. DB에 실제로 반영되는가,
 * 목록 질의에서 걸러지는가는 NoteServiceTest·NoteHttpApiTest가 본다.
 */
class NoteDeletionTest {

    private static final LocalDateTime DELETED_AT = LocalDateTime.of(2026, 8, 30, 14, 0);

    @Test
    void 새로_만든_상태는_삭제되지_않은_상태다() {
        NoteDeletion deletion = NoteDeletion.alive();

        assertThat(deletion.isDeleted()).isFalse();
        assertThat(deletion.deletedAt()).isNull();
    }

    @Test
    void 삭제하면_삭제된_상태가_되고_삭제_시각이_기록된다() {
        NoteDeletion deleted = NoteDeletion.alive().delete(DELETED_AT);

        assertThat(deleted.isDeleted()).isTrue();
        assertThat(deleted.deletedAt()).isEqualTo(DELETED_AT);
    }

    @Test
    void 되돌리면_삭제되지_않은_상태로_돌아가고_삭제_시각이_비워진다() {
        NoteDeletion restored = NoteDeletion.alive().delete(DELETED_AT).restore();

        assertThat(restored.isDeleted()).isFalse();
        assertThat(restored.deletedAt()).isNull();
    }

    @Test
    void 저장된_deleted_at이_null이면_삭제되지_않은_상태로_복원된다() {
        // 이 컬럼이 생기기 전에 저장된 기존 노트들이 이 경로로 복원된다.
        assertThat(NoteDeletion.of(null).isDeleted()).isFalse();
        assertThat(NoteDeletion.of(DELETED_AT).isDeleted()).isTrue();
    }

    @Test
    void 이미_삭제된_것을_또_삭제해도_최초_삭제_시각이_바뀌지_않는다() {
        NoteDeletion deleted = NoteDeletion.alive().delete(DELETED_AT);

        NoteDeletion deletedAgain = deleted.delete(DELETED_AT.plusHours(3));

        assertThat(deletedAgain.deletedAt()).isEqualTo(DELETED_AT);
    }

    @Test
    void 삭제되지_않은_것을_되돌려도_그대로_살아_있는_상태다() {
        assertThat(NoteDeletion.alive().restore().isDeleted()).isFalse();
    }

    @Test
    void 상태를_바꿔도_원래_값은_그대로다() {
        // 불변이라는 전제가 깨지면(내부 필드를 고치는 구현으로 바뀌면) 삭제 한 번이
        // 다른 곳이 들고 있던 상태까지 함께 바꿔버린다.
        NoteDeletion alive = NoteDeletion.alive();

        alive.delete(DELETED_AT);

        assertThat(alive.isDeleted()).isFalse();
    }

    @Test
    void 삭제_시각이_null이면_예외를_던진다() {
        assertThatThrownBy(() -> NoteDeletion.alive().delete(null))
                .isInstanceOf(NullPointerException.class);
    }
}
