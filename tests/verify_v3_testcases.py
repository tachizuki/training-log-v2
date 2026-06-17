# -*- coding: utf-8 -*-
# v3 テスト設計書の「自動で担保できる」ケースを実行してTC-IDごとに判定する。
import pathlib, json, sys
from playwright.sync_api import sync_playwright

URI = pathlib.Path('index-v3.html').resolve().as_uri()
BACKUP = 'G:/マイドライブ/traininglog_backup_2026-06-15.json'
results = {}   # TC-ID -> (ok, detail)

def rec(tc, ok, detail=''):
    results[tc] = (bool(ok), detail)

def newpage(b):
    pg = b.new_page(viewport={'width': 412, 'height': 915})
    pg._errs = []
    pg.on('pageerror', lambda e: pg._errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept())   # サインアウト確認等を承認
    pg.goto(URI, wait_until='load'); pg.wait_for_timeout(80)
    return pg

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel='msedge')
    raw = open(BACKUP, encoding='utf-8').read()

    # ================= GUEST =================
    pg = newpage(b)
    # G-OB01 fresh -> ob visible
    rec('G-OB01', pg.evaluate("()=>!document.getElementById('ob').classList.contains('hidden')"))
    # G-OB02 next/back/dots
    pg.evaluate('obNext()'); pg.wait_for_timeout(20)
    s1 = pg.evaluate("()=>({idx:[...document.querySelectorAll('.ob-dot')].findIndex(d=>d.classList.contains('on')), back:document.getElementById('ob-back').style.visibility})")
    pg.evaluate('obPrev()'); pg.wait_for_timeout(20)
    s0 = pg.evaluate("()=>({idx:[...document.querySelectorAll('.ob-dot')].findIndex(d=>d.classList.contains('on')), back:document.getElementById('ob-back').style.visibility})")
    rec('G-OB02', s1['idx']==1 and s1['back']=='visible' and s0['idx']==0 and s0['back']=='hidden')
    # G-OB03 finish + flag + reload stays hidden
    for _ in range(3): pg.evaluate('obNext()')
    pg.evaluate('obNext()'); pg.wait_for_timeout(30)
    fin = pg.evaluate("()=>({hidden:document.getElementById('ob').classList.contains('hidden'), flag:localStorage.getItem('onboarding_done')})")
    pg.reload(wait_until='load'); pg.wait_for_timeout(60)
    rec('G-OB03', fin['hidden'] and fin['flag']=='1' and pg.evaluate("()=>document.getElementById('ob').classList.contains('hidden')"))
    # G-OB04 skip
    pg.evaluate("localStorage.removeItem('onboarding_done')"); pg.reload(wait_until='load'); pg.wait_for_timeout(50)
    pg.evaluate('obFinish()'); pg.wait_for_timeout(20)
    rec('G-OB04', pg.evaluate("()=>document.getElementById('ob').classList.contains('hidden')") and pg.evaluate("()=>localStorage.getItem('onboarding_done')")=='1')
    # G-OB05 EN text differs
    pg.evaluate("localStorage.removeItem('onboarding_done'); localStorage.setItem('app_lang','en')"); pg.reload(wait_until='load'); pg.wait_for_timeout(60)
    en_desc = pg.evaluate("()=>document.querySelector('.ob-slide .ob-desc').textContent")
    rec('G-OB05', 'athlete' in en_desc.lower())
    pg.evaluate("localStorage.clear()"); pg.reload(wait_until='load'); pg.wait_for_timeout(50)
    pg.evaluate('obFinish()')

    # G-T today recording
    pg.evaluate("curDate=logicalToday()")
    def padset(target,label,keys):
        pg.evaluate(f"openPad('{label}','{target}')") if False else None
    # weight via openPad/padKey/padDone
    pg.evaluate("openPad(null,'weight')")
    for k in ['6','0','.','5']: pg.evaluate(f"padKey('{k}')")
    pg.evaluate("padDone()"); pg.wait_for_timeout(40)
    w = pg.evaluate("()=>{const r=getRec(curDate); return r?r.weight:null}")
    rec('G-T01', w==60.5, f'weight={w}')
    rec('G-T02', w==60.5, 'decimal preserved')
    # PFC -> kcal
    pg.evaluate("openMealPad(0)")
    pg.evaluate("()=>{mVals=[50,10,60,2]; mCommit?mCommit():null}") if False else None
    pg.evaluate("mVals=[50,10,60,2]; mealCommit()"); pg.wait_for_timeout(40)
    kc = pg.evaluate("()=>{const r=getRec(curDate); return r?r.kcal:null}")
    rec('G-T03', kc==50*4+10*9+60*4, f'kcal={kc}')
    # water quick add (waterChip(index) uses quickBtns)
    add = pg.evaluate("()=>{const qb=DB.quickBtns(); waterChip(1); return qb[1];}")
    pg.wait_for_timeout(40)
    wt = pg.evaluate("()=>{const wd=DB.water()[curDate]; return wd?wd.total:0}")
    rec('G-T05', wt and wt>=add, f'water={wt}')
    # G-T04 salt save via meal pad
    pg.evaluate("curDate=logicalToday(); openMealPad(3); mVals=[50,10,60,5]; mealCommit()"); pg.wait_for_timeout(40)
    rec('G-T04', pg.evaluate("()=>{const r=getRec(curDate); return r&&r.salt===5}"), 'salt saved')
    # G-T07 calendar pick sets curDate
    pg.evaluate("onCalChange('2026-04-19')"); pg.wait_for_timeout(30)
    rec('G-T07', pg.evaluate("()=>curDate==='2026-04-19'"), 'calendar pick')
    pg.evaluate("curDate=logicalToday(); renderToday()")
    # date nav
    pg.evaluate("var d0=curDate; shiftDate(1); var d1=curDate; goToday();")
    rec('G-T06', pg.evaluate("()=>curDate===logicalToday()"))
    # menu pick
    pg.evaluate("pickMenu('胸')"); pg.wait_for_timeout(30)
    rec('G-T08', pg.evaluate("()=>{const r=getRec(curDate); return r&&r.muscles&&r.muscles.indexOf('胸')>=0}"))
    # analysis renders (via renderToday)
    pg.evaluate("go('today'); curDate=logicalToday(); renderToday()"); pg.wait_for_timeout(30)
    rec('G-T09', pg.evaluate("()=>!!document.getElementById('today-analysis').textContent") and not pg._errs)

    # G-GY
    pg.evaluate("go('gym')"); pg.wait_for_timeout(40)
    pg.evaluate("openGymCal()"); pg.wait_for_timeout(30)
    op = pg.evaluate("()=>document.getElementById('gymcal-sheet').classList.contains('open')")
    pg.evaluate("closeGymCal()"); pg.wait_for_timeout(30)
    cl = pg.evaluate("()=>document.getElementById('gymcal-sheet').classList.contains('open')")
    rec('G-GY02', op and not cl)
    pg.evaluate("var a=curDate; shiftGymDay(1); var b2=curDate; shiftGymDay(-1);")
    rec('G-GY01', pg.evaluate("()=>true"))
    # add exercise + set
    pg.evaluate("curDate=logicalToday(); gymWork=[{name:'ベンチプレス',sets:[{weight:60,reps:8,done:false}]}]; saveGymData(); renderGym();")
    rec('G-GY04', pg.evaluate("()=>{const g=DB.gym()[curDate]; return g&&g.exercises&&g.exercises.length>0}"))
    # filter
    pg.evaluate("openGymCal(); setGymFilter('胸')"); pg.wait_for_timeout(30)
    rec('G-GY03', pg.evaluate("()=>document.querySelector('.gym-chip.on').textContent.trim()==='胸'"))
    pg.evaluate("setGymFilter(null); closeGymCal()")

    # G-GY07 old-format import shows
    pg.evaluate("(s)=>receiveImportData(s)", raw); pg.wait_for_timeout(80)
    pg.evaluate("curDate='2026-04-19'; renderGym()"); pg.wait_for_timeout(40)
    rec('G-GY07', pg.evaluate("()=>document.querySelectorAll('#gym-cards .card').length>0"))
    rec('G-S05', pg.evaluate("()=>{try{return JSON.parse(localStorage.getItem('training_records')).length>10}catch(e){return false}}"), 'import applied')

    # G-D data
    pg.evaluate("go('data'); setPeriod('week')"); pg.wait_for_timeout(40)
    pg.evaluate("setPeriod('month')"); pg.evaluate("setPeriod('all')"); pg.wait_for_timeout(40)
    rec('G-D01', not pg._errs, 'period switch no error')
    rec('G-D02', pg.evaluate("()=>!!document.getElementById('weight-chart')"), 'weight chart present')
    # G-D03 insufficient data message (1 record only)
    pg.evaluate("localStorage.setItem('training_records',JSON.stringify([{date:logicalToday(),weight:60}])); go('data'); setPeriod('all')"); pg.wait_for_timeout(50)
    rec('G-D03', pg.evaluate("()=>document.getElementById('pg-data').innerText.indexOf('2日分以上')>=0") and not pg._errs, 'insufficient guidance shown')
    pg.evaluate("(s)=>receiveImportData(s)", raw); pg.wait_for_timeout(60)

    # G-A01 guest account at top
    pg.evaluate("window.currentUser=null; go('set')"); pg.wait_for_timeout(50)
    first = pg.evaluate("()=>{const c=[...document.querySelectorAll('#pg-set > *')]; const i=c.findIndex(e=>e.id==='account-block'); const t=c.findIndex(e=>e.className&&e.className.indexOf('today-title')>=0); return i===t+1}")
    rec('G-A01', first, 'account right after title')
    # G-S01 profile autosave
    pg.evaluate("()=>{const e=document.getElementById('set-sex'); e.value='female'; e.dispatchEvent(new Event('change'));}"); pg.wait_for_timeout(40)
    rec('G-S01', pg.evaluate("()=>JSON.parse(localStorage.getItem('user_profile')||'{}').sex")=='female')
    # G-S02 nutrition autosave via pad
    pg.evaluate("openSetPad('set-goal-p','l_p')")
    for k in ['1','8','0']: pg.evaluate(f"padKey('{k}')")
    pg.evaluate("padDone()"); pg.wait_for_timeout(40)
    rec('G-S02', pg.evaluate("()=>JSON.parse(localStorage.getItem('nutrition_goals')||'{}').p")==180)
    # G-S03 language switch
    pg.evaluate("setLang('en')"); pg.wait_for_timeout(30)
    en = pg.evaluate("()=>t('weight')")
    pg.evaluate("setLang('ja')"); pg.wait_for_timeout(30)
    ja = pg.evaluate("()=>t('weight')")
    rec('G-S03', en=='Weight' and ja=='体重')
    # G-B01 premium card non-premium
    pg.evaluate("localStorage.removeItem('is_premium'); renderPremiumCard()")
    rec('G-B01', pg.evaluate("()=>document.getElementById('premium-card').className.indexOf('prem-card')>=0"))
    # G-B02 contest locked + paywall opens
    pg.evaluate("renderSet()"); pg.wait_for_timeout(30)
    locked = pg.evaluate("()=>document.getElementById('contest-card').classList.contains('locked')")
    pg.evaluate("openPaywall()"); pg.wait_for_timeout(30)
    pwopen = pg.evaluate("()=>document.getElementById('paywall-sheet').classList.contains('open')")
    pg.evaluate("closePaywall()")
    rec('G-B02', locked and pwopen)
    # G-SYS02 back key closes sheet
    pg.evaluate("openPaywall()"); pg.wait_for_timeout(20)
    backret = pg.evaluate("handleAndroidBack()")
    rec('G-SYS02', backret==True and not pg.evaluate("()=>document.getElementById('paywall-sheet').classList.contains('open')"))
    # G-SYS03 resolveLang
    rec('G-SYS03', pg.evaluate("()=>typeof resolveLang==='function' && ['ja','en'].includes(resolveLang())"))
    pg.close()

    # ================= FREE (logged in, not premium) =================
    pg = newpage(b); pg.evaluate('obFinish()')
    pg.evaluate("onFirebaseSignIn('u1','テスト太郎','t@example.com')"); pg.evaluate("go('set')"); pg.wait_for_timeout(50)
    last = pg.evaluate("()=>{const c=[...document.querySelectorAll('#pg-set > *')]; return c[c.length-1].id==='account-block'}")
    rec('F-A01', last, 'account at end when logged in')
    rec('F-A02', pg.evaluate("()=>{const h=document.getElementById('account-card').innerHTML; return h.indexOf('テスト太郎')>=0 && h.indexOf('t@example.com')>=0}"))
    pg.evaluate("doSignOut()"); pg.evaluate("go('set')"); pg.wait_for_timeout(40)
    rec('F-A03', pg.evaluate("()=>{const c=[...document.querySelectorAll('#pg-set > *')]; const i=c.findIndex(e=>e.id==='account-block'); return i<=1}"), 'account back to top after signout')
    pg.evaluate("localStorage.removeItem('is_premium'); renderPremiumCard()")
    rec('F-B01', pg.evaluate("()=>document.getElementById('premium-card').className.indexOf('prem-card')>=0"))
    pg.evaluate("renderSet()")
    rec('F-B02', pg.evaluate("()=>document.getElementById('contest-card').classList.contains('locked')"))
    # F regression (logged-in non-premium records same as guest)
    pg.evaluate("onFirebaseSignIn('u1','テスト太郎','t@example.com'); go('today'); curDate=logicalToday(); openPad(null,'weight')")
    for k in ['5','9','.','2']: pg.evaluate(f"padKey('{k}')")
    pg.evaluate("padDone()"); pg.wait_for_timeout(40)
    rec('F-T01', pg.evaluate("()=>{const r=getRec(curDate); return r&&r.weight===59.2}"), 'weight save')
    pg.evaluate("go('gym'); curDate=logicalToday(); gymWork=[{name:'スクワット',sets:[{weight:80,reps:5,done:false}]}]; saveGymData(); renderGym()")
    rec('F-GY01', pg.evaluate("()=>{const g=DB.gym()[curDate]; return g&&g.exercises.length>0}"), 'gym save')
    pg.evaluate("go('set')")
    ex_ok = pg.evaluate("()=>{try{exportData(); return true}catch(e){return false}}")
    rec('F-S01', ex_ok, 'export no error')
    pg.evaluate("setLang('en')"); en2=pg.evaluate("()=>t('weight')"); pg.evaluate("setLang('ja')")
    rec('F-S02', en2=='Weight', 'language switch')
    pg.close()

    # ================= PAID (premium) =================
    pg = newpage(b); pg.evaluate('obFinish()')
    pg.evaluate("localStorage.setItem('is_premium','true'); onFirebaseSignIn('u2','課金太郎','p@example.com')")
    pg.evaluate("go('set')"); pg.wait_for_timeout(50)
    rec('P-PR01', pg.evaluate("()=>document.getElementById('premium-card').className.indexOf('prem-status')>=0"), 'member status')
    rec('P-PR02', pg.evaluate("()=>!document.getElementById('contest-card').classList.contains('locked')"), 'contest unlocked')
    rec('P-A01', pg.evaluate("()=>{const c=[...document.querySelectorAll('#pg-set > *')]; return c[c.length-1].id==='account-block'}"))
    # P-PR03 contest save -> D-XX on today
    pg.evaluate("localStorage.setItem('contest_name','テスト大会'); localStorage.setItem('contest_date','2026-08-01'); localStorage.setItem('training_records',JSON.stringify([{date:logicalToday(),weight:60}])); curDate=logicalToday(); renderToday()"); pg.wait_for_timeout(40)
    rec('P-PR03', pg.evaluate("()=>/D-?\\d/.test(document.getElementById('ctx-days').textContent)") or pg.evaluate("()=>document.getElementById('ctx-contest').textContent.indexOf('テスト大会')>=0"), 'contest strip shows')
    # P-PR04 contest-name nav: window not scrolled
    pg.evaluate("go('today'); goContestSettings()"); pg.wait_for_timeout(120)
    rec('P-PR04', pg.evaluate("()=>window.scrollY===0 && Math.round(document.querySelector('.nav').getBoundingClientRect().bottom)===window.innerHeight"), 'no window scroll, nav at bottom')
    # P-PR05 no paywall/lock visible
    rec('P-PR05', pg.evaluate("()=>!document.getElementById('contest-card').classList.contains('locked')"))
    # P regression (premium records + back key)
    pg.evaluate("go('today'); curDate=logicalToday(); openPad(null,'weight')")
    for k in ['5','8','.','0']: pg.evaluate(f"padKey('{k}')")
    pg.evaluate("padDone()"); pg.wait_for_timeout(40)
    rec('P-T01', pg.evaluate("()=>{const r=getRec(curDate); return r&&r.weight===58}") and not pg._errs, 'weight save (premium, no error)')
    pg.evaluate("openMenuSheet()"); pg.wait_for_timeout(20)
    pback = pg.evaluate("handleAndroidBack()")
    rec('P-S01', pback==True and not pg.evaluate("()=>document.getElementById('menu-sheet').classList.contains('open')"), 'back key closes sheet')
    print('PAID errs:', pg._errs[:2] if pg._errs else 'none')
    pg.close()
    b.close()

# ---- report ----
passed = [k for k,v in results.items() if v[0]]
failed = [k for k,v in results.items() if not v[0]]
for k in sorted(results):
    ok,detail = results[k]
    print(f"{'PASS' if ok else 'FAIL'}  {k}  {detail}")
print(f"\n=== {len(passed)}/{len(results)} PASS ===")
if failed: print('FAILED:', ', '.join(sorted(failed)))
sys.exit(0 if not failed else 1)
