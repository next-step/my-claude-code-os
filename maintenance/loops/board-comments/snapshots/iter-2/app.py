"""아주 작은 게시판 API — 유지보수 요청 처리 OS 도그푸딩용 연습 시스템.

저장소는 인메모리 dict. 프로세스를 재시작하면 초기화된다.
"""
from flask import Flask, jsonify, request


def create_app():
    app = Flask(__name__)

    # id -> post(dict). 테스트마다 create_app() 을 새로 부르면 깨끗한 상태.
    posts = {}
    next_id = {"value": 1}

    # cid -> comment(dict). post id 와 마찬가지로 전역 카운터, 삭제해도 재사용 안 함.
    comments = {}
    next_comment_id = {"value": 1}

    def _serialize(pid):
        p = posts[pid]
        return {"id": pid, "title": p["title"], "body": p["body"]}

    def _serialize_comment(cid):
        c = comments[cid]
        return {"id": cid, "post_id": c["post_id"], "author": c["author"], "text": c["text"]}

    @app.get("/posts")
    def list_posts():
        # sort: 값이 asc/desc 가 아니면 400. 그 외 파라미터보다 먼저 봐도 순서 규정은
        # 없으므로 등장 순서(sort → page → size)대로 검사한다.
        sort = request.args.get("sort", "asc")
        if sort not in ("asc", "desc"):
            return jsonify({"error": "invalid sort"}), 400

        # page/size: 정수 문자열인지(타입) 먼저 보고, 그 다음 허용 범위(값)를 본다.
        # int() 는 "1.5" 같은 문자열에 ValueError 를 내므로 그대로 거부에 활용한다.
        page_raw = request.args.get("page")
        if page_raw is None:
            page = 1
        else:
            try:
                page = int(page_raw)
            except ValueError:
                return jsonify({"error": "invalid page"}), 400
            if page < 1:
                return jsonify({"error": "invalid page"}), 400

        size_raw = request.args.get("size")
        if size_raw is None:
            size = 10
        else:
            try:
                size = int(size_raw)
            except ValueError:
                return jsonify({"error": "invalid size"}), 400
            if size < 1 or size > 100:
                return jsonify({"error": "invalid size"}), 400

        ids = sorted(posts, reverse=(sort == "desc"))

        q = request.args.get("q", "")
        if q:
            q_lower = q.lower()
            ids = [
                pid
                for pid in ids
                if q_lower in posts[pid]["title"].lower()
                or q_lower in posts[pid]["body"].lower()
            ]

        total = len(ids)
        start = (page - 1) * size
        page_ids = ids[start:start + size]

        resp = jsonify([_serialize(pid) for pid in page_ids])
        resp.headers["X-Total-Count"] = str(total)
        return resp

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
        # version 은 _serialize 응답 몸통에는 포함하지 않는다 — 헤더로만 노출(계약 B).
        posts[pid] = {"title": title, "body": body, "version": 1}
        resp = jsonify(_serialize(pid))
        resp.headers["X-Version"] = str(posts[pid]["version"])
        return resp, 201

    @app.get("/posts/<int:pid>")
    def get_post(pid):
        if pid not in posts:
            return jsonify({"error": "not found"}), 404
        resp = jsonify(_serialize(pid))
        resp.headers["X-Version"] = str(posts[pid]["version"])
        return resp

    @app.delete("/posts/<int:pid>")
    def delete_post(pid):
        # 없는 id 는 GET 과 같은 형식으로 거부한다. 삭제(부작용)는 가드 통과 후.
        if pid not in posts:
            return jsonify({"error": "not found"}), 404

        del posts[pid]
        # 이 post 에 딸린 댓글도 함께 지운다(cascade). next_id/next_comment_id 는
        # 건드리지 않는다 — 삭제한 id 를 재사용하면 안 된다.
        for cid in [cid for cid, c in comments.items() if c["post_id"] == pid]:
            del comments[cid]
        return "", 204

    @app.patch("/posts/<int:pid>")
    def update_post(pid):
        # 검사 순서 고정: 404(존재) → If-Match(버전, 헤더가 있을 때만) → title(타입→값).
        # 없는 id 는 GET/DELETE 와 같은 형식으로 거부한다.
        if pid not in posts:
            return jsonify({"error": "not found"}), 404

        if_match = request.headers.get("If-Match")
        if if_match is not None and if_match != str(posts[pid]["version"]):
            return jsonify({"error": "version mismatch"}), 409

        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        posts[pid]["title"] = title
        posts[pid]["version"] += 1
        resp = jsonify(_serialize(pid))
        resp.headers["X-Version"] = str(posts[pid]["version"])
        return resp

    @app.post("/posts/<int:pid>/comments")
    def create_comment(pid):
        if pid not in posts:
            return jsonify({"error": "not found"}), 404

        data = request.get_json(silent=True) or {}

        # author 먼저(타입 → 값), 그다음 text. 부작용(id 발번·저장)은 두 가드를 모두
        # 통과한 뒤에만 실행한다.
        author = data.get("author")
        if not isinstance(author, str) or not author.strip():
            return jsonify({"error": "author is required"}), 400

        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "text is required"}), 400

        cid = next_comment_id["value"]
        next_comment_id["value"] += 1
        comments[cid] = {"post_id": pid, "author": author, "text": text}
        return jsonify(_serialize_comment(cid)), 201

    @app.get("/posts/<int:pid>/comments")
    def list_comments(pid):
        if pid not in posts:
            return jsonify({"error": "not found"}), 404

        cids = sorted(cid for cid, c in comments.items() if c["post_id"] == pid)
        return jsonify([_serialize_comment(cid) for cid in cids])

    @app.delete("/posts/<int:pid>/comments/<int:cid>")
    def delete_comment(pid, cid):
        # pid 가 없거나 cid 가 그 post 소속이 아니면(다른 post 소속이든 아예 없든)
        # 동일하게 404 — 존재 여부를 흘리지 않는다.
        if pid not in posts:
            return jsonify({"error": "not found"}), 404
        if cid not in comments or comments[cid]["post_id"] != pid:
            return jsonify({"error": "not found"}), 404

        del comments[cid]
        return "", 204

    return app


if __name__ == "__main__":
    create_app().run(port=5000, debug=True)
