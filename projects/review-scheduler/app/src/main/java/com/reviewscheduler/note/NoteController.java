package com.reviewscheduler.note;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 노트 등록/조회/삭제/되돌리기를 HTTP로 쓸 수 있게 노출하는 얇은 어댑터. 이 앱의 유일한 실행
 * 진입점이다(명령줄 러너는 없앴다). 계산/영속성 책임은 옮기지 않고
 * NoteService/NextReviewDateCalculator에 그대로 둔다 — 이 클래스는 HTTP
 * 요청·응답 모양으로 옮겨 담는 일만 한다.
 *
 * 로컬 1인 사용 도구라 인증, 여러 사용자, 페이지네이션은 이번 범위에 없다.
 * 경로는 네 개다 — "/notes"(등록), "/notes/due"(지금 복습할 목록),
 * "DELETE /notes/{id}"(삭제), "POST /notes/{id}/restore"(되돌리기).
 *
 * 삭제/되돌리기 응답은 204(빈 본문) 대신 200 + 노트 본문으로 돌려준다. 되돌린 노트의
 * 다음 복습일이 삭제 전과 같아야 한다는 것이 수용 기준이라, 호출자가 목록을 다시
 * 조회하지 않고도 그 값을 응답에서 바로 확인할 수 있어야 쓸모가 있다.
 *
 * 되돌리기가 POST인 이유: 되돌리기는 노트 전체를 보내 덮어쓰는 조작(PUT)이 아니라
 * "삭제를 취소하라"는 행위 호출이고, 본문이 없다.
 */
@RestController
@RequestMapping("/notes")
public class NoteController {

    private final NoteService noteService;

    public NoteController(NoteService noteService) {
        this.noteService = noteService;
    }

    @PostMapping
    public ResponseEntity<NoteResponse> register(@RequestBody NoteRegisterRequest request) {
        Note saved = noteService.registerNote(request.content());
        return ResponseEntity.status(HttpStatus.CREATED).body(NoteResponse.from(saved));
    }

    @GetMapping("/due")
    public List<NoteResponse> due() {
        return noteService.getNotesDueForReview().stream()
                .map(NoteResponse::from)
                .toList();
    }

    /**
     * 노트를 삭제한다. 행을 지우지 않고 deleted_at을 채우는 soft delete라서, 삭제한 노트도
     * 되돌리기 대상으로 계속 남아 있다. 이미 삭제된 노트를 또 삭제해도 성공으로 응답하고
     * 최초 삭제 시각을 유지한다 — 같은 요청을 두 번 보낸 것이 오류일 이유가 없다.
     */
    @DeleteMapping("/{id}")
    public NoteResponse delete(@PathVariable("id") Long id) {
        return NoteResponse.from(noteService.deleteNote(id));
    }

    /** 삭제한 노트를 복습 목록으로 되돌린다. 다음 복습일은 삭제 전 값 그대로다. */
    @PostMapping("/{id}/restore")
    public NoteResponse restore(@PathVariable("id") Long id) {
        return NoteResponse.from(noteService.restoreNote(id));
    }

    /**
     * 없는 id로 삭제/되돌리기를 요청하면 404로 답한다. 이 핸들러가 없으면 500으로
     * 새어나가서 "서버가 고장났다"와 "그런 노트가 없다"를 호출자가 구분할 수 없다.
     */
    @ExceptionHandler(NoteNotFoundException.class)
    public ResponseEntity<String> handleNoteNotFound(NoteNotFoundException exception) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(exception.getMessage());
    }

    /**
     * NoteService.registerNote는 내용이 비어 있으면 IllegalArgumentException을 던진다.
     * 이 핸들러가 없으면 그대로 500으로 새어나가므로, 요청이 잘못됐다는 뜻이 되도록
     * 400으로 바꿔준다. (수용 기준에는 없지만, HTTP 진입점을 새로 여는 이상 최소한의
     * 입력 오류 처리는 API 하나 몫이라고 판단해 함께 넣었다.)
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<String> handleInvalidInput(IllegalArgumentException exception) {
        return ResponseEntity.badRequest().body(exception.getMessage());
    }
}
