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
#pages["test"] = [["","","",""],[["","","","",""],["","","","",""]],["100","","","",""],[[[0,0,0,0],[0,0,0,0]],[0,0]],["","","",""],time.time()]
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

def get_setting(data, path):

    return data[3][path[0]][path[1]]

def set_setting(data, path, new_val):

    data[3][path[0]][path[1]] = new_val
    
    return data

def add_row_data(data):
    print(data)

    data[1].append(["" for i in range(len(data[1][0]))])
    data[3][0].append([0,0,0,0])
    data[3][1].append(0)

    return data

def add_member_data(data):
    data[0].append("")
    for i,_ in enumerate(data[1]):
        data[1][i].append("")
    data[2].append("")
    data[4].append("")

    return data

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
            DROP TABLE pages;
            """)

        con.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    page_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    last_change INTEGER NOT NULL DEFAULT 0
                );
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
                data,
                last_change
            )
            VALUES(?, 0, ?, ?)
            """,
            (page_id,data_json,int(time.time()))
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
                "error": "not_found",
                "code": 404
            }

        data = json.loads(row["data"])
        current_value = get_by_path(data, path)

        if current_value != old_value:
            con.rollback()

            return {
                "ok": False,
                "error": "conflict",
                "revision": row["revision"],
                "current_value": current_value,
                "code": 409
            }

        set_by_path(data, path, new_value)

        new_revision = row["revision"] + 1

        con.execute(
            """
            UPDATE pages
            SET data = ?,
                revision = ?,
                last_change = ?
            WHERE page_id = ?
            """,
            (
                json.dumps(data, ensure_ascii=False),
                new_revision,
                int(time.time()),
                page_id
            )
        )

        con.commit()

        return {
            "ok": True,
            "revision": new_revision,
            "code": 200,
            "val": new_value
        }

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()

def patch_setting(
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
                "error": "not_found",
                "code": 404
            }

        data = json.loads(row["data"])
        current_value = get_setting(data, path)

        if current_value != old_value:
            con.rollback()

            return {
                "ok": False,
                "error": "conflict",
                "revision": row["revision"],
                "current_value": current_value,
                "code": 409
            }

        new_data = set_setting(data, path, new_value)

        new_revision = row["revision"] + 1

        con.execute(
            """
            UPDATE pages
            SET data = ?,
                revision = ?,
                last_change = ?
            WHERE page_id = ?
            """,
            (
                json.dumps(new_data, ensure_ascii=False),
                new_revision,
                int(time.time()),
                page_id
            )
        )

        con.commit()

        return {
            "ok": True,
            "revision": new_revision,
            "code": 200,
            "val": new_value
        }

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()

def add_row(
    page_id,
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
                "error": "not_found",
                "code": 404
            }

        current_revision = row["revision"]
        data = json.loads(row["data"])

        if revision != current_revision:
            con.rollback()

            return {
                "ok": False,
                "error": "conflict",
                "revision": row["revision"],
                "code": 409
            }

        new_data = add_row_data(data)

        new_revision = current_revision + 1

        con.execute(
            """
            UPDATE pages
            SET data = ?,
                revision = ?,
                last_change = ?
            WHERE page_id = ?
            """,
            (
                json.dumps(new_data, ensure_ascii=False),
                new_revision,
                int(time.time()),
                page_id
            )
        )

        con.commit()

        return {
            "ok": True,
            "revision": new_revision,
            "code": 200,
        }

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()
    
def add_member(
    page_id,
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
                "error": "not_found",
                "code": 404
            }

        data = json.loads(row["data"])
        curreny_revision = row["revision"]

        if revision != curreny_revision:
            con.rollback()

            return {
                "ok": False,
                "error": "conflict",
                "revision": curreny_revision,
                "code": 409
            }

        new_data = add_member_data(data)

        new_revision = curreny_revision + 1

        con.execute(
            """
            UPDATE pages
            SET data = ?,
                revision = ?,
                last_change = ?
            WHERE page_id = ?
            """,
            (
                json.dumps(new_data, ensure_ascii=False),
                new_revision,
                int(time.time()),
                page_id
            )
        )

        con.commit()

        return {
            "ok": True,
            "revision": new_revision,
            "code": 200,
        }

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()

