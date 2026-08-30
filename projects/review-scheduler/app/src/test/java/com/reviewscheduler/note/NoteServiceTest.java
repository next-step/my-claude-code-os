package com.reviewscheduler.note;

import com.reviewscheduler.domain.NextReviewDateCalculator;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jpa.test.autoconfigure.TestEntityManager;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * @DataJpaTest: 실제 JPA/리포지토리 계층만 띄우는 슬라이스 테스트라서
 * 전체 애플리케이션 컨텍스트(@SpringBootTest)보다 훨씬 빠르다.
 * NoteService 자체는 Spring 빈이 아니라 이 테스트 안에서 직접 new로 조립한다 —
 * 이 서비스가 의존하는 건 리포지토리와 순수 계산기, Clock뿐이라 그래도 충분하다.
 *
 * 검증 대상 수용 기준:
 * 1) "노트를 1건 등록하면 등록 시각과 다음 복습일이 각각 1개씩 저장된다."
 * 3) "지금 복습할 노트 목록에는 다음 복습일이 오늘 이하인 노트만 포함된다."
 */
@DataJpaTest
class NoteServiceTest {

    @Autowired
    private NoteRepository noteRepository;

    /**
     * @DataJpaTest가 제공하는 영속성 컨텍스트 제어 도구. flush()/clear()로 1차 캐시를
     * 비워서, 이후 조회가 메모리에 남은 객체가 아니라 진짜 DB SELECT를 타게 만드는 데 쓴다.
     */
    @Autowired
    private TestEntityManager entityManager;

    private NoteService newService(Clock clock) {
        return new NoteService(noteRepository, new NextReviewDateCalculator(), clock);
    }

    @Test
    void 노트를_1건_등록하면_등록_시각과_다음_복습일이_각각_1개씩_저장된다() {
        NoteService noteService = newService(Clock.systemDefaultZone());

        Note saved = noteService.registerNote("스프링 부트 학습");
        Long savedId = saved.getId();
        LocalDateTime registeredAtWhenSaved = saved.getRegisteredAt();
        LocalDate nextReviewDateWhenSaved = saved.getNextReviewDate();

        // save()가 돌려준 saved와, 같은 트랜잭션/영속성 컨텍스트 안에서 다시 조회한 결과는
        // 1차 캐시 때문에 항상 "같은 자바 인스턴스"다. 그 상태로 saved 자신의 필드를
        // saved에서 다시 읽은 값과 비교하면, DB에 실제로 컬럼이 쓰였는지와 무관하게
        // 항상 통과해버린다(등록 시각/다음 복습일을 @Transient로 바꿔 전혀 저장되지
        // 않게 해도 실패하지 않는다). 그래서 flush + clear로 영속성 컨텍스트를 비우고,
        // 이후의 조회가 진짜 DB로 가서 새 인스턴스를 만들어내게 강제한다.
        entityManager.flush();
        entityManager.clear();

        List<Note> all = noteRepository.findAll();

        assertThat(all).hasSize(1);
        Note reloaded = all.get(0);
        // 캐시가 아니라 DB에서 새로 만들어진 객체인지를 명시적으로 못박아 둔다.
        // 이 단언이 없으면 나중에 누군가 flush/clear를 지워도 컴파일과 로직상으로는
        // 티가 안 나서 다시 예전의 "항상 통과하는" 상태로 조용히 되돌아갈 수 있다.
        assertThat(reloaded).isNotSameAs(saved);
        assertThat(reloaded.getId()).isEqualTo(savedId);
        assertThat(reloaded.getRegisteredAt()).isNotNull().isEqualTo(registeredAtWhenSaved);
        assertThat(reloaded.getNextReviewDate()).isNotNull().isEqualTo(nextReviewDateWhenSaved);
    }

    @Test
    void 지금_복습할_노트_목록에는_다음_복습일이_오늘_이하인_노트만_포함된다() {
        // "오늘"을 실제 시스템 시각이 아니라 고정된 임의의 날짜로 못박는다. Clock을
        // 주입받게 바꾼 덕분에, 실제 오늘 날짜가 며칠이든 상관없이 이 테스트는 항상
        // 같은 결과를 낸다.
        LocalDate fixedToday = LocalDate.of(2030, 5, 20);
        Clock fixedClock = Clock.fixed(
                fixedToday.atStartOfDay(ZoneId.systemDefault()).toInstant(),
                ZoneId.systemDefault());
        NoteService noteService = newService(fixedClock);

        Note overdueNote = noteRepository.save(
                new Note("어제까지였던 복습", LocalDateTime.now(), fixedToday.minusDays(1)));
        Note dueTodayNote = noteRepository.save(
                new Note("오늘 복습", LocalDateTime.now(), fixedToday));
        Note futureNote = noteRepository.save(
                new Note("나중에 복습", LocalDateTime.now(), fixedToday.plusDays(5)));

        List<Note> dueNotes = noteService.getNotesDueForReview();

        assertThat(dueNotes)
                .extracting(Note::getId)
                .contains(overdueNote.getId(), dueTodayNote.getId())
                .doesNotContain(futureNote.getId());
    }

    @Test
    void 자정_근처로_시각을_고정해도_등록_시각과_다음_복습일이_결정적으로_계산된다() {
        // registerNote가 내부적으로 LocalDateTime.now()를 직접 부르던 예전 구조에서는
        // 이런 경계 시각을 테스트에서 재현할 방법이 없었다. Clock을 주입받게 바뀐 뒤에는
        // Clock.fixed(...)로 자정 1초 전 같은 시각을 그대로 고정해 검증할 수 있다.
        LocalDateTime justBeforeMidnight = LocalDateTime.of(2026, 3, 1, 23, 59, 59);
        ZoneId zone = ZoneId.of("Asia/Seoul");
        Clock fixedClock = Clock.fixed(justBeforeMidnight.atZone(zone).toInstant(), zone);
        NoteService noteService = newService(fixedClock);

        Note saved = noteService.registerNote("자정 근처 등록");

        assertThat(saved.getRegisteredAt()).isEqualTo(justBeforeMidnight);
        assertThat(saved.getNextReviewDate()).isEqualTo(LocalDate.of(2026, 3, 2));
    }
}
