"""PDF・Excel・HTML本文から「品目名 … 金額円」の行を拾って、品目別手数料の候補を作る（表になっていない資料向け）。

使い方: python scripts/extract_generic.py <自治体コード> <URL> [<URL> ...] [--dry]
- PDF は pdfplumber で表を優先して読み、表がなければ行ごとのテキストを読む。
- Excel（xls/xlsx）は全シートの行を読む。
- HTML は表（table）と本文の行を読む。
取り込んだ結果は必ず人の目で確認すること（--dry で保存せずに件数とサンプルを表示）。
"""
import io
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from extract_fees import UA, clean, parse_fee, save  # noqa: E402

LINE = re.compile(r'^(?P<name>[^円\d]{2,80}?)[\s　:：…・]*(?P<fees>[\d,]{3,6}\s*円.*)$')
SKIP = re.compile(r'手数料は|合計|手数料の|券の|枚|貼|購入|処理券|シール|ページ|問い合わせ|電話|受付|料金表|一覧|改定|以降|現在')


def get(url):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja'})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read(), r.headers.get('content-type', '')
        except Exception:
            if i == 3:
                raise
            time.sleep(3)


def rows_from_pdf(b):
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                for t in tables:
                    for r in t:
                        out.append([clean(c or '') for c in r])
            else:
                for line in (page.extract_text() or '').splitlines():
                    out.append([clean(line)])
    return out


def rows_from_excel(b, url):
    out = []
    if url.lower().endswith('.xls'):
        import xlrd
        wb = xlrd.open_workbook(file_contents=b)
        for sh in wb.sheets():
            for i in range(sh.nrows):
                out.append([clean(str(v)) for v in sh.row_values(i)])
    else:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(b), read_only=True, data_only=True)
        for ws in wb.worksheets:
            for r in ws.iter_rows(values_only=True):
                out.append([clean('' if v is None else str(v)) for v in r])
    return out


def rows_from_html(b):
    from bs4 import BeautifulSoup
    m = re.search(rb'charset=["\']?([\w-]+)', b[:3000])
    soup = BeautifulSoup(b.decode(m.group(1).decode() if m else 'utf-8', 'replace'), 'lxml')
    for t in soup(['script', 'style', 'header', 'footer', 'nav']):
        t.decompose()
    out = []
    for tr in soup.find_all('tr'):
        out.append([clean(c.get_text(' ')) for c in tr.find_all(['th', 'td'])])
        tr.decompose()
    for el in soup.find_all(['li', 'p', 'dd', 'dt', 'div']):
        if el.find(['li', 'p', 'div', 'table']):
            continue
        text = clean(el.get_text(' '))
        # 入れ子の箇条書き（親の品目名の下に条件別の料金）は親の品目名を前に付ける
        par = el.find_parent('li') if el.name == 'li' else None
        if par is not None:
            own = clean(''.join(t for t in par.find_all(string=True, recursive=False)))
            if own and not re.search(r'円', own):
                text = own + '（' + text.split('円')[0].rsplit(' ', 1)[0].strip() + '）' + text[len(text.split('円')[0].rsplit(' ', 1)[0]):] if False else own + ' ' + text
        out.append([text])
    return out


NUM = re.compile(r'^[\d,]+(\.0)?$')


