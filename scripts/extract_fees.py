"""自治体の公式ページから粗大ごみの品目別手数料を取り出し、data/fees/<code>.json の items を作る。

使い方:
  python scripts/extract_fees.py html <code> <url> [--table-filter 文字列]
  python scripts/extract_fees.py eco  <code> <受付システムの品目一覧URL>

html: 公式ページの表（品目・備考・手数料の列）を読む。rowspan で省略された品目名は上の行から補う。
eco : sodai-xxx.jp/eco 系の受付システムの品目一覧をブラウザで描画して読む（Playwright が必要）。
既存の JSON があれば items と source だけを書き換え、手で入れた申込方法などの項目は残す。
"""
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = 'Mozilla/5.0 (compatible; suteru-navi-research/0.1)'
YEN = re.compile(r'([\d,]+)\s*円')


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja'})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
    m = re.search(rb'charset=["\']?([\w-]+)', b[:3000])
    return b.decode(m.group(1).decode() if m else 'utf-8', errors='replace')


def clean(t):
    import jaconv
    t = jaconv.h2z(t or '', kana=True, ascii=False, digit=False)
    t = re.sub(r'[▼▲]説明を?(表示|閉じる)', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def parse_fee(text):
    """「15kg未満390円 25kg未満780円」→ [{'cond': '15kg未満', 'fee': 390}, ...]。円がなければ []"""
    text = clean(text)
    out, pos = [], 0
    for m in YEN.finditer(text):
        cond = clean(text[pos:m.start()]).strip('、,・/／()（）')
        out.append({'cond': cond, 'fee': int(m.group(1).replace(',', ''))})
        pos = m.end()
    return out


def grid(table):
    """rowspan/colspan を展開した2次元のセル文字列"""
    rows, carry = [], {}
    for tr in table.find_all('tr'):
        row, col = [], 0
        cells = tr.find_all(['th', 'td'])
        ci = 0
        while ci < len(cells) or col in carry:
            if col in carry:
                txt, left = carry[col]
                row.append(txt)
                if left > 1: carry[col] = (txt, left - 1)
                else: del carry[col]
                col += 1
                continue
            c = cells[ci]; ci += 1
            txt = clean(c.get_text(' '))
            rs, cs = int(c.get('rowspan', 1) or 1), int(c.get('colspan', 1) or 1)
            for k in range(cs):
                row.append(txt)
                if rs > 1: carry[col] = (txt, rs - 1)
                col += 1
        rows.append(row)
    return rows


def from_html(url, table_filter=None):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(fetch(url), 'lxml')
    items = []
    for t in soup.find_all('table'):
        cap = t.find('caption')
        cap = clean(cap.get_text()) if cap else ''
        if table_filter and table_filter not in cap:
            continue
        g = grid(t)
        if not g: continue
        head = g[0]
        def col(*names):
            for i, h in enumerate(head):
                if any(n in h for n in names): return i
            return None
        ci, cf, cn = col('品目', '品名'), col('手数料', '料金'), col('備考', '注意')
        if ci is None or cf is None: continue
        last = None
        for r in g[1:]:
            if len(r) <= max(ci, cf): continue
            name, fee_txt = r[ci], r[cf]
            note = r[cn] if cn is not None and cn < len(r) else ''
            opts = parse_fee(fee_txt)
            if not opts or not name or name == head[ci]: continue
            if note and note != name and len(opts) == 1 and not opts[0]['cond']:
                opts[0]['cond'] = note; note = ''
            key = (name, tuple((o['cond'], o['fee']) for o in opts))
            if key == last: continue
            last = key
            # 同じ品目の条件違いはまとめる
            if items and items[-1]['name'] == name:
                items[-1]['options'] += opts
            else:
                items.append({'name': name, 'options': opts, 'note': note, 'group': cap})
    return items


def from_eco(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(locale='ja-JP', extra_http_headers={'Accept-Language': 'ja'}, user_agent=UA)
        pg.goto(url, wait_until='networkidle', timeout=90000)
        pg.wait_for_timeout(6000)
        if pg.eval_on_selector_all('#dust_dustList li', 'ls => ls.length') <= 1:
            # 自動で全品目を表示しない設定の受付サイトは「全ての品目」を押す
            for sel in ['a.classAll', '#dust_classList a', 'text=全ての品目', 'text=すべての品目']:
                if pg.query_selector(sel):
                    pg.click(sel)
                    pg.wait_for_timeout(6000)
                    break
        rows = pg.eval_on_selector_all('#dust_dustList li', '''ls => ls.map(l => {
            const g = s => { const e = l.querySelector(s); return e ? e.innerText.trim() : ''; };
            return {text: l.innerText.replace(/\\s+/g, ' ').trim()};
        })''')
        b.close()
    items = []
    for r in rows:
        t = r['text'].replace('▼説明を表示', '').replace('▲説明を閉じる', '').strip()
        m = YEN.search(t)
        if not m: continue
        name = re.sub(r'\s*(収集|持込)?手数料[:：]?\s*$', '', clean(t[:m.start()]))
        rest = clean(t[m.end():])
        items.append({'name': name, 'options': [{'cond': '', 'fee': int(m.group(1).replace(',', ''))}], 'note': rest})
    return items


def save(code, items, url):
    path = os.path.join(ROOT, 'data', 'fees', f'{code}.json')
    d = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'code': code}
    d['items'] = items
    d['source_items'] = url
    d['items_fetched_at'] = time.strftime('%Y-%m-%d')
    json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    fees = sorted({o['fee'] for i in items for o in i['options']})
    print(f'{code}: {len(items)}品目 料金の種類 {fees[:12]}')


if __name__ == '__main__':
    kind, code, url = sys.argv[1:4]
    flt = sys.argv[sys.argv.index('--table-filter') + 1] if '--table-filter' in sys.argv else None
    items = from_html(url, flt) if kind == 'html' else from_eco(url)
    save(code, items, url)


def from_eco_json(base=None, path=None, free=False):
    """sodai-xxx.jp/eco 系の受付サイトの品目一覧（JSON）を読む。
    base: 'https://www.sodai-setagaya.jp/eco/view/setagaya' のような品目一覧ページのフォルダ。
    path: 日本以外から接続できない自治体用に、別の環境で保存したJSONファイル。
    戻り値: (items, 処理券の金額の一覧)"""
    import http.cookiejar
    if path:
        data = json.load(open(path, encoding='utf-8'))
    else:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [('User-Agent', UA), ('Accept-Language', 'ja')]
        page = op.open(base + '/dustlistSearch.html', timeout=40).read().decode('utf-8', 'replace')
        m = re.search(r'id="carryFlag"[^>]*>([^<]*)<', page)
        carry = (m.group(1).strip() if m else 'false') or 'false'
        time.sleep(2)
        q = f'{base}/teeda.ajax?time=1&component=dustPage&action=ajaxGetDustList&AjaxParam0=0&AjaxParam1=&AjaxParam2={carry}'
        req = urllib.request.Request(q, headers={'Referer': base + '/dustlistSearch.html'})
        data = json.loads(op.open(req, timeout=60).read().decode('utf-8'))
    items, tickets = [], set()
    for d in data:
        # free=True: 手数料が無料の自治体（単価0円の品目も取り込む）
        if d.get('uncollct_flg') or d.get('tanka') is None or d['tanka'] < 0 or (not free and not d['tanka']):
            continue
        name = clean(d.get('dustName', ''))
        note = clean(re.sub(r'<[^>]+>', ' ', d.get('html_memo') or ''))[:120]
        items.append({'name': name, 'options': [{'cond': '', 'fee': int(d['tanka'])}], 'note': note,
                      'group': clean(d.get('className', ''))})
        for k, n in zip(d.get('ticketKind') or [], d.get('ticketNumber') or []):
            tickets.add(int(k))
    items.sort(key=lambda i: i['name'])
    return items, sorted(tickets)
