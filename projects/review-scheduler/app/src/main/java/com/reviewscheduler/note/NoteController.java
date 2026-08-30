package com.reviewscheduler.note;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 노트 등록/조회를 HTTP로 쓸 수 있게 노출하는 얇은 어댑터. 이 앱의 유일한 실행
 * 진입점이다(명령줄 러너는 없앴다). 계산/영속성 책임은 옮기지 않고
 * NoteService/NextReviewDateCalculator에 그대로 둔다 — 이 클래스는 HTTP
 * 요청·응답 모양으로 옮겨 담는 일만 한다.
 *
 * 로컬 1인 사용 도구라 인증, 여러 사용자, 페이지네이션은 이번 범위에 없다.
 * 경로는 "/notes"(등록)와 "/notes/due"(지금 복습할 목록)로 뒀다.
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
