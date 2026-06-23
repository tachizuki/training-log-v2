# -*- coding: utf-8 -*-
# 体重変動分析：推定カロリー収支(摂取−基礎代謝−有酸素−歩行)と内訳表示を検証。
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
    def setup(kcal, steps=8000):
        pg.evaluate(f"""()=>{{
          localStorage.setItem('user_profile', JSON.stringify({{height:168,age:25,sex:'male'}}));
          const t=logicalToday(); const d=new Date(t+'T00:00:00'); d.setDate(d.getDate()-1);
          const z=n=>String(n).padStart(2,'0'); const y=d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate());
          localStorage.setItem('training_records', JSON.stringify([
            {{date:y, weight:61, kcal:{kcal}, steps:{steps}}},
            {{date:t, weight:60.8}}
          ]));
        }}""")
        pg.evaluate("go('today'); curDate=logicalToday(); renderToday();"); pg.wait_for_timeout(40)
        return pg.evaluate("()=>document.getElementById('today-analysis').innerHTML")
    h = setup(1100)  # 大幅赤字
    bmr = pg.evaluate("()=>getUserBMR(61)")
    rec('BMR_CALC', bmr and 1560<=bmr<=1580, f"bmr={bmr} (期待~1570)")
    rec('BMR_IN_TEXT', '基礎代謝15' in h, f"breakdown has computed BMR (not 1700 fallback)")
    rec('GOOD', ('推定カロリー収支' in h) and ('十分な赤字' in h) and ('基礎代謝' in h) and ('歩行' in h), f"has十分={'十分な赤字' in h}")
    h2 = setup(2300)
    rec('OVER', '黒字気味' in h2, f"{'黒字気味' in h2}")
    h3 = setup(1600)
    rec('OK', '適度な赤字' in h3, f"{'適度な赤字' in h3}")
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
