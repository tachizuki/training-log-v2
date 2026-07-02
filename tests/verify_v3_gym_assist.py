# -*- coding: utf-8 -*-
# チンニング/ディップス等の「アシスト（マシン補助）」入力の検証。
# 仕様: 重量は符号付き（荷重=+n / 自重=0 / アシスト=-n）。パッドに🦾アシストボタン（gym重量時のみ表示）。
#       表示はカード=-n kg(水色.asw)、シェア=アシストn kg。既存の自重/荷重は無変更。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':414,'height':1000}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    pg.evaluate("go('gym'); curDate=logicalToday();"); pg.wait_for_timeout(40)
    pg.evaluate("pickEx('チンニング')"); pg.wait_for_timeout(60)
    pg.evaluate("if(!gymWork[0].sets||!gymWork[0].sets.length) gymAddSet(0); gymAddSet(0); gymAddSet(0);"); pg.wait_for_timeout(40)
    # ① gym重量パッドでアシストボタンが出る
    pg.evaluate("openGymPad(0,0,'w')"); pg.wait_for_timeout(30)
    rec('BTN_VISIBLE', pg.evaluate("()=>!document.getElementById('pad-assist').classList.contains('hide')"))
    # ② 20と打って→アシスト → -20保存・セルは水色の-20
    pg.evaluate("document.getElementById('pad-val').textContent='20'; padAssist();"); pg.wait_for_timeout(50)
    rec('SAVE_NEG', pg.evaluate("()=>gymWork[0].sets[0].weight")==-20, f"w={pg.evaluate('()=>gymWork[0].sets[0].weight')}")
    cell=pg.evaluate("()=>document.querySelector('.srow .cell').innerHTML")
    rec('CELL_ASW', 'asw' in cell and '-20' in cell, f"cell={cell[:60]}")
    # ③ 再編集: パッドを開くとアシストがon・値は-20
    pg.evaluate("openGymPad(0,0,'w')"); pg.wait_for_timeout(30)
    rec('BTN_ON', pg.evaluate("()=>document.getElementById('pad-assist').classList.contains('on')"))
    rec('PAD_VAL_NEG', pg.evaluate("()=>document.getElementById('pad-val').textContent")=='-20')
    pg.evaluate("closePad()")
    # ④ 自重は従来どおり0
    pg.evaluate("openGymPad(0,1,'w'); padBodyweight();"); pg.wait_for_timeout(40)
    rec('BW_STILL_0', pg.evaluate("()=>gymWork[0].sets[1].weight")==0)
    rec('BW_LABEL', pg.evaluate("()=>document.querySelectorAll('.srow')[1].querySelector('.cell').textContent.indexOf('自重')>=0"))
    # ⑤ 決定は従来どおり荷重(+n)
    pg.evaluate("openGymPad(0,2,'w'); document.getElementById('pad-val').textContent='25'; padDone();"); pg.wait_for_timeout(40)
    rec('LOAD_POS', pg.evaluate("()=>gymWork[0].sets[2].weight")==25)
    # ⑥ repsパッド・今日画面パッドでは非表示
    pg.evaluate("openGymPad(0,0,'r')"); pg.wait_for_timeout(20)
    rec('HIDE_REPS', pg.evaluate("()=>document.getElementById('pad-assist').classList.contains('hide')"))
    pg.evaluate("closePad(); go('today'); openPad('','weight');"); pg.wait_for_timeout(30)
    rec('HIDE_TODAY', pg.evaluate("()=>document.getElementById('pad-assist').classList.contains('hide')"))
    pg.evaluate("closePad(); go('gym');"); pg.wait_for_timeout(30)
    # ⑦ 永続化: localStorage に -20
    saved=pg.evaluate("()=>{const g=JSON.parse(localStorage.getItem('gym_data')); const k=Object.keys(g).find(k=>k.startsWith(logicalToday())); return g[k].exercises[0].sets[0].weight;}")
    rec('PERSIST', saved==-20, f"stored={saved}")
    # ⑧ シェア画像がエラーなく生成される（アシスト行含む）
    pg.evaluate("HTMLAnchorElement.prototype.click=function(){}")
    try:
        pg.evaluate("gymShare()"); pg.wait_for_timeout(80); share_ok=True
    except Exception:
        share_ok=False
    rec('SHARE_NOERR', share_ok)
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
