# -*- coding: utf-8 -*-
# サインアウト/アカウント削除でローカルデータが消去されることを検証（残留表示バグ修正）。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept())   # confirm(サインアウト) を承認
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')

    # ===== サインアウト: データ消去・端末プレフ(言語/オンボ)は残す =====
    pg.evaluate("""()=>{
      localStorage.setItem('app_lang','ja'); localStorage.setItem('onboarding_done','1');
      localStorage.setItem('training_records', JSON.stringify([{date:'2026-06-16',weight:60}]));
      localStorage.setItem('gym_data', JSON.stringify({'2026-06-16':{exercises:[{name:'ベンチプレス',sets:[]}]}}));
      localStorage.setItem('water_data', JSON.stringify({'2026-06-16':{total:500,log:[]}}));
      localStorage.setItem('nutrition_goals', JSON.stringify({p:150}));
      localStorage.setItem('is_premium','true');
      onFirebaseSignIn('u1','テスト太郎','t@example.com');
    }""")
    pg.evaluate("doSignOut()"); pg.evaluate("document.getElementById('confirm-ok').click()"); pg.wait_for_timeout(60)
    after=pg.evaluate("""()=>({
      rec: localStorage.getItem('training_records'),
      gym: localStorage.getItem('gym_data'),
      water: localStorage.getItem('water_data'),
      ng: localStorage.getItem('nutrition_goals'),
      prem: localStorage.getItem('is_premium'),
      lang: localStorage.getItem('app_lang'),
      ob: localStorage.getItem('onboarding_done'),
      user: !!window.currentUser
    })""")
    cleared = (after['rec'] is None and after['gym'] is None and after['water'] is None and after['ng'] is None and after['prem'] is None and (not after['user']))
    kept = (after['lang']=='ja' and after['ob']=='1')
    rec('SO-SIGNOUT', cleared and kept, f'cleared={cleared} keptPrefs={kept} {after}')
    pg.close()

    # ===== アカウント削除: 全消去 =====
    pg2=b.new_page(viewport={'width':412,'height':915}); pg2._errs=[]
    pg2.on('pageerror',lambda e:pg2._errs.append(str(e)))
    pg2.goto(URI,wait_until='load'); pg2.evaluate('obFinish()')
    pg2.evaluate("""()=>{
      localStorage.setItem('training_records', JSON.stringify([{date:'2026-06-16',weight:60}]));
      localStorage.setItem('app_lang','ja');
      onFirebaseSignIn('u1','太郎','t@example.com');
      onAccountDeleted(true);
    }""")
    pg2.wait_for_timeout(60)
    n=pg2.evaluate("()=>localStorage.length")
    rec('SO-DELETE', n==0 and not pg2._errs, f'localStorage.length={n}')
    pg2.close()
    b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
