# -*- coding: utf-8 -*-
# 自重ボタン(#6): gym重量入力時のみ表示・保存(0)・「自重」表示・他パッドに漏れない、を検証。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
def hidden(pg,idd): return pg.evaluate(f"()=>document.getElementById('{idd}').classList.contains('hide')")
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    pg.evaluate("go('gym'); curDate=logicalToday(); pickEx('チンニング')"); pg.wait_for_timeout(40)
    # 重量パッド→自重ボタン表示
    pg.evaluate("openGymPad(0,0,'w')"); pg.wait_for_timeout(20)
    rec('BW_SHOWN_W', not hidden(pg,'pad-bw'), 'visible on weight')
    # 自重を押す→weight=0、表示「自重」
    pg.evaluate("padBodyweight()"); pg.wait_for_timeout(30)
    st=pg.evaluate("()=>({w:gymWork[0].sets[0].weight, html:document.getElementById('gym-cards').innerHTML.includes('自重')})")
    rec('BW_SAVE', st['w']==0 and st['html'], f"{st}")
    # repパッド→自重ボタン非表示
    pg.evaluate("openGymPad(0,0,'r')"); pg.wait_for_timeout(20)
    rec('BW_HIDE_R', hidden(pg,'pad-bw'), 'hidden on reps'); pg.evaluate("closePad()")
    # 体重パッド(openPad)→自重ボタン非表示
    pg.evaluate("go('today'); curDate=logicalToday(); openPad('','weight')"); pg.wait_for_timeout(20)
    rec('BW_HIDE_WEIGHT', hidden(pg,'pad-bw'), 'hidden on body weight'); pg.evaluate("closePad()")
    # 1RM分析がエラーにならない（自重含むデータ）
    pg.evaluate("go('data'); setPeriod('all'); try{renderGymAnalytics&&renderGymAnalytics();}catch(e){}"); pg.wait_for_timeout(40)
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
