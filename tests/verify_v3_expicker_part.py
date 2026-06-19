# -*- coding: utf-8 -*-
# 種目追加ピッカーが、その日に選択した部位カテゴリで開くことを検証(#1)。
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
    pg.evaluate("go('gym'); curDate=logicalToday();")
    # 部位=足を選択 → 種目追加ピッカーが「足」で開く
    pg.evaluate("pickMenu('足')"); pg.wait_for_timeout(30)
    pg.evaluate("openExSheet()"); pg.wait_for_timeout(40)
    st=pg.evaluate("()=>({exCat:exCat, glabel:document.getElementById('ex-glabel').textContent})")
    rec('LEG', st['exCat']=='足' and st['glabel']=='足', f"{st}")
    pg.evaluate("closeExSheet()")
    # 部位=背中に変更 → ピッカーも背中で開く
    pg.evaluate("pickMenu('背中')"); pg.evaluate("openExSheet()"); pg.wait_for_timeout(40)
    st2=pg.evaluate("()=>({exCat:exCat})")
    rec('BACK', st2['exCat']=='背中', f"{st2}")
    pg.evaluate("closeExSheet()")
    # 部位=自由(プリセット無し) → フォールバック(エラーにならず先頭カテゴリ等)
    pg.evaluate("pickMenu('自由')"); pg.evaluate("openExSheet()"); pg.wait_for_timeout(40)
    st3=pg.evaluate("()=>({exCat:exCat, valid:!!gymPresets[exCat]})")
    rec('FREE_FALLBACK', st3['valid'], f"{st3}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
