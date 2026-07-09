package com.habit.tracker.web;

import com.habit.tracker.service.RoutineService;
import com.habit.tracker.service.UserStatsService;
import com.habit.tracker.service.dto.RoutineForm;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.model;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.view;

/**
 * HomeController 통합 테스트
 *
 * - H2 인메모리 DB 사용 (src/test/resources/application.yml)
 * - @Transactional: 각 테스트 종료 후 자동 롤백 → 테스트 간 격리
 * - @BeforeEach 에서 공통 루틴 데이터를 설정
 *
 * 검증 범위:
 *   GET /         — 오늘 루틴 목록 + 완료율
 *   POST /check   — 체크 토글 후 리다이렉트
 *   GET /stats    — 7일/30일 통계
 *   GET /history  — 날짜별 루틴 이력
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class HomeControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private RoutineService routineService;

    @Autowired
    private UserStatsService userStatsService;

    /** 각 테스트에서 사용하는 루틴 ID */
    private Long routineId;

    @BeforeEach
    void setUp() {
        RoutineForm form = new RoutineForm();
        form.setName("테스트 루틴");
        form.setDescription("통합 테스트용");
        // 모든 요일 — 어떤 날에 테스트해도 오늘 루틴에 포함된다
        form.setDays(List.of("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"));

        routineId = routineService.createRoutine(form).getId();
    }

    // ── GET / ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("GET /: HTTP 200 + index 뷰 반환, 모델에 todayRoutines/today/completionRate 포함")
    void index_성공() throws Exception {
        mockMvc.perform(get("/"))
                .andExpect(status().isOk())
                .andExpect(view().name("index"))
                .andExpect(model().attributeExists("todayRoutines"))
                .andExpect(model().attributeExists("today"))
                .andExpect(model().attributeExists("completionRate"))
                .andExpect(model().attributeExists("currentXp"))
                .andExpect(model().attributeExists("xpLevelRange"));
    }

    @Test
    @DisplayName("GET /: 루틴이 한 개도 없을 때도 정상 응답한다")
    void index_루틴없어도정상응답() throws Exception {
        // given — setUp 에서 생성한 루틴을 비활성화
        routineService.deactivateRoutine(routineId);

        // when & then
        mockMvc.perform(get("/"))
                .andExpect(status().isOk())
                .andExpect(view().name("index"));
    }

    // ── POST /check/{routineId} ───────────────────────────────────────────

    @Test
    @DisplayName("POST /check/{id}: returnDate 없으면 체크 토글 후 / 로 리다이렉트한다")
    void toggleCheck_returnDate없으면홈리다이렉트() throws Exception {
        mockMvc.perform(post("/check/" + routineId))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/"));
    }

    @Test
    @DisplayName("POST /check/{id}: 동일 루틴을 두 번 토글하면 완료 → 미완료로 전환된다 (토글 왕복)")
    void toggleCheck_두번토글하면미완료로전환() throws Exception {
        // given — 첫 번째 토글: 미완료 → 완료
        mockMvc.perform(post("/check/" + routineId));

        // when — 두 번째 토글: 완료 → 미완료
        mockMvc.perform(post("/check/" + routineId))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/"));
    }

    @Test
    @DisplayName("POST /check/{id}: returnDate 파라미터가 있으면 히스토리 페이지로 리다이렉트한다")
    void toggleCheck_returnDate있으면히스토리리다이렉트() throws Exception {
        mockMvc.perform(post("/check/" + routineId)
                        .param("returnDate", "2024-01-01"))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/history?date=2024-01-01"));
    }

    // ── GET /stats ────────────────────────────────────────────────────────

    @Test
    @DisplayName("GET /stats: HTTP 200 + stats/index 뷰, 모델에 rates7/rates30/today/hasActiveRoutines 포함")
    void stats_성공() throws Exception {
        mockMvc.perform(get("/stats"))
                .andExpect(status().isOk())
                .andExpect(view().name("stats/index"))
                .andExpect(model().attributeExists("rates7"))
                .andExpect(model().attributeExists("rates30"))
                .andExpect(model().attributeExists("today"))
                .andExpect(model().attributeExists("hasActiveRoutines"));
    }

    // ── GET /history ──────────────────────────────────────────────────────

    @Test
    @DisplayName("GET /history?date=2024-01-01: HTTP 200 + history/index 뷰, 모델에 target/routines/prev/next/isToday/isFuture 포함")
    void history_특정날짜조회성공() throws Exception {
        mockMvc.perform(get("/history").param("date", "2024-01-01"))
                .andExpect(status().isOk())
                .andExpect(view().name("history/index"))
                .andExpect(model().attributeExists("target"))
                .andExpect(model().attributeExists("routines"))
                .andExpect(model().attributeExists("prev"))
                .andExpect(model().attributeExists("next"))
                .andExpect(model().attributeExists("isToday"))
                .andExpect(model().attributeExists("isFuture"));
    }

    @Test
    @DisplayName("GET /history?date=미래날짜: isFuture=true 를 모델에 포함한다 — BUG-05")
    void history_미래날짜이면_isFuture_true() throws Exception {
        String futureDate = LocalDate.now().plusDays(1).toString();
        mockMvc.perform(get("/history").param("date", futureDate))
                .andExpect(status().isOk())
                .andExpect(model().attribute("isFuture", true));
    }

    @Test
    @DisplayName("GET /history?date=과거날짜: isFuture=false 를 모델에 포함한다 — BUG-05")
    void history_과거날짜이면_isFuture_false() throws Exception {
        mockMvc.perform(get("/history").param("date", "2024-01-01"))
                .andExpect(status().isOk())
                .andExpect(model().attribute("isFuture", false));
    }

    @Test
    @DisplayName("GET /history: date 파라미터 없으면 오늘 날짜를 target 으로 사용한다")
    void history_날짜없으면오늘기준() throws Exception {
        mockMvc.perform(get("/history"))
                .andExpect(status().isOk())
                .andExpect(view().name("history/index"))
                .andExpect(model().attributeExists("target"));
    }

    // ── POST /check/{routineId} — 레벨업 시나리오 ─────────────────────────────

    @Test
    @DisplayName("POST /check/{id}: 체크 완료로 레벨업 발생 시 플래시 속성에 레벨 정보를 담아 / 로 리다이렉트한다")
    void toggleCheck_레벨업발생시_플래시속성전달() throws Exception {
        // given — 레벨업 직전 XP 상태 만들기
        // SPROUT(0XP) → SAPLING(200XP) 레벨업을 유발하기 위해 190XP 를 미리 적립한다.
        // 루틴 체크 시 +10XP 가 추가되면 200XP 가 되어 레벨업이 발생한다.
        userStatsService.awardXp(190);

        // when & then — 체크 후 / 로 리다이렉트되고 플래시 속성이 포함된다
        mockMvc.perform(post("/check/" + routineId))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/"));
    }

    @Test
    @DisplayName("POST /check/{id}: 레벨업 없이 체크 완료 시 플래시 속성 없이 / 로 리다이렉트한다")
    void toggleCheck_레벨업없을때_기본리다이렉트() throws Exception {
        // given — XP 가 낮아 레벨업이 발생하지 않는 상태 (기본값 0 XP)

        // when & then — 체크 후 / 로 리다이렉트
        mockMvc.perform(post("/check/" + routineId))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/"));
    }

    @Test
    @DisplayName("POST /check/{id}: returnDate 있을 때 레벨업이 발생해도 플래시 속성 없이 히스토리로 리다이렉트한다")
    void toggleCheck_returnDate있으면_레벨업이어도_히스토리리다이렉트() throws Exception {
        // given — 레벨업 직전 XP 상태
        userStatsService.awardXp(190);

        // when & then — returnDate 가 있으면 레벨업과 무관하게 히스토리로 리다이렉트
        mockMvc.perform(post("/check/" + routineId)
                        .param("returnDate", "2024-01-01"))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/history?date=2024-01-01"));
    }
}
