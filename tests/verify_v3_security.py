# -*- coding: utf-8 -*-
# セキュリティ: 悪意あるデータ(XSSペイロード)を各所に仕込み、描画してもスクリプトが実行されない（esc）・
# 不正/巨大/型違いのインポートでクラッシュしないことを検証。
import pathlib, sys, json
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
PAY = '<img src=x onerror="window.__xss=(window.__xss||0)+1">'
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge'); pg=b.new_page(viewport={'width':412,'height':915})
    pg._errs=[]; pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')

    # 敵対データを各所に投入
    pg.evaluate("""(PAY)=>{
      window.__xss=undefined;
      const today=logicalToday();
      const d=new Date(today+'T00:00:00'); d.setDate(d.getDate()-1); const prev=fmt(d);
      localStorage.setItem('contest_name', PAY);
      localStorage.setItem('contest_date','2026-08-01'); localStorage.setItem('contest_weight','57'); localStorage.setItem('is_premium','true');
      localStorage.setItem('nutrition_goals', JSON.stringify({p:150,f:40,c:180,salt:5}));
      localStorage.setItem('training_records', JSON.stringify([
        {date:prev, weight:PAY, p:PAY, c:PAY, salt:PAY, steps:PAY, cardioKcal:PAY, salon:PAY, trained:true, muscles:[PAY], u:2},
        {date:today, weight:PAY, sleep:PAY, p:150, muscles:[PAY], trained:true, u:2}
      ]));
      const g={}; g[today]={exercises:[
        {name:PAY, sets:[{weight:PAY,reps:PAY,memo:PAY},{weight:60,reps:8,memo:PAY}]},
        {name:'トレッドミル', sets:[], cardio:{time:PAY,speed:PAY,incline:PAY,kcal:PAY}}
      ], u:2};
      localStorage.setItem('gym_data', JSON.stringify(g));
      localStorage.setItem('gym_presets', JSON.stringify({'胸':[PAY,'ベンチプレス'], [PAY]:['x']}));
      const wd={}; wd[prev]={total:1200,log:[{ml:PAY,time:PAY}],u:2}; localStorage.setItem('water_data', JSON.stringify(wd));
    }""", PAY)

    # 各画面を描画（アクティブにして img の load を発火させる）
    for scr in ['today','gym','data','set']:
        pg.evaluate(f"curDate=logicalToday(); go('{scr}')"); pg.wait_for_timeout(60)
    # 種目ピッカー（カテゴリ名/種目名ペイロード）
    pg.evaluate("go('gym'); openExSheet()"); pg.wait_for_timeout(40)
    cats=pg.evaluate("()=>exCats()")
    # 各カテゴリ表示（ペイロードカテゴリ含む）
    pg.evaluate("()=>{ exCats().forEach((c,i)=>{ try{exShowCatI(i);}catch(e){} }); }"); pg.wait_for_timeout(40)
    pg.evaluate("()=>{ const q=document.getElementById('ex-q'); q.value='<img'; exSearch(); }"); pg.wait_for_timeout(40)
    pg.evaluate("closeExSheet()")
    # アカウント（表示名/メールにペイロード）
    pg.evaluate("onFirebaseSignIn('u', '"+PAY.replace('"','\\"')+"', '"+PAY.replace('"','\\"')+"'); go('set')"); pg.wait_for_timeout(60)
    # 筋トレ分析（プレミアム）
    pg.evaluate("go('data'); setPeriod('all'); renderData()"); pg.wait_for_timeout(60)
    # 今日の分析（多要因・前日ペイロード）
    pg.evaluate("go('today'); curDate=logicalToday(); renderToday()"); pg.wait_for_timeout(60)

    xss=pg.evaluate("()=>window.__xss")
    # ペイロードがエスケープされ、テキストとして残っている（=描画はされるが実行されない）
    leaked=pg.evaluate("()=>document.querySelectorAll('img[onerror]').length")
    rec('SEC-XSS', (xss is None) and leaked==0, f'__xss={xss} imgWithOnerror={leaked}')
    rec('SEC-NOCRASH', not pg._errs, f'errs={pg._errs[:3]}')

    # 不正インポート（型違い・壊れ・巨大）でクラッシュしない
    pg.evaluate("""()=>{
      try{ receiveImportData('not json {'); }catch(e){}
      try{ receiveImportData(JSON.stringify({training_records:'\"a string not array\"', gym_data: 12345, water_data: [1,2], nutrition_goals:'oops'})); }catch(e){}
      try{ receiveImportData(JSON.stringify([1,2,3])); }catch(e){}
      try{ go('today'); go('gym'); go('data'); }catch(e){}
    }"""); pg.wait_for_timeout(60)
    # DBアクセサが安全な型を返す
    safe=pg.evaluate("()=>({rec:Array.isArray(DB.records()), gym:(typeof DB.gym()==='object'&&!Array.isArray(DB.gym())), water:(typeof DB.water()==='object'&&!Array.isArray(DB.water()))})")
    rec('SEC-IMPORT', safe['rec'] and safe['gym'] and safe['water'] and not pg._errs, f'safe={safe} errs={pg._errs[:2]}')

    print("cats sample:", cats[:3])
    pg.close(); b.close()

passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
