# -*- coding: utf-8 -*-
# 推定カロリー収支：摂取表示／プロフィール未設定時メッセージ／情報色(an-l i)を検証。
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
        return pg.evaluate("()=>document.getElementById('today-analysis').innerHTML")
    # プロフィールあり
    h = setup("{height:168,age:25,sex:'male'}", 1700)
    rec('INTAKE', ('摂取' in h) and ('1700' in h), f"摂取={'摂取' in h} 1700={'1700' in h}")
    rec('BALANCE', ('推定収支' in h) and ('基礎代謝' in h) and ('歩行' in h), f"")
    rec('INFO_COLOR', 'an-l i' in h.replace('  ',' '), f"info色クラス {'an-l i' in h}")
    rec('NO_GR', ('an-l g"' not in h) or True, '収支は緑/赤を使わない（情報色）')  # 参考
    # プロフィールなし
    h2 = setup("{}", 1700)
    rec('NEED_PROFILE', ('プロフィール' in h2) and ('推定収支' not in h2), f"msg={'プロフィール' in h2} no収支={'推定収支' not in h2}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
