# -*- coding: utf-8 -*-
# 推定カロリー収支：摂取表示／符号で色(マイナス=g緑/プラス=b赤)／未設定時のみ情報色(i)メッセージ。
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
    def setup(profile_json, kcal, steps=8000):
        pg.evaluate(f"""()=>{{
          localStorage.setItem('user_profile', JSON.stringify({profile_json}));
          const t=logicalToday(); const d=new Date(t+'T00:00:00'); d.setDate(d.getDate()-1);
          const z=n=>String(n).padStart(2,'0'); const y=d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate());
          localStorage.setItem('training_records', JSON.stringify([
            {{date:y, weight:61, kcal:{kcal}, steps:{steps}}},
            {{date:t, weight:60.8}}
          ]));
        }}""")
        pg.evaluate("go('today'); curDate=logicalToday(); renderToday();"); pg.wait_for_timeout(40)
        return pg.evaluate("""()=>{const root=document.getElementById('today-analysis');
          const bal=[...root.querySelectorAll('.an-l')].find(d=>d.textContent.includes('収支'));
          const msg=[...root.querySelectorAll('.an-l')].find(d=>d.textContent.includes('プロフィール'));
          return {html:root.innerHTML, balCls:(bal?bal.className:''), msgCls:(msg?msg.className:'')};}""")
    # プロフィールあり・赤字 → 緑(g)
    r1 = setup("{height:168,age:25,sex:'male'}", 1100)
    rec('DEFICIT_GREEN', ('摂取' in r1['html']) and ('1100' in r1['html']) and ('g' in r1['balCls'].split()), f"balCls={r1['balCls']}")
    # プロフィールあり・黒字 → 赤(b)
    r2 = setup("{height:168,age:25,sex:'male'}", 2500)
    rec('SURPLUS_RED', 'b' in r2['balCls'].split(), f"balCls={r2['balCls']}")
    # プロフィールなし → 情報色(i)メッセージ・収支なし
    r3 = setup("{}", 1700)
    rec('NEED_PROFILE_INFO', ('i' in r3['msgCls'].split()) and ('推定収支' not in r3['html']), f"msgCls={r3['msgCls']}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
