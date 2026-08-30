package com.reviewscheduler.note;

/**
 * 노트 등록 HTTP 요청 바디.
 *
 * 명령줄의 {@code register <내용>}과 받는 정보가 같다(내용 하나뿐) — 이번 범위에는
 * 난이도 입력 등 추가 항목이 없으므로 필드를 하나만 둔다.
 */
public record NoteRegisterRequest(String content) {
}
