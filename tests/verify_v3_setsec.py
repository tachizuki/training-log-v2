# -*- coding: utf-8 -*-
# 設定アコーディオン: 開状態ハイライト＋他タブ往復で全閉、を検証。
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
    pg.evaluate("go('set')"); pg.wait_for_timeout(40)
    # 最初のセクションを開く
    pg.evaluate("()=>{const h=document.querySelector('.set-sec.collap'); h.click();}"); pg.wait_for_timeout(40)
    st=pg.evaluate("""()=>{const h=document.querySelector('.set-sec.collap');
      const cs=getComputedStyle(h); const card=h.nextElementSibling;
      return {open:h.classList.contains('open'), cardShown:!card.classList.contains('sec-hidden'),
              chev:getComputedStyle(h,'::after').color, bdr:cs.borderColor};}""")
    rec('OPEN', st['open'] and st['cardShown'], f"{st}")
    # 開いてる時はライム系ハイライト（▾の色がfaintでない）
    rec('HILIGHT', 'rgb' in st['chev'] and st['chev']!='rgb(84, 92, 100)', f"chev={st['chev']}")
    # 別タブへ→設定に戻る
    pg.evaluate("go('today')"); pg.wait_for_timeout(30)
    pg.evaluate("go('set')"); pg.wait_for_timeout(40)
    after=pg.evaluate("""()=>{const heads=[...document.querySelectorAll('.set-sec.collap')];
      const shownAccordion=heads.filter(h=>{const c=h.nextElementSibling; return c&&c.classList.contains('set-card')&&!c.classList.contains('sec-hidden');}).length;
      return {openCount:document.querySelectorAll('.set-sec.collap.open').length, shownAccordion};}""")
    rec('RESET', after['openCount']==0 and after['shownAccordion']==0, f"{after}")
    # goContestSettings は往復リセット後でも開ける
    pg.evaluate("goContestSettings()"); pg.wait_for_timeout(60)
    con=pg.evaluate("()=>{const s=document.getElementById('sec-contest'); return {open:s.classList.contains('open')};}")
    rec('CONTEST_OPEN', con['open'], f"{con}")
    # アカウント欄: 未ログイン時はアコーディオンにしない（ログインボタン常時表示）
    pg.evaluate("onFirebaseSignOut && onFirebaseSignOut()"); pg.evaluate("window.currentUser=null; renderAccountCard(); go('set')"); pg.wait_for_timeout(40)
    out=pg.evaluate("()=>{const h=document.getElementById('sec-account-head'); const c=document.getElementById('account-card'); return {collap:h.classList.contains('collap'), shown:!c.classList.contains('sec-hidden'), hasLogin:!!c.querySelector('.acc-google')};}")
    rec('ACC_LOGGEDOUT', (not out['collap']) and out['shown'] and out['hasLogin'], f"{out}")
    # ログイン時はアコーディオン（初期は閉）、展開で削除ボタン出現
    pg.evaluate("onFirebaseSignIn('u1','テスト太郎','t@example.com'); go('set')"); pg.wait_for_timeout(40)
    li=pg.evaluate("()=>{const h=document.getElementById('sec-account-head'); const c=document.getElementById('account-card'); return {collap:h.classList.contains('collap'), hiddenDefault:c.classList.contains('sec-hidden')};}")
    rec('ACC_LOGGEDIN', li['collap'] and li['hiddenDefault'], f"{li}")
    pg.evaluate("()=>document.getElementById('sec-account-head').click()"); pg.wait_for_timeout(40)
    ex=pg.evaluate("()=>{const h=document.getElementById('sec-account-head'); const c=document.getElementById('account-card'); return {open:h.classList.contains('open'), shown:!c.classList.contains('sec-hidden'), hasDel:!!c.querySelector('.acc-danger')};}")
    rec('ACC_EXPAND', ex['open'] and ex['shown'] and ex['hasDel'], f"{ex}")
    rec('NOERR', not pg._errs, f"errs={pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
