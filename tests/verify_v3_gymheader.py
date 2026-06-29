# -*- coding: utf-8 -*-
# #4 gym-datebarがスクロール外の固定ヘッダー(BK-004: sticky廃止)、#5 シート内入力でページが過剰スクロールしない、を検証。
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
    pg.evaluate("go('gym'); curDate=logicalToday();"); pg.wait_for_timeout(30)
    # #4 datebarはスクロール外の固定ヘッダー（BK-004: sticky廃止。スクロールに巻き込まれず見切れない）
    header_fixed=pg.evaluate("""()=>{const bar=document.querySelector('.gym-datebar');const sc=document.getElementById('gym-scroll');
      return !!bar && !!sc && !sc.contains(bar) && ['auto','scroll'].includes(getComputedStyle(sc).overflowY);}""")
    rec('HEADER_FIXED', header_fixed, "datebar outside #gym-scroll & inner scroll has overflow")
    # scrollIntoView スパイ
    pg.evaluate("""()=>{window.__siv=[]; const o=Element.prototype.scrollIntoView;
      Element.prototype.scrollIntoView=function(){ window.__siv.push(this.id||this.className||''); return o&&o.apply(this,arguments); };}""")
    pg.evaluate("pickEx('ベンチプレス')"); pg.wait_for_timeout(40)
    # #5 シート内入力(ex-q)はスクロールさせない
    pg.evaluate("openExSheet()"); pg.wait_for_timeout(20)
    pg.evaluate("()=>document.getElementById('ex-q').focus()"); pg.wait_for_timeout(360)
    sheet_scrolled=pg.evaluate("()=>window.__siv.includes('ex-q')")
    rec('SHEET_NO_SCROLL', not sheet_scrolled, f"siv={pg.evaluate('()=>window.__siv')}")
    pg.evaluate("closeExSheet()"); pg.wait_for_timeout(20)
    # ページ内入力(srow-memo)は従来通りスクロールする
    pg.evaluate("()=>{const m=document.querySelector('.srow-memo'); if(m) m.focus();}"); pg.wait_for_timeout(360)
    page_scrolled=pg.evaluate("()=>window.__siv.some(x=>String(x).indexOf('srow-memo')>=0)")
    rec('PAGE_SCROLL', page_scrolled, f"siv={pg.evaluate('()=>window.__siv')}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
