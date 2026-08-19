from flask import Flask,url_for,redirect,render_template,request
import random
import string
import time
import json
import hashlib

pages = {} #id: [names,pages,settings]
app = Flask(__name__)

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
    del_page()
    page_id = "".join([random.choice(string.ascii_letters+string.digits) for i in range(5)])
    while page_id in pages.keys():
        page_id = "".join([random.choice(string.ascii_letters+string.digits) for i in range(5)])

    pages[page_id] = [["","","",""],[["","","","",""],["","","","",""]],[100,"","","",""],[[[0,0,0,0],[0,0,0,0]],[0,0]],["","","",""],time.time()]
    
    return redirect(url_for("page",page_id = page_id))

@app.route("/p/<page_id>/")
def page(page_id):
    del_page()
    if page_id in pages.keys():
        log_write(page_id, pages[page_id])
        pages[page_id][5] = time.time()
        return render_template("mahjong_score.html",datas = pages[page_id],page_id=page_id)
    else:
        return redirect(url_for("home"))

@app.route("/data/<page_id>/",methods = ["POST"])
def send_data(page_id):
    del_page()
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

@app.route("/master/", methods = ["POST","GET"])
def master_access():
    if request.method == "POST":
        print(request.form.get("pass"))
        if hashlib.sha256(request.form.get("pass").encode("utf-8")).hexdigest() == "52cb412a854716ee65c9ad1065a4ed1861bab4c05bceed184cef51f78e8101b3":
            with open("log.txt", mode="r") as f:
                print(f.read())
                return render_template("master.html", pages = f.read())
        else:
            return redirect(url_for("home"))
    else:
        return render_template("master_access.html")

if __name__=="__main__":
    app.run(debug=True)
