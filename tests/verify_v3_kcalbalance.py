# -*- coding: utf-8 -*-
# 体重変動分析：カロリー収支(±◯kcal)が適正範囲でも常に表示されることを検証。
import pathlib, sys, re
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    def setup(kcal):
        pg.evaluate(f"""()=>{{
          localStorage.setItem('nutrition_goals', JSON.stringify({{p:150,f:50,c:200}}));
          const t=logicalToday(); const d=new Date(t+'T00:00:00'); d.setDate(d.getDate()-1);
          const z=n=>String(n).padStart(2,'0'); const y=d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate());
          localStorage.setItem('training_records', JSON.stringify([
            {{date:y, weight:61, kcal:{kcal}}},
            {{date:t, weight:60.9}}
          ]));
        }}""")
        pg.evaluate("go('today'); curDate=logicalToday(); renderToday();"); pg.wait_for_timeout(40)
        return pg.evaluate("()=>document.getElementById('today-analysis').innerHTML")
    gk = pg.evaluate("()=>calcKcal(150,50,200)")
    # 適正範囲（収支+50想定）
    html_ok = setup(gk+50)
    rec('OK_RANGE', ('収支' in html_ok) and ('+50' in html_ok), f"gk={gk} has収支={'収支' in html_ok} has+50={'+50' in html_ok}")
    # 余剰（+500）
    html_over = setup(gk+500)
    rec('OVER', '+500' in html_over and '余剰' in html_over, f"{'+500' in html_over}")
    # 赤字（-500）
    html_under = setup(gk-500)
    rec('UNDER', '-500' in html_under and '赤字' in html_under, f"{'-500' in html_under}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
