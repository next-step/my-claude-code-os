package com.reviewscheduler.note;

/**
 * 주어진 id의 노트가 없을 때 던진다.
 *
 * 삭제된 노트는 이 예외의 대상이 아니다 — soft delete라서 행이 그대로 남아 있고,
 * 삭제된 노트도 되돌릴 수 있어야 하기 때문이다. 여기서 말하는 "없다"는 그런 id의
 * 행이 애초에 저장된 적 없다는 뜻이다.
 */
public class NoteNotFoundException extends RuntimeException {

    public NoteNotFoundException(Long id) {
        super("노트를 찾을 수 없습니다: id=" + id);
    }
}
