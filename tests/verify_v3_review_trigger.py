# -*- coding: utf-8 -*-
# In-App Review トリガー（記録が累計7日で1回だけ requestReview）の検証。
# 仕様: upsertRec後に判定。7日未満/ブリッジ無し=発火しない。7日到達+ブリッジ有=1200ms後に1回だけ発火し
#       review_asked=1 を保存。以後は保存が増えても再発火しない。ブラウザ(ブリッジ無し)ではフラグを消費しない。
import pathlib, sys
from playwright.sync_api import sync_playwright
URI = pathlib.Path('index-v3.html').resolve().as_uri()
results={}
def rec(tc,ok,detail=''): results[tc]=(bool(ok),detail)
def seed(pg, days):
    pg.evaluate("""(days)=>{
      const recs=[]; const t=new Date(logicalToday()+'T00:00:00');
      for(let i=0;i<days;i++){ const d=new Date(t); d.setDate(d.getDate()-i); recs.push({date:fmt(d), weight:62.0, sleep:null, steps:null, p:null, trained:false, muscles:[], memo:''}); }
      localStorage.setItem('training_records', JSON.stringify(recs));
    }""", days)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,channel='msedge')
    pg=b.new_page(viewport={'width':414,'height':900}); pg._errs=[]
    pg.on('pageerror',lambda e:pg._errs.append(str(e)))
    pg.goto(URI,wait_until='load'); pg.evaluate('obFinish()')
    # ブリッジ(spy)を用意
    pg.evaluate("window.__rr=0; window.AndroidBridge={requestReview:function(){window.__rr++;}};")
    # ① 6日分では発火しない
    seed(pg,6)
    pg.evaluate("const r=getRec(logicalToday())||blankRec(logicalToday()); r.weight=61.9; upsertRec(r);")
    pg.wait_for_timeout(1600)
    rec('NO_FIRE_UNDER_7', pg.evaluate("()=>window.__rr")==0 and pg.evaluate("()=>localStorage.getItem('review_asked')")!='1')
    # ② 7日分に到達で1回発火・フラグ保存
    seed(pg,7)
    pg.evaluate("const r=getRec(logicalToday())||blankRec(logicalToday()); r.weight=61.8; upsertRec(r);")
    pg.wait_for_timeout(1700)
    rec('FIRE_AT_7', pg.evaluate("()=>window.__rr")==1, f"calls={pg.evaluate('()=>window.__rr')}")
    rec('FLAG_SET', pg.evaluate("()=>localStorage.getItem('review_asked')")=='1')
    # ③ 以後は保存しても再発火しない
    pg.evaluate("const r=getRec(logicalToday()); r.weight=61.7; upsertRec(r);")
    pg.wait_for_timeout(1600)
    rec('NO_REFIRE', pg.evaluate("()=>window.__rr")==1)
    # ④ ブリッジ無し(ブラウザ)ではフラグを消費しない
    pg.evaluate("localStorage.removeItem('review_asked'); window.AndroidBridge=undefined; _revTimer=null;")
    pg.evaluate("const r=getRec(logicalToday()); r.weight=61.6; upsertRec(r);")
    pg.wait_for_timeout(1600)
    rec('BROWSER_NO_CONSUME', pg.evaluate("()=>localStorage.getItem('review_asked')")!='1')
    rec('NOERR', not pg._errs, f"{pg._errs[:2]}")
    pg.close(); b.close()
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results): ok,d=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {d}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
sys.exit(0 if not failed else 1)
