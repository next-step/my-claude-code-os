package com.reviewscheduler.note;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 노트 등록/조회/삭제/되돌리기 HTTP 응답 바디.
 *
 * nextReviewDate를 반드시 포함한다 — "등록 응답"과 "지금 복습할 목록 조회 응답"
 * 모두에 각 노트의 다음 복습일이 담겨 있어야 한다는 게 이전 작업의 수용 기준이다.
 * 계산은 여기서 하지 않고 이미 계산되어 저장된 Note의 값을 그대로 옮겨 담기만 한다.
 *
 * deletedAt은 삭제/되돌리기 응답에서 조작이 실제로 반영됐는지 호출자가 눈으로 확인하는
 * 값이다. 삭제되지 않은 노트에서는 null이다.
 */
public record NoteResponse(Long id,
                           String content,
                           LocalDateTime registeredAt,
                           LocalDate nextReviewDate,
                           LocalDateTime deletedAt) {

    public static NoteResponse from(Note note) {
        return new NoteResponse(note.getId(), note.getContent(), note.getRegisteredAt(),
                note.getNextReviewDate(), note.getDeletedAt());
    }
}
