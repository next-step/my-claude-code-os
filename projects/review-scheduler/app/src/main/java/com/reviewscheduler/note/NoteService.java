package com.reviewscheduler.note;

import com.reviewscheduler.domain.NextReviewDateCalculator;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 노트 등록/조회를 담당하는 애플리케이션 서비스.
 *
 * 실제 "다음 복습일이 며칠 뒤인가"는 여기서 계산하지 않고 NextReviewDateCalculator에
 * 위임한다. 이 클래스는 "지금 시각을 구하고, 계산기를 호출하고, 저장소에 저장한다"는
 * 조립(오케스트레이션) 책임만 갖는다.
 *
 * "지금"이 언제인지는 LocalDateTime.now()/LocalDate.now()를 직접 부르지 않고
 * 주입받은 Clock을 통해서만 구한다. 그래야 자정 근처나 타임존 경계 같은 특정 시각을
 * 테스트에서 고정해 이 클래스의 동작을 결정적으로 재현할 수 있다.
 */
@Service
public class NoteService {

    private final NoteRepository noteRepository;
    private final NextReviewDateCalculator nextReviewDateCalculator;
    private final Clock clock;

    public NoteService(NoteRepository noteRepository, NextReviewDateCalculator nextReviewDateCalculator, Clock clock) {
        this.noteRepository = noteRepository;
        this.nextReviewDateCalculator = nextReviewDateCalculator;
        this.clock = clock;
    }

    /** 노트를 한 건 등록한다. 등록 시각은 호출 시점의 현재 시각(주입된 clock 기준)으로 고정한다. */
    public Note registerNote(String content) {
        if (content == null || content.isBlank()) {
            throw new IllegalArgumentException("content는 비어 있을 수 없습니다");
        }
        LocalDateTime registeredAt = LocalDateTime.now(clock);
        LocalDate nextReviewDate = nextReviewDateCalculator.calculateNextReviewDate(registeredAt);
        Note note = new Note(content, registeredAt, nextReviewDate);
        return noteRepository.save(note);
    }

    /**
     * 지금 시점에 복습해야 할 노트 목록을 반환한다.
     *
     * 이름에 "Today"를 넣지 않았다: 다음 복습일이 오늘인 노트뿐 아니라 이미 지난
     * (밀린) 노트까지 전부 포함하기 때문이다. "오늘 것만"이라는 인상을 주는 이름을
     * 쓰면 나중에 누군가 밀린 복습을 위한 조회를 별도로 또 만들면서 "지금 복습할
     * 목록"을 결정하는 로직이 두 군데로 갈라질 위험이 있다.
     */
    public List<Note> getNotesDueForReview() {
        return noteRepository.findByNextReviewDateLessThanEqual(LocalDate.now(clock));
    }
}
