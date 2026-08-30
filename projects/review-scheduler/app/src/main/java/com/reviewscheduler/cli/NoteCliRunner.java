package com.reviewscheduler.cli;

import com.reviewscheduler.note.Note;
import com.reviewscheduler.note.NoteService;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 사람이 로컬에서 이 앱을 실제로 쓰기 위한 진입점.
 *
 * 이 앱의 배포 형태는 "로컬 실행"이고 사용자는 만든 사람 한 명이다. 그래서 서버나
 * REST API 대신, 한 줄 명령으로 "등록"과 "지금 볼 목록"만 되는 가장 얇은 CLI를 골랐다.
 * 하루에 몇 번, 짧게 쓰고 끝나는 용도라 매번 새로 뜨는 비용(몇 초)이 문제가 되지 않는다 —
 * 자세한 이유는 배포 보고에 적는다.
 *
 * 명령줄 인자에 "--"로 시작하는 항목(예: 테스트가 SpringApplicationBuilder#run(...)에
 * 넘기는 --spring.datasource.url=... 같은 프로퍼티 오버라이드)은 실제 사용자 명령이
 * 아니므로 걸러내고 무시한다.
 */
@Component
public class NoteCliRunner implements CommandLineRunner {

    private static final DateTimeFormatter DATE_TIME_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final NoteService noteService;

    public NoteCliRunner(NoteService noteService) {
        this.noteService = noteService;
    }

    @Override
    public void run(String... args) {
        List<String> commandArgs = Arrays.stream(args)
                .filter(arg -> !arg.startsWith("--"))
                .collect(Collectors.toList());

        if (commandArgs.isEmpty()) {
            printUsage();
            return;
        }

        String command = commandArgs.get(0);
        switch (command) {
            case "register" -> handleRegister(commandArgs);
            case "list" -> handleList();
            default -> {
                System.out.println("알 수 없는 명령: " + command);
                printUsage();
            }
        }
    }

    private void handleRegister(List<String> commandArgs) {
        if (commandArgs.size() < 2) {
            System.out.println("등록할 내용을 입력하세요. 예: register 스프링 부트 학습");
            return;
        }
        String content = String.join(" ", commandArgs.subList(1, commandArgs.size()));
        Note saved = noteService.registerNote(content);
        System.out.printf(
                "등록됨: [id=%d] %s (등록: %s, 다음 복습일: %s)%n",
                saved.getId(),
                saved.getContent(),
                saved.getRegisteredAt().format(DATE_TIME_FORMAT),
                saved.getNextReviewDate());
    }

    private void handleList() {
        List<Note> dueNotes = noteService.getNotesDueForReview();
        if (dueNotes.isEmpty()) {
            System.out.println("지금 복습할 노트가 없습니다.");
            return;
        }
        System.out.println("지금 복습할 노트 " + dueNotes.size() + "건:");
        for (Note note : dueNotes) {
            System.out.printf(
                    "[id=%d] %s (등록: %s, 다음 복습일: %s)%n",
                    note.getId(),
                    note.getContent(),
                    note.getRegisteredAt().format(DATE_TIME_FORMAT),
                    note.getNextReviewDate());
        }
    }

    private void printUsage() {
        System.out.println("사용법:");
        System.out.println("  register <내용>   - 노트를 한 건 등록합니다");
        System.out.println("  list              - 지금 복습할 노트 목록을 봅니다");
    }
}
