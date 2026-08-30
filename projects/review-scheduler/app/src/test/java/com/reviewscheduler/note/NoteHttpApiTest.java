package com.reviewscheduler.note;

import com.jayway.jsonpath.JsonPath;
import com.reviewscheduler.domain.NextReviewDateCalculator;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 이번 작업의 승인된 수용 기준 두 가지를 실제 HTTP 계층까지 요청을 태워서 검증한다.
 *
 * 1) "노트 등록에 성공하면 응답 본문에 등록된 노트의 다음 복습일이 포함된다."
 * 2) "HTTP 요청으로 지금 복습할 노트 목록을 조회하면 응답에 각 노트의 다음 복습일이
 *    포함된다."
 *
 * 독립 리뷰 지적 반영: 예전 버전은 "다음 복습일 필드가 비어있지 않다"만 확인해서,
 * 응답 조립부가 항상 고정된 엉뚱한 날짜(예: 1999-01-01)를 돌려줘도 통과했다. 그래서
 * 지금은 두 테스트 모두 "값 자체"를 확인한다: 등록 테스트는 같은 응답에 실린
 * registeredAt으로부터 NextReviewDateCalculator(도메인 규칙, 프레임워크 의존 없음)가
 * 계산한 값과 응답의 nextReviewDate가 정확히 같은지 비교하고, 목록 테스트는 서로 다른
 * 다음 복습일을 가진 노트 두 건을 만들어 응답 배열의 각 항목이 각자 자신의 값을 담고
 * 있는지(첫 항목만 보지 않고) 확인한다.
 *
 * @SpringBootTest + @AutoConfigureMockMvc로 DispatcherServlet까지 포함한 실제 웹
 * 계층을 띄우되, 소켓을 여는 실제 포트 대신 MockMvc로 서블릿 요청/응답을 시뮬레이션한다.
 * "HTTP 응답 바디에 다음 복습일이 정확한 값으로 직렬화되어 담기는가"는 컨트롤러의 응답
 * 조립과 JSON 직렬화 결과를 확인하는 것이라 순수 단위 테스트로는 검증할 수 없다 — 다음
 * 복습일을 "계산"하는 규칙 자체는 여전히 NextReviewDateCalculatorTest가 프레임워크
 * 없이 검증하고 있으므로, 이 클래스가 통합 테스트라는 사실이 그 원칙과 충돌하지 않는다.
 *
 * 로컬 실사용 데이터 파일(./data/review-scheduler)을 이 테스트가 건드리지 않도록,
 * 이 클래스 전용의 격리된 인메모리 H2로 데이터소스를 오버라이드한다.
 */
@SpringBootTest
@AutoConfigureMockMvc
class NoteHttpApiTest {

    @DynamicPropertySource
    static void overrideDatasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url",
                () -> "jdbc:h2:mem:note-http-api-test-" + System.nanoTime() + ";DB_CLOSE_DELAY=-1");
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private NoteRepository noteRepository;

    /** 컨트롤러/서비스가 실제로 쓰는 것과 같은 도메인 규칙. 프레임워크 의존이 없어 테스트에서 그대로 new로 쓸 수 있다. */
    private final NextReviewDateCalculator nextReviewDateCalculator = new NextReviewDateCalculator();

    @Test
    void 노트_등록에_성공하면_응답_본문에_등록된_노트의_다음_복습일이_포함된다() throws Exception {
        // Jackson 버전 차이(패키지가 tools.jackson.* 로 옮겨간 버전 포함)에 테스트가
        // 얽히지 않도록, ObjectMapper 없이 요청 바디를 직접 문자열로 만든다.
        String requestBody = "{\"content\":\"스프링 부트로 HTTP API 만들기\"}";

        String responseBody = mockMvc.perform(post("/notes")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(requestBody))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);

        String registeredAt = JsonPath.read(responseBody, "$.registeredAt");
        String nextReviewDate = JsonPath.read(responseBody, "$.nextReviewDate");

        // "비어있지 않은 무언가"가 아니라, 이 응답 자신의 registeredAt으로부터 도메인
        // 규칙이 계산해내는 값과 정확히 같은지를 비교한다. 응답 조립부가 registeredAt과
        // 무관한 고정 날짜를 돌려주면(예: 1999-01-01) 이 비교는 실패한다.
        LocalDate expectedNextReviewDate =
                nextReviewDateCalculator.calculateNextReviewDate(LocalDateTime.parse(registeredAt));
        assertThat(LocalDate.parse(nextReviewDate)).isEqualTo(expectedNextReviewDate);
    }

    @Test
    void 지금_복습할_노트_목록을_HTTP로_조회하면_각_노트의_다음_복습일이_포함된다() throws Exception {
        // 노트를 한 건만 만들고 목록의 첫 항목만 보면, 두 번째 이후 항목에서 값이
        // 누락되거나 엉뚱해도 잡아내지 못한다. 그래서 서로 다른(둘 다 이미 지난)
        // 다음 복습일을 가진 노트 두 건을 만들고, 응답 배열의 모든 항목을 그 노트의
        // content로 찾아 각자의 nextReviewDate가 맞는지 확인한다.
        //
        // "등록 후 즉시 복습 대상"은 아니다(최소 간격이 1일이라 방금 등록한 노트는
        // 오늘 목록에 안 뜬다). 그래서 리포지토리에 다음 복습일이 이미 지난 노트를
        // 직접 저장한다 — NoteServiceTest가 쓰는 것과 같은 방식이다.
        String uniqueSuffix = String.valueOf(System.nanoTime());
        String contentA = "복습 대상 노트 A-" + uniqueSuffix;
        String contentB = "복습 대상 노트 B-" + uniqueSuffix;
        LocalDate nextReviewDateA = LocalDate.now().minusDays(3);
        LocalDate nextReviewDateB = LocalDate.now().minusDays(1);

        noteRepository.save(new Note(contentA, LocalDateTime.now(), nextReviewDateA));
        noteRepository.save(new Note(contentB, LocalDateTime.now(), nextReviewDateB));

        String responseBody = mockMvc.perform(get("/notes/due"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);

        List<String> contents = JsonPath.read(responseBody, "$[*].content");
        List<String> nextReviewDates = JsonPath.read(responseBody, "$[*].nextReviewDate");

        assertThat(contents).contains(contentA, contentB);
        assertThat(nextReviewDates)
                .as("배열의 모든 항목에 nextReviewDate가 채워져 있어야 한다")
                .doesNotContainNull();

        int indexA = contents.indexOf(contentA);
        int indexB = contents.indexOf(contentB);
        assertThat(nextReviewDates.get(indexA)).isEqualTo(nextReviewDateA.toString());
        assertThat(nextReviewDates.get(indexB)).isEqualTo(nextReviewDateB.toString());
    }
}
