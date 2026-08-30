package com.reviewscheduler.note;

import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;

public interface NoteRepository extends JpaRepository<Note, Long> {

    /** 다음 복습일이 주어진 날짜 이하인(=오늘까지 복습해야 하는) 노트를 모두 찾는다. */
    List<Note> findByNextReviewDateLessThanEqual(LocalDate date);
}
