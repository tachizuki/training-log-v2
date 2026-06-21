# -*- coding: utf-8 -*-
# 数字パッドの電話配列(1が上)＋機能、体重グラフの今日値を右上表示、を検証。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    order=pg.evaluate("()=>[...document.querySelectorAll('#pad .pad-grid button')].map(b=>b.textContent)")
    rec('PAD_ORDER', order[:4]==['1','2','3','⌫'] and order[8:11]==['7','8','9'], f"{order}")
    mo=pg.evaluate("()=>[...document.querySelectorAll('#mpad .pad-grid button')].map(b=>b.textContent)")
    rec('MPAD_ORDER', mo[:4]==['1','2','3','⌫'] and mo[8:11]==['7','8','9'], f"{mo}")
    pg.evaluate("go('today'); curDate=logicalToday(); openPad('','weight')"); pg.wait_for_timeout(20)
    pg.evaluate("()=>[...document.querySelectorAll('#pad .pad-grid button')].find(b=>b.textContent==='7').click()")
    pg.evaluate("()=>[...document.querySelectorAll('#pad .pad-grid button')].find(b=>b.textContent==='3').click()")
    val=pg.evaluate("()=>document.getElementById('pad-val').textContent")
    rec('PAD_FUNC', val=='73', f"val={val}")
    pg.evaluate("closePad()")
    pg.evaluate("""()=>{const t=logicalToday(); const d=new Date(t+'T00:00:00'); d.setDate(d.getDate()-1);
      const p=n=>String(n).padStart(2,'0'); const y=d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());
      localStorage.setItem('training_records', JSON.stringify([{date:y,weight:61.2},{date:t,weight:60.7}]));}""")
    pg.evaluate("go('data'); setPeriod('all');"); pg.wait_for_timeout(60)
    chart=pg.evaluate("()=>document.getElementById('weight-chart').innerHTML")
    rec('CHART_TOPRIGHT', ('x=\"334\"' in chart) and ('60.7' in chart), f"has334={'x=\"334\"' in chart} has607={'60.7' in chart}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