def items_from_header_tables(rows):
    """「品目」「金額／手数料」の見出しがある表（金額に円が付かない表）を読む"""
    items, ci, cf, cn, last_name = [], None, None, None, ''
    for k, r in enumerate(rows):
        cells = [c.replace(' ', '') for c in r]
        joined = ''.join(cells)
        prev = [c.replace(' ', '') for c in rows[k - 1]] if k else []
        nxt = [c.replace(' ', '') for c in rows[k + 1]] if k + 1 < len(rows) else []
        fee_here = re.search(r'金額|手数料|料金', joined)
        fee_prev = (not fee_here) and any(re.search(r'金額|手数料|料金', c) for c in prev)
        if re.search(r'品目|品名', joined) and (fee_here or fee_prev):
            ci = next((i for i, c in enumerate(cells) if re.search(r'品目|品名', c)), None)
            src = cells if fee_here else prev
            cf = next((i for i, c in enumerate(src) if re.search(r'金額|手数料|料金', c)), None)
            # 見出しの次の行に「〜以降」の列があれば、新しい料金の列を使う
            later = next((i for i, c in enumerate(nxt) if '以降' in c), None)
            if later is not None:
                cf = later
            cn = next((i for i, c in enumerate(cells) if re.search(r'備考|例示|注意', c)), None)
            # 見出しの「品目」列の下が頭文字（あ・か…）や空欄ばかりなら、品目名は右隣の列にある
            if ci is not None and cf is not None and ci + 1 < cf:
                sample = [x for x in rows[k + 1:k + 25] if len(x) > ci + 1]
                kana = sum(1 for x in sample if not x[ci] or re.fullmatch(r'[ぁ-んァ-ン]', x[ci]))
                if sample and kana / len(sample) > 0.6 and sum(1 for x in sample if x[ci + 1]) / len(sample) > 0.6:
                    ci += 1
            continue
        if ci is None or cf is None or cf >= len(r):
            continue
        nm0 = r[ci] if ci < len(r) else ''
        if nm0 and not re.fullmatch(r'[ぁ-んァ-ン]', nm0):
            last_name = re.sub(r'^※', '', nm0).strip()
        m = re.match(r'^\s*([\d,]+(?:\.0)?)\s*円?(\s|$)', r[cf].replace('，', ','))
        if not m:
            continue
        fee = int(float(m.group(1).replace(',', '')))
        if not 100 <= fee <= 20000:
            continue
        name = r[ci] if ci < len(r) else ''
        rest = [c for c in r[ci + 1:cf] if c and not re.fullmatch(r'[\d,]+|[●■○〇×◯△\-－\s]+', c)]
        if not name and rest and not any(c for c in r[:ci] if c and not re.fullmatch(r'[ぁ-んァ-ン]', c)):
            if items and items[-1]['name'] == last_name:
                items[-1]['options'].append({'cond': ' '.join(rest), 'fee': fee})
            elif last_name:
                items.append({'name': last_name, 'options': [{'cond': ' '.join(rest), 'fee': fee}], 'note': ''})
            continue
        if not name or re.fullmatch(r'[ぁ-んァ-ン]', name):
            name = next((c for c in r[:cf] if c and not re.fullmatch(r'[ぁ-んァ-ン]|[\d,.]+', c)), '')
        cond = ' '.join(c for c in r[ci + 1:cf] if c and c != name and not re.search(r'[ァ-ン]{4,}$', c)
                        and not re.fullmatch(r'[\d,]+|[●■○〇×◯△\-－\s]+', c) and not re.fullmatch(r'[ァ-ンー・（）()\s]+', c))
        name = re.sub(r'^※', '', name).strip()
        if not name or (cond and name == cond):
            if items and cond:
                items[-1]['options'].append({'cond': cond, 'fee': fee})
            continue
        if cond:
            items.append({'name': name, 'options': [{'cond': cond, 'fee': fee}], 'note': ''})
            continue
        note = r[cn] if cn is not None and cn < len(r) else ''
        items.append({'name': name, 'options': [{'cond': '', 'fee': fee}], 'note': note[:80]})
    return items


def items_from_rows(rows):
    tbl = items_from_header_tables(rows)
    if len(tbl) >= 20:
        return tbl
    items, seen = [], set()
    for r in rows:
        cells = [c for c in r if c]
        if not cells:
            continue
        name, fee_txt, note = None, None, ''
        fee_cells = [i for i, c in enumerate(cells) if re.search(r'[\d,]{3,6}\s*円', c)]
        if len(cells) >= 2 and fee_cells:
            fi = fee_cells[0]
            name = next((c for c in cells[:fi] if not re.fullmatch(r'[ぁ-んァ-ン]|[\d,]+', c)), None)
            fee_txt = ' '.join(cells[fi:fi + 1])
            note = ' '.join(c for c in cells[fi + 1:] if not re.search(r'円', c))[:80]
        else:
            m = LINE.match(' '.join(cells))
            if m:
                name, fee_txt = m.group('name'), m.group('fees')
        if not name or not fee_txt or SKIP.search(name) or len(name) < 2:
            continue
        opts = [o for o in parse_fee(fee_txt) if 100 <= o['fee'] <= 20000]
        if not opts:
            continue
        name = name.strip(' ・…:：')
        key = (name, tuple((o['cond'], o['fee']) for o in opts))
        if key in seen:
            continue
        seen.add(key)
        if items and items[-1]['name'] == name:
            items[-1]['options'] += opts
        else:
            items.append({'name': name, 'options': opts, 'note': note})
    return items


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    code, urls = args[0], args[1:]
    rows = []
    for u in urls:
        b, ct = get(u)
        low = u.lower().split('?')[0]
        if low.endswith('.pdf') or 'pdf' in ct:
            rows += rows_from_pdf(b)
        elif low.endswith(('.xls', '.xlsx')):
            rows += rows_from_excel(b, low)
        else:
            rows += rows_from_html(b)
        time.sleep(1)
    items = items_from_rows(rows)
    fees = sorted({o['fee'] for i in items for o in i['options']})
    print(f'{code}: {len(items)}品目 料金 {fees[:10]}')
    for i in items[:6] + items[len(items) // 2:len(items) // 2 + 3]:
        print('   ', i['name'][:30], [(o['cond'][:15], o['fee']) for o in i['options']])
    if '--dry' not in sys.argv:
        save(code, items, ' '.join(urls))


if __name__ == '__main__':
    main()