def list_all_record():
    con = get_connection()

    try:
        rows = con.execute(
            """
                SELECT page_id,data,last_change
                FROM pages
                ORDER BY last_change
            """
        ).fetchall()

    finally:
        con.close()
    
    return [
        [i["page_id"], time.strftime("%Y/%m/%d %H:%M:%S",time.localtime(i["last_change"])), json.loads(i["data"])] for i in reversed(rows)
    ]

def list_all_key():
    con = get_connection()

    try:
        rows = con.execute(
            """
                SELECT page_id
                FROM pages
                ORDER BY last_change
            """
        ).fetchall()

    finally:
        con.close()
    return [i["page_id"] for i in rows]

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
    while page_id in list_all_key():
        page_id = "".join([random.choice(string.ascii_letters+string.digits) for i in range(5)])

    create_page_db(page_id, [["","","",""],[["","","","",""],["","","","",""]],["100","","","",""],[[[0,0,0,0],[0,0,0,0]],[0,0]],["","","",""]])
    
    return redirect(url_for("page",page_id = page_id))

@app.route("/p/<page_id>/")
def page(page_id):
    if page_id in list_all_key():
        #pages[page_id][5] = time.time()

        datas = load_page(page_id)#pages[page_id]
        print("fromDB", datas)

        log_write(page_id, datas)
        
        return render_template("mahjong_score.html", datas = datas["data"], page_id=page_id, revision = datas["revision"])
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


@app.route("/data_setting2/<page_id>/",methods = ["POST"])
def send_data_setting_2(page_id):
    try:
        datas = request.json
        print("senddata",datas)
        
        ret = patch_setting(page_id, list(map(lambda e:int(e), datas["index"])), datas["oldVal"], datas["newVal"], datas["revision"])

        db_data = load_page(page_id)
        log_write(page_id, db_data)
        print("ret", ret)
        print(db_data)

        if ret["code"] == 200:
            return json.dumps(ret)
        else:
            return json.dumps(ret), ret["code"]
    except Exception as e:
        return json.dumps(e)

@app.route("/data2/<page_id>/",methods = ["POST"])
def send_data2(page_id):
    try:
        datas = request.json
        print("senddata",datas)
        
        ret = patch_page(page_id, list(map(lambda e:int(e), datas["index"])), datas["oldVal"], datas["newVal"], datas["revision"])

        db_data = load_page(page_id)
        log_write(page_id, db_data)
        print("ret", ret)
        print(db_data)

        if ret["code"] == 200:
            return json.dumps(ret)
        else:
            return json.dumps(ret), ret["code"]
    except Exception as e:
        return json.dumps(e)


@app.route("/add_row/<page_id>/",methods = ["POST"])
def add_row_post(page_id):
    try:
        revision = request.json["revision"]

        ret = add_row(page_id, revision)

        db_data = load_page(page_id)
        log_write(page_id, db_data)
        print("ret", db_data)

        if ret["code"] == 200:
            return json.dumps(ret)
        else:
            return json.dumps(ret), ret["code"]
    except Exception as e:
        return json.dumps(e)
        
@app.route("/add_member/<page_id>/",methods = ["POST"])
def add_member_post(page_id):
    try:
        revision = request.json["revision"]
        
        ret = add_member(page_id, revision)

        db_data = load_page(page_id)
        log_write(page_id, db_data)
        print("ret", ret)
        print(db_data)

        if ret["code"] == 200:
            return json.dumps(ret)
        else:
            return json.dumps(ret), ret["code"]
    except Exception as e:
        return json.dumps(e)

@app.route("/send_test/<page_id>/<revision>/<old>/<new>/<index>")
def send_data_test(page_id,revision,old,new,index):
    print(page_id,revision,old,new,index)
    if old == "None":
        old = ""
    
    if new == "None":
        new = ""
    
    print("response",patch_page(page_id,list(map(lambda e:int(e), index.split(","))),old,new,revision))

    print("load",load_page(page_id))
    
    return "succes"

@app.route("/load_data/<page_id>/", methods = ["POST"])
def load_data(page_id):
    ret = json.dumps(load_page(page_id))#pages[page_id])
    #print(pages[page_id])
    print("load_data",ret)
    return ret

@app.route("/history/", methods = ["GET", "POST"])
def history():
    print(list_all_key())
    all_record = list_all_record()
    print(all_record)
    return render_template("history.html", allRecord = all_record)

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
