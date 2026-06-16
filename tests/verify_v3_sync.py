# -*- coding: utf-8 -*-
import pathlib, sys, datetime
from playwright.sync_api import sync_playwright
today=datetime.date.today().isoformat()
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel="msedge"); pg=b.new_page()
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.on("console",lambda m:errs.append("C:"+m.text) if m.type=="error" else None)
    pg.goto(pathlib.Path("index-v3.html").resolve().as_uri(),wait_until="load")
    # ローカルデータをシード
    pg.evaluate(f"""()=>{{
      localStorage.setItem('gym_data', JSON.stringify({{'{today}':{{exercises:[{{name:'ローカル種目',sets:[{{weight:10,reps:10}}]}}]}}}}));
      localStorage.setItem('training_records', JSON.stringify([{{date:'{today}',weight:62.0}}]));
      localStorage.setItem('nutrition_goals', JSON.stringify({{p:100}}));
    }}""")
    # 関数存在
    defined=pg.evaluate("()=>[typeof syncToCloud, typeof loadFromCloud, typeof receiveFirestoreData, typeof STORAGE_KEYS]")
    # ブラウザでsync呼んでも例外なし
    noerr=pg.evaluate("()=>{try{syncToCloud('uid1',0);loadFromCloud('uid1');return true;}catch(e){return String(e)}}")
    # クラウドデータでreceiveFirestoreData（ローカル優先マージ）
    cloud={
      "gym_data": "{\"%s\":{\"exercises\":[{\"name\":\"クラウド種目\"}]},\"2000-01-01\":{\"exercises\":[{\"name\":\"昔の\"}]}}" % today,
      "training_records": "[{\"date\":\"2000-01-01\",\"weight\":99}]",
      "nutrition_goals": "{\"p\":200,\"f\":50}"
    }
    import json as _j
    pg.evaluate("(s)=>receiveFirestoreData(s)", _j.dumps(cloud))
    res=pg.evaluate(f"""()=>({{
      gymToday: JSON.parse(localStorage.getItem('gym_data'))['{today}'].exercises[0].name,
      gymOld: !!JSON.parse(localStorage.getItem('gym_data'))['2000-01-01'],
      recs: JSON.parse(localStorage.getItem('training_records'))[0].weight,
      goalsP: JSON.parse(localStorage.getItem('nutrition_goals')).p
    }})""")
    # ログインコールバックも例外なし
    cbOk=pg.evaluate("()=>{try{onFirebaseSignIn('u','名前','a@b.com');onFirebaseSignOut();return true;}catch(e){return String(e)}}")
    print("関数型:",defined,"(全function/object)")
    print("sync呼出し例外:",noerr)
    print("マージ結果:",res)
    print("  gymToday=ローカル種目(local優先), gymOld=True(cloud追加), recs=62(local優先), goalsP=200(cloud上書き)")
    print("ログインCB:",cbOk)
    print("errs:",errs if errs else "なし")
    ok=(defined==['function','function','function','object'] and noerr is True and res['gymToday']=='ローカル種目' and res['gymOld'] and res['recs']==62.0 and res['goalsP']==200 and cbOk is True and not errs)
    print("RESULT:","PASS" if ok else "FAIL")
    b.close(); sys.exit(0 if ok else 1)
