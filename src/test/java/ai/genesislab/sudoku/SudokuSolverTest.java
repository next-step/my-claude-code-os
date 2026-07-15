package ai.genesislab.sudoku;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;

import ai.genesislab.testutil.UtilityClasses;
import java.time.Duration;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * {@link SudokuSolver} 단위 테스트.
 *
 * <p>유일해 퍼즐 정상 풀이, 경계(거의 다 찬 보드·단 한 칸 빈 보드), 도메인 실패(해 없음·비유일),
 * 형식/모순 예외, 그리고 원본 불변(새 배열 반환)을 검증한다.</p>
 */
@DisplayName("SudokuSolver 단위 테스트")
class SudokuSolverTest {

    /** 유일해를 가지는 표준 난이도 퍼즐. */
    static int[][] uniquePuzzle() {
        return new int[][] {
                {5, 3, 0, 0, 7, 0, 0, 0, 0},
                {6, 0, 0, 1, 9, 5, 0, 0, 0},
                {0, 9, 8, 0, 0, 0, 0, 6, 0},
                {8, 0, 0, 0, 6, 0, 0, 0, 3},
                {4, 0, 0, 8, 0, 3, 0, 0, 1},
                {7, 0, 0, 0, 2, 0, 0, 0, 6},
                {0, 6, 0, 0, 0, 0, 2, 8, 0},
                {0, 0, 0, 4, 1, 9, 0, 0, 5},
                {0, 0, 0, 0, 8, 0, 0, 7, 9},
        };
    }

    /** {@link #uniquePuzzle()}의 유일한 해. */
    static int[][] uniqueSolution() {
        return new int[][] {
                {5, 3, 4, 6, 7, 8, 9, 1, 2},
                {6, 7, 2, 1, 9, 5, 3, 4, 8},
                {1, 9, 8, 3, 4, 2, 5, 6, 7},
                {8, 5, 9, 7, 6, 1, 4, 2, 3},
                {4, 2, 6, 8, 5, 3, 7, 9, 1},
                {7, 1, 3, 9, 2, 4, 8, 5, 6},
                {9, 6, 1, 5, 3, 7, 2, 8, 4},
                {2, 8, 7, 4, 1, 9, 6, 3, 5},
                {3, 4, 5, 2, 8, 6, 1, 7, 9},
        };
    }

    @Nested
    @DisplayName("정상 풀이 — 유일해")
    class HappyPath {

        @Test
        @DisplayName("정상: 유일해 퍼즐을 정확한 해로 푼다")
        void solve_uniquePuzzle_returnsExpectedSolution() {
            int[][] solution = SudokuSolver.solve(uniquePuzzle());
            assertArrayEquals(uniqueSolution(), solution);
        }

        @Test
        @DisplayName("정상: 해는 완성(빈칸 0개)이며 규칙을 만족한다")
        void solve_result_isCompleteAndValid() {
            int[][] solution = SudokuSolver.solve(uniquePuzzle());
            assertTrue(SudokuValidator.isComplete(solution));
        }
    }

    @Nested
    @DisplayName("경계 — 거의 다 찬 보드 / 단 한 칸 빈 보드")
    class Boundary {

        @Test
        @DisplayName("경계: 단 한 칸만 빈 보드를 채운다")
        void solve_singleEmptyCell_fillsIt() {
            int[][] puzzle = uniqueSolution();
            puzzle[2][3] = SudokuValidator.EMPTY; // 한 칸만 비운다
            int[][] solution = SudokuSolver.solve(puzzle);
            assertArrayEquals(uniqueSolution(), solution);
        }

        @Test
        @DisplayName("경계: 이미 완성된 유효 보드는 그대로 유일해로 반환한다")
        void solve_alreadyComplete_returnsSameBoard() {
            int[][] solved = uniqueSolution();
            int[][] solution = SudokuSolver.solve(solved);
            assertArrayEquals(uniqueSolution(), solution);
        }
    }

    @Nested
    @DisplayName("도메인 실패 — SudokuException(해 없음 / 비유일)")
    class DomainFailure {

