package com.reviewscheduler.note;

import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;

public interface NoteRepository extends JpaRepository<Note, Long> {

    /**
     * 복습 목록에 들어갈 노트를 찾는다: 삭제되지 않았고(deleted_at이 비어 있고),
     * 다음 복습일이 주어진 날짜 이하인(=오늘까지 복습해야 하는) 노트.
     *
     * 삭제 필터를 조회한 뒤 메모리에서 거르지 않고 질의 조건에 넣는 이유는, 목록을
     * 만드는 곳이 여기 하나뿐이어서 "삭제된 노트는 목록에 없다"는 규칙이 갈라질 자리를
     * 남기지 않기 위해서다. 삭제는 물리 삭제가 아니라 soft delete라서 행 자체는 계속
     * 남아 있고, 이 조건이 빠지면 삭제한 노트가 그대로 목록에 다시 나타난다.
     */
    List<Note> findByDeletedAtIsNullAndNextReviewDateLessThanEqual(LocalDate date);
}
