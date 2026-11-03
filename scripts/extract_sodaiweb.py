"""sodai-web.jp 系の受付サイト（排出品目一覧）から品目別手数料を取り込む。

使い方: python scripts/extract_sodaiweb.py <自治体コード> <itemSelect.na のURL>
種別（電気・家具・趣味…）を1つずつ選んで検索し、結果の表（品目名・単価・A券・B券）を読む。
Playwright が必要。1種別ごとに数秒あけて、受付サイトに負荷をかけない。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from extract_fees import UA, clean, save  # noqa: E402


def fetch(url):
    from playwright.sync_api import sync_playwright
    items, seen = [], set()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(locale='ja-JP', user_agent=UA)
        pg.goto(url, wait_until='networkidle', timeout=60000)
        values = pg.eval_on_selector_all('select[name=itemType] option', 'os => os.map(o => [o.value, o.innerText.trim()])')
        for v, label in values:
            if v == 'UN_SELECT':
                continue
            pg.goto(url, wait_until='networkidle', timeout=60000)
            pg.select_option('select[name=itemType]', v)
            pg.click('input[name=search_btn]')
            pg.wait_for_load_state('networkidle')
            pg.wait_for_timeout(1500)
            rows = pg.eval_on_selector_all('table tr', 'rs => rs.map(r => [...r.querySelectorAll("th,td")].map(c => c.innerText.trim()))')
            n = 0
            for r in rows:
                if len(r) < 2 or not r[1].replace(',', '').isdigit():
                    continue
                name_full = clean(r[0])
                name, _, note = name_full.partition('※')
                name = name.strip()
                key = (name, r[1])
                if key in seen:
                    continue
                seen.add(key)
                items.append({'name': name, 'options': [{'cond': '', 'fee': int(r[1].replace(',', ''))}],
                              'note': ('※' + note.strip()) if note else '', 'group': label})
                n += 1
            print(f'  {label}: {n}件')
            time.sleep(3)
        b.close()
    items.sort(key=lambda i: i['name'])
    return items


if __name__ == '__main__':
    code, url = sys.argv[1], sys.argv[2]
    save(code, fetch(url), url)
