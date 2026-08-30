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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 승인된 수용 기준을 실제 HTTP 계층까지 요청을 태워서 검증한다.
 *
 * 이번 작업(삭제/되돌리기)의 기준 세 가지가 여기 있어야 하는 이유: 사람이 이 앱을 쓰는
 * 통로는 HTTP 하나뿐이라, 서비스 계층에서만 통과하는 기능은 "만들어졌지만 부를 수 없는"
 * 상태다. NoteServiceTest가 저장·조회 규칙을 보는 것과 별개로, 여기서는 실제로 호출
 * 가능한 경로·메서드·상태 코드가 붙어 있는지를 본다.
 *
 * 이전 작업의 수용 기준 두 가지도 그대로 남겨 검증한다.
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

    @Test
    void 복습_목록에_있던_노트를_HTTP로_삭제하면_그_노트는_목록에서_제외된다() throws Exception {
        // 삭제 대상 말고 다른 노트도 하나 둔다. 삭제가 목록 전체를 비워버리는 구현이어도
        // "삭제한 노트가 없다"만 확인하면 통과하기 때문이다.
        String suffix = String.valueOf(System.nanoTime());
        String targetContent = "HTTP로 삭제할 노트-" + suffix;
        String survivorContent = "삭제와 무관한 노트-" + suffix;
        Long targetId = saveDueNote(targetContent, LocalDate.now().minusDays(2));
        saveDueNote(survivorContent, LocalDate.now().minusDays(1));
        assertThat(dueContents()).contains(targetContent, survivorContent);

        mockMvc.perform(delete("/notes/{id}", targetId))
                .andExpect(status().isOk());

        assertThat(dueContents())
                .doesNotContain(targetContent)
                .contains(survivorContent);
    }

    @Test
    void HTTP로_삭제한_노트를_되돌리면_목록에_다시_포함되고_다음_복습일이_삭제_전과_같다() throws Exception {
        // 수용 기준 2와 3을 한 흐름에서 본다. 되돌리기가 다음 복습일을 오늘 기준으로 다시
        // 계산하는 구현이라면 목록에는 다시 들어오더라도(기준 2 통과) 날짜가 달라져
        // 기준 3에서 걸린다. 그래서 "다시 들어왔는가"와 "값이 같은가"를 함께 단언한다.
        String suffix = String.valueOf(System.nanoTime());
        String content = "삭제했다 되돌릴 노트-" + suffix;
        LocalDate nextReviewDateBeforeDelete = LocalDate.now().minusDays(5);
        Long noteId = saveDueNote(content, nextReviewDateBeforeDelete);

        String deleteResponse = mockMvc.perform(delete("/notes/{id}", noteId))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat((String) JsonPath.read(deleteResponse, "$.deletedAt"))
                .as("삭제 응답에는 삭제 시각이 채워져 있어야 한다")
                .isNotNull();
        assertThat(dueContents()).doesNotContain(content);

        String restoreResponse = mockMvc.perform(post("/notes/{id}/restore", noteId))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);

        assertThat((String) JsonPath.read(restoreResponse, "$.deletedAt"))
                .as("되돌린 노트에는 삭제 시각이 남아 있으면 안 된다")
                .isNull();
        assertThat((String) JsonPath.read(restoreResponse, "$.nextReviewDate"))
                .isEqualTo(nextReviewDateBeforeDelete.toString());

        // 응답 본문만이 아니라 실제 목록 조회에서도 같은 값으로 돌아와야 한다.
        String dueBody = dueResponseBody();
        List<String> contents = JsonPath.read(dueBody, "$[*].content");
        List<String> nextReviewDates = JsonPath.read(dueBody, "$[*].nextReviewDate");
        assertThat(contents).contains(content);
        assertThat(nextReviewDates.get(contents.indexOf(content)))
                .isEqualTo(nextReviewDateBeforeDelete.toString());
    }

    @Test
    void 삭제는_행을_지우지_않으므로_삭제한_노트도_HTTP로_되돌릴_수_있다() throws Exception {
        // 사람이 정한 제약(soft delete)이 HTTP 경로에서도 지켜지는지 본다. 물리 삭제라면
        // 되돌리기 요청이 404가 되어 여기서 걸린다.
        Long noteId = saveDueNote("물리 삭제였다면 되돌릴 수 없는 노트-" + System.nanoTime(),
                LocalDate.now().minusDays(1));

        mockMvc.perform(delete("/notes/{id}", noteId)).andExpect(status().isOk());

        mockMvc.perform(post("/notes/{id}/restore", noteId)).andExpect(status().isOk());
        assertThat(noteRepository.findById(noteId)).isPresent();
    }

    @Test
    void 없는_노트를_삭제하거나_되돌리려_하면_404로_답한다() throws Exception {
        mockMvc.perform(delete("/notes/{id}", 999_999L)).andExpect(status().isNotFound());
        mockMvc.perform(post("/notes/{id}/restore", 999_999L)).andExpect(status().isNotFound());
    }

    /**
     * 다음 복습일이 이미 지난 노트를 저장해 "지금 복습할 목록"에 뜨게 만든다.
     * 방금 등록한 노트는 최소 간격이 1일이라 오늘 목록에 뜨지 않으므로, 등록 API 대신
     * 리포지토리에 직접 저장한다(다른 테스트들이 쓰는 것과 같은 방식).
     */
    private Long saveDueNote(String content, LocalDate nextReviewDate) {
        return noteRepository.save(new Note(content, LocalDateTime.now(), nextReviewDate)).getId();
    }

    private String dueResponseBody() throws Exception {
        return mockMvc.perform(get("/notes/due"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private List<String> dueContents() throws Exception {
        return JsonPath.read(dueResponseBody(), "$[*].content");
    }
}
