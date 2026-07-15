package ai.genesislab.sudoku;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * {@link SudokuException} 단위 테스트.
 *
 * <p>모듈 전용 비검사 예외의 두 생성자를 직접 검증한다. 특히 {@code (String, Throwable)}
 * 생성자가 <b>원인(cause)을 항상 보존</b>하는지 확인한다(DECISIONS A: 도메인 실패는 전용 예외로,
 * JDK 검사 예외를 래핑할 때 원인 보존).</p>
 */
@DisplayName("SudokuException 단위 테스트")
class SudokuExceptionTest {

    @Nested
    @DisplayName("생성자 — 메시지만")
    class MessageOnly {

        @Test
        @DisplayName("정상: 메시지를 보존하고 원인은 없다")
        void messageConstructor_preservesMessage_withoutCause() {
            SudokuException ex = new SudokuException("boom");

            assertEquals("boom", ex.getMessage());
            assertNull(ex.getCause(), "메시지 전용 생성자는 원인이 없어야 한다");
        }

        @Test
        @DisplayName("설계: RuntimeException(비검사 예외)이다")
        void sudokuException_isUnchecked() {
            assertTrue(RuntimeException.class.isAssignableFrom(SudokuException.class),
                    "SudokuException은 비검사(unchecked) 예외여야 한다");
        }
    }

    @Nested
    @DisplayName("생성자 — 메시지 + 원인")
    class MessageAndCause {

        @Test
        @DisplayName("정상: 메시지와 원인(cause)을 모두 보존한다")
        void causeConstructor_preservesMessageAndCause() {
            Throwable cause = new IllegalStateException("root");

            SudokuException ex = new SudokuException("wrapped", cause);

            assertEquals("wrapped", ex.getMessage());
            assertSame(cause, ex.getCause(), "원인(cause)은 그대로 보존되어야 한다");
        }

        @Test
        @DisplayName("경계: 원인이 null이어도 생성되며 원인은 null로 보존된다")
        void causeConstructor_nullCause_isPreservedAsNull() {
            SudokuException ex = new SudokuException("no-cause", null);

            assertEquals("no-cause", ex.getMessage());
            assertNull(ex.getCause());
        }
    }
}
