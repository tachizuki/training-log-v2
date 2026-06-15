# -*- coding: utf-8 -*-
# 観点漏れ（設計書6/15以降に追加された機能）の自動検証。
# 対象: 大会按分テーブル(週/月)・按分線グラフ・価格表示・$プレースホルダ回帰・
#        アカウント注記・admin解放・多要因分析・不正import・起点時刻即反映・新規i18n。
import pathlib, sys
from playwright.sync_api import sync_playwright

URI = pathlib.Path('index-v3.html').resolve().as_uri()
BACKUP = 'G:/マイドライブ/traininglog_backup_2026-06-15.json'
results = {}
def rec(tc, ok, detail=''): results[tc] = (bool(ok), detail)

def newpage(b):
    pg = b.new_page(viewport={'width': 412, 'height': 915})
    pg._errs = []
    pg.on('pageerror', lambda e: pg._errs.append(str(e)))
    pg.goto(URI, wait_until='load'); pg.wait_for_timeout(80)
    pg.evaluate('obFinish()')
    return pg

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel='msedge')
    raw = open(BACKUP, encoding='utf-8').read()

    # ===== PREMIUM + 大会設定（按分テーブル/グラフ） =====
    pg = newpage(b)
    pg.evaluate("(s)=>receiveImportData(s)", raw); pg.wait_for_timeout(80)
    # 大会設定を確実に投入（importに含まれない場合の保険）
    pg.evaluate("localStorage.setItem('contest_date','2026-08-01'); localStorage.setItem('contest_weight','57'); localStorage.setItem('contest_name','APFファーストタイマー'); localStorage.setItem('is_premium','true');")
    plan = pg.evaluate("()=>roadmapPlan()")
    rec('X-RM00', plan and not plan.get('trivial'), f'plan={plan}')

    # X-RM01 週次按分テーブル（プレミアム）
    pg.evaluate("go('data'); setPeriod('week'); renderData()"); pg.wait_for_timeout(60)
    wk = pg.evaluate("()=>({rmtable:!!document.querySelector('#week-table .rmtable'), wtable:!!document.querySelector('#week-table .wtable'), title:document.getElementById('week-table-title').textContent, rows:document.querySelectorAll('#week-table .rmtable tr').length, cur:!!document.querySelector('#week-table .rmtable tr.cur')})")
    rec('X-RM01', wk['rmtable'] and not wk['wtable'] and wk['rows']>1, f"title={wk['title']} rows={wk['rows']} cur={wk['cur']}")
    # X-RM02 月次按分テーブル
    pg.evaluate("setPeriod('month'); renderData()"); pg.wait_for_timeout(60)
    mo = pg.evaluate("()=>({rmtable:!!document.querySelector('#week-table .rmtable'), title:document.getElementById('week-table-title').textContent, hd:(document.querySelector('#week-table .rmtable tr.hd td')||{}).textContent})")
    rec('X-RM02', mo['rmtable'], f"title={mo['title']} hd={mo['hd']}")
    # X-CH01 按分目標線＋当日目標注記（プレミアム）
    pg.evaluate("setPeriod('all'); renderData()"); pg.wait_for_timeout(60)
    ch = pg.evaluate("()=>{const s=document.getElementById('weight-chart').innerHTML; return {goal:s.indexOf('"+"目標"+"')>=0 || s.indexOf(t('rm_goal'))>=0, redline:s.indexOf('#f87171')>=0};}")
    rec('X-CH01', ch['goal'] and ch['redline'], f"goal={ch['goal']} redline={ch['redline']}")
    # X-RM04 targetAt 線形按分（境界＋中点）
    lin = pg.evaluate("""()=>{const pl=roadmapPlan(); if(!pl) return null;
        const s=targetAt(pl, pl.startDate), e=targetAt(pl, pl.endDate);
        const md=new Date((new Date(pl.startDate)-0 + (new Date(pl.endDate)-0))/2); const mid=md.toISOString().slice(0,10);
        const m=targetAt(pl, mid); const expMid=(pl.startWeight+pl.endWeight)/2;
        return {s, e, sw:pl.startWeight, ew:pl.endWeight, m, expMid};}""")
    rec('X-RM04', lin and abs(lin['s']-lin['sw'])<0.01 and abs(lin['e']-lin['ew'])<0.01 and abs(lin['m']-lin['expMid'])<0.2, f"{lin}")
    pg.close()

    # ===== FREE：按分でなく平均テーブル＆目標線なし =====
    pg = newpage(b)
    pg.evaluate("(s)=>receiveImportData(s)", raw); pg.wait_for_timeout(80)
    pg.evaluate("localStorage.removeItem('is_premium'); localStorage.setItem('contest_date','2026-08-01'); localStorage.setItem('contest_weight','57'); window.currentUser=null;")
    pg.evaluate("go('data'); setPeriod('week'); renderData()"); pg.wait_for_timeout(60)
    fr = pg.evaluate("()=>({wtable:!!document.querySelector('#week-table .wtable'), rmtable:!!document.querySelector('#week-table .rmtable')})")
    rec('X-RM03', fr['wtable'] and not fr['rmtable'], f"{fr}")
    pg.evaluate("setPeriod('all'); renderData()"); pg.wait_for_timeout(60)
    frc = pg.evaluate("()=>document.getElementById('weight-chart').innerHTML.indexOf('#f87171')>=0")
    rec('X-CH02', not frc, 'free: no premium target line')
    pg.close()

    # ===== ペイウォール：価格表示・$回帰・アカウント注記 =====
    pg = newpage(b)
    pg.evaluate("onPremiumPriceLoaded('¥480'); openPaywall()"); pg.wait_for_timeout(40)
    pn = pg.evaluate("()=>document.getElementById('paywall-price-note').textContent")
    rec('X-PW02', '¥480' in pn, f'price-note={pn}')
    pg.evaluate("onPremiumPriceLoaded('$4.99'); updatePaywallPrice()"); pg.wait_for_timeout(20)
    pn2 = pg.evaluate("()=>document.getElementById('paywall-price-note').textContent")
    rec('X-PW03', '$4.99' in pn2 and 'US.99' not in pn2, f'price-note=$ -> {pn2}')
    acct = pg.evaluate("()=>{const e=document.querySelector('.pw-acct-note'); return e?e.textContent:null;}")
    keyv = pg.evaluate("()=>t('paywall_account_note')")
    rec('X-PW04', acct and acct==keyv and 'Play' in acct, 'account-binding note shown')
    pg.close()

    # ===== admin 解放 =====
    pg = newpage(b)
    pg.evaluate("window.currentUser={email:'moyaki397@gmail.com'}; localStorage.removeItem('is_premium');")
    adm = pg.evaluate("()=>({admin:isAdmin(), prem:isPremium(), real:isPremiumReal()})")
    rec('X-ADM01', adm['admin'] and adm['real'], f'admin unlock -> {adm}')
    pg.evaluate("window.currentUser={email:'someone@example.com'}; localStorage.removeItem('is_premium');")
    adm2 = pg.evaluate("()=>({admin:isAdmin(), real:isPremiumReal()})")
    rec('X-ADM02', (not adm2['admin']) and (not adm2['real']), f'non-admin -> {adm2}')
    pg.close()

    # ===== 多要因 体重変動分析 =====
    pg = newpage(b)
    pg.evaluate("""()=>{
        const today=logicalToday(); const d=new Date(today+'T00:00:00'); d.setDate(d.getDate()-1);
        const prev=fmt(d);
        localStorage.setItem('training_records', JSON.stringify([
          {date:prev, weight:60.5, salt:9, salon:35, p:200,f:80,c:300, kcal:3140},
          {date:today, weight:60.0, p:150,f:50,c:200}
        ]));
        localStorage.setItem('nutrition_goals', JSON.stringify({p:150,f:40,c:180,salt:5}));
        const wd={}; wd[prev]={total:1200, log:[]}; localStorage.setItem('water_data', JSON.stringify(wd));
        curDate=today; renderToday();
    }"""); pg.wait_for_timeout(60)
    an = pg.evaluate("()=>{const el=document.getElementById('today-analysis'); return {n:el.querySelectorAll('.an-l').length, html:el.innerHTML};}")
    has_salt = '塩分' in an['html'] or 'salt' in an['html'].lower()
    has_water = '水分' in an['html'] or 'water' in an['html'].lower()
    has_kcal = '🔥' in an['html']
    rec('X-AN01', an['n']>=4 and has_salt and has_water and has_kcal and not pg._errs, f"lines={an['n']} salt={has_salt} water={has_water} kcal={has_kcal}")
    pg.close()

    # ===== 不正JSONインポート（エラー推測） =====
    pg = newpage(b)
    pg.evaluate("(s)=>{try{receiveImportData(s);}catch(e){}}", "{これは壊れたJSON,,,"); pg.wait_for_timeout(60)
    still = pg.evaluate("()=>{try{go('today'); renderToday(); return true;}catch(e){return false;}}")
    rec('X-IMP01', still and not pg._errs, f'malformed import handled, errs={pg._errs[:1]}')
    pg.close()

    # ===== 起点時刻の即反映（再起動不要） =====
    pg = newpage(b)
    res = pg.evaluate("""()=>{
        const h=new Date().getHours();
        localStorage.setItem('day_start_hour','0'); const t0=logicalToday();
        // 現在時刻より後の起点なら logicalToday は前日になる
        const future=(h+1)%24; localStorage.setItem('day_start_hour', String(future)); const t1=logicalToday();
        return {h, t0, future, t1, changed:(future>h ? t1<t0 : true)};
    }""")
    rec('X-SET01', res['t0']!=res['t1'] if res['future']>res['h'] else True, f"hour={res['h']} t0={res['t0']} t1={res['t1']}")
    pg.close()

    # ===== 新規i18nキーの JA/EN 充足 =====
    pg = newpage(b)
    keys = ['rm_weekly_title','rm_monthly_title','rm_col_target','rm_col_actual','rm_col_week','rm_col_month','rm_goal','paywall_account_note','price_note','week_table_title','month_table_title','wa_salt_high','wa_water_low']
    miss = {'ja':[], 'en':[]}
    for lang in ('ja','en'):
        pg.evaluate(f"setLang('{lang}')"); pg.wait_for_timeout(20)
        for k in keys:
            v = pg.evaluate(f"()=>t('{k}')")
            if (not v) or v==k: miss[lang].append(k)
    rec('X-I18N01', not miss['ja'] and not miss['en'], f"missing={miss}")
    pg.close()
    b.close()

# ---- report ----
passed=[k for k,v in results.items() if v[0]]; failed=[k for k,v in results.items() if not v[0]]
for k in sorted(results):
    ok,detail=results[k]; print(f"{'PASS' if ok else 'FAIL'}  {k}  {detail}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
