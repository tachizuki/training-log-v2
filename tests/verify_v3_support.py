# -*- coding: utf-8 -*-
# サポートボタン（アプリを評価／お問い合わせ）のJS結線を検証。
# 疑似AndroidBridgeを注入し、正しいネイティブ関数を呼ぶか・フォームのバリデーション・送信結果処理を確認。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    def newpage():
        pg=b.new_page(viewport={'width':412,'height':915}); pg._errs=[]
        pg.on('pageerror',lambda e:pg._errs.append(str(e)))
        pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()'); pg.evaluate("go('set')")
        return pg

    # ===== ブリッジ無し（ブラウザ）: 無反応でなくフォールバック動作 =====
    pg=newpage()
    pg.evaluate("reviewApp()"); pg.wait_for_timeout(30)
    rv=pg.evaluate("()=>document.getElementById('toast').textContent")
    rec('S-REVIEW-FB', 'ストア' in rv or 'store' in rv.lower(), f'review fallback toast={rv!r}')
    pg.evaluate("contactApp()"); pg.wait_for_timeout(30)
    opened=pg.evaluate("()=>document.getElementById('contact-sheet').classList.contains('open')")
    rec('S-CONTACT-OPEN', opened, 'contact sheet opens')
    # 空送信→バリデーション（送信されない）
    pg.evaluate("()=>{document.getElementById('contact-subject').value=''; document.getElementById('contact-body').value=''; submitContact();}"); pg.wait_for_timeout(30)
    vmsg=pg.evaluate("()=>document.getElementById('toast').textContent")
    rec('S-CONTACT-VALID', ('入力' in vmsg) or ('fill' in vmsg.lower()), f'validation toast={vmsg!r}')
    rec('S-ERR1', not pg._errs, f'errs={pg._errs[:2]}')
    pg.close()

    # ===== 疑似ブリッジ注入（実機相当）: 正しいネイティブ関数を呼ぶ =====
    pg=newpage()
    pg.evaluate("""()=>{ window.AndroidBridge={ _calls:[],
        openPlayStore(){ this._calls.push(['openPlayStore']); },
        httpPost(url, body){ this._calls.push(['httpPost', url, body]); },
        sendContactForm(s){ this._calls.push(['sendContactForm', s]); } }; }""")
    # 評価 → openPlayStore を呼ぶ
    pg.evaluate("reviewApp()"); pg.wait_for_timeout(20)
    rec('S-REVIEW-STORE', pg.evaluate("()=>AndroidBridge._calls.some(c=>c[0]==='openPlayStore')"), 'review calls openPlayStore')
    # お問い合わせ → フォーム入力 → GAS(httpPost) に本文付きで渡る（メール通知経路）
    pg.evaluate("contactApp()"); pg.wait_for_timeout(20)
    pg.evaluate("""()=>{ document.getElementById('contact-category').value='bug';
        document.getElementById('contact-subject').value='テスト件名';
        document.getElementById('contact-body').value='テスト本文です'; submitContact(); }"""); pg.wait_for_timeout(30)
    sent=pg.evaluate("""()=>{ const c=AndroidBridge._calls.find(x=>x[0]==='httpPost'); if(!c) return null; try{ return {url:c[1], p:JSON.parse(c[2])}; }catch(e){ return {url:c[1], raw:c[2]}; } }""")
    ok_send = bool(sent) and 'script.google.com' in (sent.get('url') or '') and sent.get('p',{}).get('body')=='テスト本文です' and sent.get('p',{}).get('subject')=='テスト件名'
    rec('S-CONTACT-SEND', ok_send, f'gas call={sent}')
    # 送信成功コールバック → シートが閉じ、入力クリア
    pg.evaluate("onContactSent(true)"); pg.wait_for_timeout(30)
    after=pg.evaluate("()=>({open:document.getElementById('contact-sheet').classList.contains('open'), subj:document.getElementById('contact-subject').value, body:document.getElementById('contact-body').value})")
    rec('S-CONTACT-DONE', (not after['open']) and after['subj']=='' and after['body']=='', f'{after}')
    rec('S-ERR2', not pg._errs, f'errs={pg._errs[:2]}')
    pg.close()
    b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
