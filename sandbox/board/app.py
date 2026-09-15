"""아주 작은 게시판 API — 유지보수 요청 처리 OS 도그푸딩용 연습 시스템.

저장소는 인메모리 dict. 프로세스를 재시작하면 초기화된다.
"""
from flask import Flask, jsonify, request


def create_app():
    app = Flask(__name__)

    # id -> post(dict). 테스트마다 create_app() 을 새로 부르면 깨끗한 상태.
    posts = {}
    next_id = {"value": 1}

    def _serialize(pid):
        p = posts[pid]
        return {"id": pid, "title": p["title"], "body": p["body"]}

    @app.get("/posts")
    def list_posts():
        return jsonify([_serialize(pid) for pid in sorted(posts)])

    @app.post("/posts")
    def create_post():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        body = data.get("body", "")

        # title 은 내용이 있는 문자열이어야 한다. isinstance 를 먼저 봐서
        # None/숫자 등에 .strip() 을 호출하지 않는다(500 방지). id 발번 전에 거부한다.
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        # body 는 title 과 달리 빈 값·생략은 허용한다 — 타입만 본다. None(생략·명시적 null
        # 둘 다 .get 기본값 "" 이거나 None으로 들어옴)은 빈 문자열로 취급하고, 문자열이 아닌
        # 값(숫자·객체·배열·불린)만 거부한다.
        if body is None:
            body = ""
        elif not isinstance(body, str):
            return jsonify({"error": "body must be a string"}), 400

        pid = next_id["value"]
        next_id["value"] += 1
        posts[pid] = {"title": title, "body": body}
        return jsonify(_serialize(pid)), 201

    @app.get("/posts/<int:pid>")
    def get_post(pid):
        if pid not in posts:
            return jsonify({"error": "not found"}), 404
        return jsonify(_serialize(pid))

    @app.delete("/posts/<int:pid>")
    def delete_post(pid):
        # 없는 id 는 GET 과 같은 형식으로 거부한다. 삭제(부작용)는 가드 통과 후.
        if pid not in posts:
            return jsonify({"error": "not found"}), 404

        del posts[pid]
        # next_id 는 건드리지 않는다 — 삭제한 id 를 재사용하면 안 된다.
        return "", 204

    @app.patch("/posts/<int:pid>")
    def update_post(pid):
        # 없는 id 는 GET/DELETE 와 같은 형식으로 거부한다. 그 다음 title 을 POST 와
        # 동일 순서(타입 → 값)로 검사해 부작용(갱신)은 모든 가드 통과 후에만 낸다.
        if pid not in posts:
            return jsonify({"error": "not found"}), 404

        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        posts[pid]["title"] = title
        return jsonify(_serialize(pid))

    return app


if __name__ == "__main__":
    create_app().run(port=5000, debug=True)
