# -*- coding: utf-8 -*-
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
ok_all=True
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':412,'height':915}); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    pg.evaluate("""()=>{
      localStorage.setItem('user_profile', JSON.stringify({height:168,age:25,sex:'male'}));
      const t=logicalToday(); const d=new Date(t+'T00:00:00'); d.setDate(d.getDate()-1);
      const z=n=>String(n).padStart(2,'0'); const y=d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate());
      localStorage.setItem('training_records', JSON.stringify([{date:y,weight:61,kcal:1700},{date:t,weight:60.8}]));
      localStorage.setItem('gym_data', JSON.stringify({[y]:{exercises:[{name:'ベンチプレス',sets:[{weight:60,reps:8},{weight:60,reps:8},{weight:60,reps:8}]}]}}));
    }""")
    pg.evaluate("go('today'); curDate=logicalToday(); renderToday();"); pg.wait_for_timeout(40)
    html=pg.evaluate("()=>document.getElementById('today-analysis').innerHTML")
    wk=pg.evaluate("()=>dayWeightKcal((()=>{const t=logicalToday();const d=new Date(t+'T00:00:00');d.setDate(d.getDate()-1);const z=n=>String(n).padStart(2,'0');return d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate());})(),61)")
    print('weightKcal=',wk, ' 筋トレ in text=', '筋トレ' in html, ' errs=', errs[:1])
    ok_all = (wk>0) and ('筋トレ' in html) and (not errs)
    pg.close(); b.close()
print('PASS' if ok_all else 'FAIL')
sys.exit(0 if ok_all else 1)
