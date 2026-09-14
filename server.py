from flask import Flask,url_for,redirect,render_template,request,abort,session,jsonify
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import random
import string
import time
import json
import hashlib
import os
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
import secrets

pages = {} #id: [names,pages,settings]
app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]
app.config.update(
    SECRET_KEY=os.environ["FLASK_SECRET_KEY"],
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

#db = SQLAlchemy(app)
db_path = Path("mahjong.db")

def get_by_path(data, path):
    current = data

    for index in path:
        current = current[index]

    return current


def set_by_path(data, path, new_value):
    if not path:
        raise ValueError("pathを空にはできません")

    current = data

    # 最後のindexの1つ手前まで移動
    for index in path[:-1]:
        current = current[index]

    # 最後のindexの値を変更
    current[path[-1]] = new_value

def get_connection():
    con = sqlite3.connect(db_path, timeout=10)
    con.row_factory = sqlite3.Row
    
    return con

def initialize_db():
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with get_connection() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                page_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL DEFAULT 0,
                data TEXT NOT NULL
            )
        """
        )

def create_page_db(page_id, data):
    data_json = json.dumps(data, ensure_ascii=False)

    with get_connection() as con:
        con.execute(
            """
            INSERT INTO pages(
                page_id,
                revision,
                data
            )
            VALUES(?, 0, ?)
            """,
            (page_id,data_json)
        )

def load_page(page_id):
    with get_connection() as con:
        row = con.execute(
            """
            SELECT page_id, revision, data
            FROM pages
            WHERE page_id = ?
            """,
            (page_id,)
        ).fetchone()

    if row is None:
        return None

    return {
        "page_id": row["page_id"],
        "revision": row["revision"],
        "data": json.loads(row["data"])
    }

def patch_page(
    page_id,
    path,
    old_value,
    new_value,
    revision
):
    con = get_connection()

    try:
        con.execute("BEGIN IMMEDIATE")

        row = con.execute(
            """
            SELECT revision, data
            FROM pages
            WHERE page_id = ?
            """,
            (page_id,)
        ).fetchone()

        if row is None:
            return {
                "ok": False,
                "error": "not_found"
            }, 404

        data = json.loads(row["data"])
        current_value = get_by_path(data, path)

        if current_value != old_value:
            con.rollback()

            return {
                "ok": False,
                "error": "conflict",
                "revision": row["revision"],
                "current_value": current_value
            }, 409

        set_by_path(data, path, new_value)

        new_revision = row["revision"] + 1

        con.execute(
            """
            UPDATE pages
            SET data = ?,
                revision = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE page_id = ?
            """,
            (
                json.dumps(data, ensure_ascii=False),
                new_revision,
                page_id
            )
        )

        con.commit()

        return {
            "ok": True,
            "revision": new_revision
        }, 200

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()

master_url_salt = secrets.token_hex(32)
reload_sec = 86400

def del_page():
    now = time.time()
    dels = []
    for i in pages.keys():
        if now-pages[i][5] >= reload_sec:
            dels.append(i)
    
    for i in dels:
        del pages[i]

def log_write(*content):
    content_decorated = time.strftime("%y/%m/%d %H:%M:%S") + "; " + " ".join([str(i) for i in content])
    with open("log.txt",mode="a") as f:
        print(content_decorated,file=f)

@app.route("/")
def home():
    page_id = "".join([random.choice(string.ascii_letters+string.digits) for i in range(5)])
    while page_id in pages.keys():
        page_id = "".join([random.choice(string.ascii_letters+string.digits) for i in range(5)])

    pages[page_id] = [["","","",""],[["","","","",""],["","","","",""]],[100,"","","",""],[[[0,0,0,0],[0,0,0,0]],[0,0]],["","","",""],time.time()]

    create_page_db(page_id, pages[page_id])
    
    return redirect(url_for("page",page_id = page_id))

@app.route("/p/<page_id>/")
def page(page_id):
    if page_id in pages.keys():
        log_write(page_id, pages[page_id])
        pages[page_id][5] = time.time()

        print("fromDB",load_page(page_id))
        
        return render_template("mahjong_score.html",datas = pages[page_id],page_id=page_id)
    else:
        return redirect(url_for("home"))

@app.route("/data/<page_id>/",methods = ["POST"])
def send_data(page_id):
    try:
        datas = request.json
        print(datas)
        datas.append(time.time())
        pages[page_id] = datas
        log_write(page_id,pages[page_id])
        return json.dumps("succes")
    except Exception as e:
        return json.dumps(e)

@app.route("/load_data/<page_id>/", methods = ["POST"])
def load_data(page_id):
    ret = json.dumps(pages[page_id])
    #print(pages[page_id])
    return ret

@app.route("/analysis/",methods = ["GET", "POST"])
def analysis():
    return render_template("analysis.html")

@app.route(f"/master_acces/", methods = ["POST","GET"])
def master_access():
    if request.method == "POST":
        password = request.form.get("pass","")
        password_hash = os.environ("MASTER_PASSWORD_HASH")

        if not check_password_hash(password_hash, password):
            return redirect("home")

        session.clear()
        session["is_master"] = True
        return redirect(url_for("master"))
    else:
        return render_template("master_access.html")

@app.route(f"/master/{master_url_salt}/",methods = ["POST", "GET"])
def master():
    if not session.get("is_master"):
        abort(404)
    return render_template("master.html")

@app.route("/master/logout/")
def master_logout():
    session.clear()
    return redirect("home")

if __name__=="__main__":
    initialize_db()
    app.run(debug=True)
