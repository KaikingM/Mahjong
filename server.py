from flask import Flask,url_for,redirect,render_template,request,abort,session
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
    
    return redirect(url_for("page",page_id = page_id))

@app.route("/p/<page_id>/")
def page(page_id):
    if page_id in pages.keys():
        log_write(page_id, pages[page_id])
        pages[page_id][5] = time.time()
        return render_template("mahjong_score.html",datas = pages[page_id],page_id=page_id)
    else:
        return redirect(url_for("home"))

@app.route("/data/<page_id>/",methods = ["POST"])
def send_data(page_id):
    try:
        datas = request.json
        datas.append(time.time())
        pages[page_id] = datas
        return json.dumps("succes")
    except Exception as e:
        return json.dumps(e)

@app.route("/load_data/<page_id>/", methods = ["POST"])
def load_data(page_id):
    ret = json.dumps(pages[page_id])
    print(pages[page_id])
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
    app.run(debug=True)
