# -*- coding: utf-8 -*-
# 固定ヘッダー化: 擬似時計→カウントダウン、各タブのctx-strip撤去、JSエラーなしを検証。
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
    pg.evaluate("()=>{localStorage.setItem('contest_name','APFファーストタイマー');localStorage.setItem('contest_date','2026-08-01');localStorage.setItem('contest_weight','58');localStorage.setItem('training_records',JSON.stringify([{date:logicalToday(),weight:60.6}]));}")
    pg.evaluate("go('today'); curDate=logicalToday(); renderToday();"); pg.wait_for_timeout(40)
    st=pg.evaluate("""()=>({
      header: !!document.querySelector('.statusbar.topbar'),
      days: (document.getElementById('ctx-days')||{}).textContent||'',
      contest: (document.getElementById('ctx-contest')||{}).textContent||'',
      noClock: !document.getElementById('sb-time'),
      stripCount: document.querySelectorAll('.ctx-strip').length,
      headerInPhone: !!document.querySelector('.phone > .statusbar.topbar')
    })""")
    rec('HEADER', st['header'] and st['noClock'], f"{st}")
    rec('COUNTDOWN', ('残り' in st['days'] or '日' in st['days']) and 'APF' in st['contest'], f"days={st['days']} contest={st['contest']}")
    rec('NOSTRIP', st['stripCount']==0, f"ctx-strip remain={st['stripCount']}")
    rec('HEADER_FIXED', st['headerInPhone'], '.phone直下=スクロール外')
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
