from flask import Flask,url_for,redirect,render_template,request
import random
import string
import time
import json

pages = {"114514":[["a","b","c","d"],[["","","","",""],["","","","",""]],[["0","0"],["0","0"]],["0","0","0","0"],time.time()]} #id: [names,pages,settings]
app = Flask(__name__)

reload_sec = 86400

def del_page():
    now = time.time()
    dels = []
    for i in pages.keys():
        if now-pages[i][4] >= reload_sec:
            dels.append(i)
            print("DEL",i)
    
    for i in dels:
        del pages[i]

@app.route("/")
def home():
    del_page()
    page_id = "".join([random.choice(string.ascii_letters+string.digits) for i in range(5)])
    while page_id in pages.keys():
        page_id = "".join([random.choice(string.ascii_letters+string.digits) for i in range(5)])

    pages[page_id] = [["","","",""],[["","","","",""],["","","","",""]],[[[0,0,0,0],[0,0,0,0]],[0,0]],["","","",""],time.time()]
    
    return redirect(url_for("page",page_id = page_id))

@app.route("/p/<page_id>/")
def page(page_id):
    del_page()
    if page_id in pages.keys():
        pages[page_id][4] = time.time()
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
        print(pages)
        print("datas",datas)
        return json.dumps("succes")
    except Exception as e:
        return json.dumps(e)

if __name__=="__main__":
    app.run(debug=True)
