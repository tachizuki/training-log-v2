# -*- coding: utf-8 -*-
# 今日画面の歩数・日サロ入力(復活#7)の保存/表示を検証。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
def enterpad(pg, target, digits):
    pg.evaluate(f"openPad('','{target}')"); pg.wait_for_timeout(20)
    for d in str(digits): pg.evaluate(f"padKey('{d}')")
    pg.evaluate("padDone()"); pg.wait_for_timeout(30)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    pg.evaluate("go('today'); curDate=logicalToday();")
    # タイルが存在する
    exist=pg.evaluate("()=>({steps:!!document.getElementById('salon-val')&&!!document.getElementById('steps-val'), label_salon:document.querySelector('[data-i18n=\"salon\"]').textContent})")
    rec('TILES', exist['steps'] and exist['label_salon']=='日サロ', f"{exist}")
    # 日サロ30分を入力
    enterpad(pg,'salon',30)
    s=pg.evaluate("()=>({salon:(getRec(curDate)||{}).salon, disp:document.getElementById('salon-val').textContent})")
    rec('SALON', s['salon']==30 and '30' in s['disp'] and '分' in s['disp'], f"{s}")
    # 歩数8000を入力
    enterpad(pg,'steps',8000)
    st=pg.evaluate("()=>({steps:(getRec(curDate)||{}).steps, disp:document.getElementById('steps-val').textContent})")
    rec('STEPS', st['steps']==8000 and '8000' in st['disp'], f"{st}")
    # padラベル
    lbl=pg.evaluate("()=>padLabel('salon')")
    rec('PADLABEL', '日サロ' in lbl and '分' in lbl, f"lbl={lbl}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