        @Test
        @DisplayName("예외: 해가 없는 퍼즐은 SudokuException(NO_SOLUTION)")
        void solve_noSolution_throwsSudokuException() {
            // 형식·모순은 정상이지만 풀 수 없는 퍼즐.
            // 0번 행에 1~8을 배치하면 마지막 칸은 9여야 하나, 9번 열에 9를 둘 수 없게 막아 모순 없이 해를 제거한다.
            int[][] puzzle = new int[SudokuValidator.SIZE][SudokuValidator.SIZE];
            puzzle[0] = new int[] {1, 2, 3, 4, 5, 6, 7, 8, 0}; // (0,8)은 9가 되어야 함
            puzzle[1][8] = 9; // 같은 열(8)에 9를 미리 둬서 (0,8)=9를 불가능하게 만든다 → 해 없음
            SudokuException ex = assertThrows(SudokuException.class,
                    () -> SudokuSolver.solve(puzzle));
            assertEquals(SudokuSolver.NO_SOLUTION_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 전부 빈 보드는 해가 매우 많으므로 비유일 SudokuException")
        void solve_emptyBoard_throwsMultipleSolutions() {
            int[][] empty = new int[SudokuValidator.SIZE][SudokuValidator.SIZE];
            SudokuException ex = assertThrows(SudokuException.class,
                    () -> SudokuSolver.solve(empty));
            assertEquals(SudokuSolver.MULTIPLE_SOLUTIONS_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 해가 2개 이상인 퍼즐은 비유일 SudokuException")
        void solve_multipleSolutions_throwsSudokuException() {
            // 유일해 퍼즐에서 단서를 대거 제거해 해가 여러 개가 되도록 만든다.
            int[][] puzzle = uniquePuzzle();
            // 윗쪽 절반 단서를 지워 자유도를 크게 늘린다 → 해 다수.
            for (int r = 0; r < 5; r++) {
                for (int c = 0; c < SudokuValidator.SIZE; c++) {
                    puzzle[r][c] = SudokuValidator.EMPTY;
                }
            }
            SudokuException ex = assertThrows(SudokuException.class,
                    () -> SudokuSolver.solve(puzzle));
            assertEquals(SudokuSolver.MULTIPLE_SOLUTIONS_MESSAGE, ex.getMessage());
        }
    }

    @Nested
    @DisplayName("형식 / 모순 예외 — IllegalArgumentException")
    class IllegalInput {

        @Test
        @DisplayName("예외: null 보드는 IllegalArgumentException")
        void solve_nullBoard_throws() {
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> SudokuSolver.solve(null));
            assertEquals(SudokuValidator.NULL_BOARD_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 9x9가 아니면 IllegalArgumentException")
        void solve_wrongSize_throws() {
            int[][] board = new int[9][8]; // 9x8
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> SudokuSolver.solve(board));
            assertEquals(SudokuValidator.INVALID_SIZE_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 값 범위(0~9) 밖이면 IllegalArgumentException")
        void solve_valueOutOfRange_throws() {
            int[][] puzzle = uniquePuzzle();
            puzzle[0][2] = 99;
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> SudokuSolver.solve(puzzle));
            assertEquals(SudokuValidator.VALUE_OUT_OF_RANGE_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 이미 모순(중복)인 보드는 풀이 전에 IllegalArgumentException")
        void solve_contradictoryBoard_throws() {
            int[][] puzzle = uniquePuzzle();
            // 같은 행에 중복을 심어 모순 보드를 만든다.
            puzzle[0][2] = 5; // (0,0)이 이미 5 → 같은 행 중복
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> SudokuSolver.solve(puzzle));
            assertEquals(SudokuSolver.CONTRADICTORY_BOARD_MESSAGE, ex.getMessage());
        }
    }

    @Nested
    @DisplayName("원본 불변 — 새 배열 반환")
    class Immutability {

        @Test
        @DisplayName("solve는 입력 퍼즐을 변형하지 않고 새 배열을 반환한다")
        void solve_doesNotMutateInput_returnsNewArray() {
            int[][] puzzle = uniquePuzzle();
            int[][] snapshot = new int[SudokuValidator.SIZE][];
            for (int r = 0; r < SudokuValidator.SIZE; r++) {
                snapshot[r] = puzzle[r].clone();
            }

            int[][] solution = SudokuSolver.solve(puzzle);

            // 입력은 그대로(빈칸 포함) 보존된다.
            for (int r = 0; r < SudokuValidator.SIZE; r++) {
                assertArrayEquals(snapshot[r], puzzle[r]);
            }
            // 반환 배열은 입력과 다른 최상위 인스턴스다.
            assertTrue(solution != puzzle, "최상위 배열은 새 인스턴스여야 한다");
            // 그리고 각 행 배열도 입력 행과 별개 인스턴스여야 한다(얕은 복사 회귀 방지).
            for (int r = 0; r < SudokuValidator.SIZE; r++) {
                assertTrue(solution[r] != puzzle[r],
                        "행 " + r + " 배열은 입력 행과 별개 인스턴스여야 한다(deep copy)");
            }
        }
    }

    @Nested
    @DisplayName("탐색 견고성 — MRV 최적화 / 노드 가드")
    class SearchRobustness {

        /**
         * 단서가 17개뿐인 유효한 <b>유일해</b> 퍼즐(최소 단서 스도쿠).
         *
         * <p>단서가 희박해 MRV 없이 첫 빈칸부터 탐색하면 트리가 폭발하기 쉽지만, MRV(후보 최소 칸 우선)
         * 를 적용하면 노드 가드({@link SudokuSolver#MAX_SEARCH_NODES})에 한참 못 미치는 노드만
         * 방문하고 즉시 풀린다.</p>
         */
        static int[][] sparseUniquePuzzle() {
            return new int[][] {
                    {0, 0, 0, 0, 0, 0, 0, 1, 0},
                    {4, 0, 0, 0, 0, 0, 0, 0, 0},
                    {0, 2, 0, 0, 0, 0, 0, 0, 0},
                    {0, 0, 0, 0, 5, 0, 4, 0, 7},
                    {0, 0, 8, 0, 0, 0, 3, 0, 0},
                    {0, 0, 1, 0, 9, 0, 0, 0, 0},
                    {3, 0, 0, 4, 0, 0, 2, 0, 0},
                    {0, 5, 0, 1, 0, 0, 0, 0, 0},
                    {0, 0, 0, 8, 0, 6, 0, 0, 0},
            };
        }

        @Test
        @DisplayName("MRV: 단서 17개의 희소 유일해 퍼즐을 가드 한참 이내에 즉시 푼다")
        void solve_sparseUniquePuzzle_solvesQuicklyWithinGuard() {
            // MRV가 동작하지 않으면 사실상 hang(가드 상한까지 탐색)할 입력이다.
            // 넉넉한 시간 상한(2초) 안에 끝나면 MRV가 트리를 충분히 줄였다는 의미다.
            int[][] solution = assertTimeoutPreemptively(Duration.ofSeconds(2),
                    () -> SudokuSolver.solve(sparseUniquePuzzle()));

            // 정상 풀이 계약: 완성·유효한 유일해이며, 원본 단서를 보존한다.
            assertTrue(SudokuValidator.isComplete(solution), "희소 퍼즐의 해도 완성·유효해야 한다");
            int[][] puzzle = sparseUniquePuzzle();
            for (int r = 0; r < SudokuValidator.SIZE; r++) {
                for (int c = 0; c < SudokuValidator.SIZE; c++) {
                    if (puzzle[r][c] != SudokuValidator.EMPTY) {
                        assertEquals(puzzle[r][c], solution[r][c],
                                "단서 (" + r + "," + c + ")는 해에서도 보존되어야 한다");
                    }
                }
            }
        }

        @Test
        @DisplayName("가드 계약: 노드 상한·전용 메시지 상수가 노출되고 NO_SOLUTION/MULTIPLE과 구분된다")
        void searchGuard_constantsAreExposedAndDistinct() {
            // 형식 문제가 아니라 풀이 자원 한계용 메시지/상수가 public 으로 노출되어야 한다(계약 고정).
            // 상한 상수는 양수여야 하며, 메시지는 다른 도메인 실패 메시지와 구분되어야 한다.
            assertTrue(SudokuSolver.MAX_SEARCH_NODES > 0, "노드 상한은 양수여야 한다");
            assertNotEquals(SudokuSolver.SEARCH_LIMIT_EXCEEDED_MESSAGE, SudokuSolver.NO_SOLUTION_MESSAGE);
            assertNotEquals(SudokuSolver.SEARCH_LIMIT_EXCEEDED_MESSAGE, SudokuSolver.MULTIPLE_SOLUTIONS_MESSAGE);

            // 가드 동작 설명(계약): 백트래킹이 MAX_SEARCH_NODES 노드를 초과하면
            // IllegalArgumentException 이 아니라 SudokuException(SEARCH_LIMIT_EXCEEDED_MESSAGE)을 던진다.
            // MRV 적용 후 정상 9x9 유일해 퍼즐은 이 상한에 한참 못 미치므로 가드에 걸리지 않는다.
        }

        @Test
        @DisplayName("가드: 표준 유일해 퍼즐은 노드 가드에 걸리지 않고 정상 해를 반환한다")
        void solve_normalUniquePuzzle_doesNotTripGuard() {
            // 정상 퍼즐이 SEARCH_LIMIT_EXCEEDED 로 오인되지 않음을 고정한다(false positive 방지).
            int[][] solution = SudokuSolver.solve(uniquePuzzle());
            assertArrayEquals(uniqueSolution(), solution);
        }

        /**
         * 형식·모순은 정상이지만 <b>해가 없고</b>, 백트래킹 방문 노드가
         * {@link SudokuSolver#MAX_SEARCH_NODES}(2,000,000)를 초과하도록 구성된 병리적 희소 보드.
         *
         * <p>MRV로도 조기에 모순을 못 찾고 탐색 트리가 폭발하는 입력이라, 노드 가드가 없으면 사실상
         * hang한다. 이 보드는 결정적으로 노드 예산을 소진시켜 방어적 가드
         * ({@link SudokuSolver#SEARCH_LIMIT_EXCEEDED_MESSAGE})가 발동되게 한다.</p>
         */
        static int[][] guardBustingPuzzle() {
            return new int[][] {
                    {0, 0, 0, 0, 0, 0, 0, 0, 0},
                    {5, 0, 0, 0, 0, 0, 0, 0, 0},
                    {0, 0, 0, 8, 0, 0, 2, 0, 0},
                    {0, 0, 1, 0, 0, 6, 0, 0, 0},
                    {0, 6, 0, 0, 0, 2, 0, 5, 0},
                    {3, 9, 0, 0, 0, 0, 0, 0, 0},
                    {9, 0, 0, 0, 8, 0, 0, 0, 0},
                    {0, 0, 0, 0, 6, 0, 0, 0, 0},
                    {0, 0, 0, 0, 0, 0, 0, 0, 0},
            };
        }

        @Test
        @DisplayName("가드: 탐색 노드가 상한을 초과하는 병리적 입력은 SudokuException(SEARCH_LIMIT_EXCEEDED)")
        void solve_searchExplodesBeyondNodeLimit_throwsSearchLimitExceeded() {
            // 노드 가드가 발동하는 실제 경로(--nodeBudget[0] < 0 → throw)를 실행한다.
            // 이 입력은 형식·모순 정상(→ IllegalArgumentException 아님)이며 해가 없지만, 트리가 폭발해
            // 2,000,000 노드 예산을 소진하므로 도메인 실패가 아닌 자원 한계로 분류되어야 한다.
            // 넉넉한 상한(30초)은 회귀로 가드가 사라져 hang하는 경우를 잡기 위한 안전망이다(정상 시 ~2초).
            SudokuException ex = assertThrows(SudokuException.class,
                    () -> assertTimeoutPreemptively(Duration.ofSeconds(30),
                            () -> SudokuSolver.solve(guardBustingPuzzle())));
            assertEquals(SudokuSolver.SEARCH_LIMIT_EXCEEDED_MESSAGE, ex.getMessage());
        }
    }

    @Test
    @DisplayName("설계: 유틸리티 클래스는 인스턴스화할 수 없다")
    void sudokuSolver_cannotBeInstantiated() throws Exception {
        UtilityClasses.assertNotInstantiable(SudokuSolver.class);
    }
}
