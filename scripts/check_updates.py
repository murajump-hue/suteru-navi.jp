"""各自治体の料金ページが更新されていないかを確認する（月1回、GitHub Actions から実行）。

使い方: python scripts/check_updates.py [--save]
- data/fees/*.json の fee_page と official の本文（タグを除いた文字列）のハッシュを data/page_hashes.json と比べる。
- 変わったページがあれば一覧を出して終了コード1で止まる（GitHub から通知メールが届く）。
- 内容を確認して料金データを直したら --save を付けて実行し、ハッシュを更新する。
受付システムのように JavaScript で描画するページは本文が取れないため、比較の対象外になる。
"""
import glob
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = 'Mozilla/5.0 (compatible; suteru-navi-research/0.1)'
HASHES = os.path.join(ROOT, 'data', 'page_hashes.json')


def body_hash(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja'})
    b = urllib.request.urlopen(req, timeout=30).read()
    m = re.search(rb'charset=["\']?([\w-]+)', b[:3000])
    s = b.decode(m.group(1).decode() if m else 'utf-8', errors='replace')
    s = re.sub(r'<(script|style|header|footer|nav)[^>]*>.*?</\1>', ' ', s, flags=re.S | re.I)
    t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s)))
    # 料金・品目に関係する部分（円の前後）だけを比べ、日付やアクセス数などの細かな変化を拾わない
    parts = re.findall(r'.{0,40}\d[\d,]*\s*円', t)
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest(), len(parts)


def main():
    save = '--save' in sys.argv
    old = json.load(open(HASHES, encoding='utf-8')) if os.path.exists(HASHES) else {}
    new, changed, errors = {}, [], []
    for path in sorted(glob.glob(os.path.join(ROOT, 'data', 'fees', '*.json'))):
        d = json.load(open(path, encoding='utf-8'))
        for url in sorted({d.get('fee_page'), d.get('official')} - {None}):
            try:
                h, n = body_hash(url)
            except Exception as e:
                errors.append(f"{d['code']} {url} {type(e).__name__}")
                continue
            if n == 0:
                continue  # 本文に料金がない（JavaScript描画など）
            new[url] = h
            if url in old and old[url] != h:
                changed.append(f"{d['code']} {url}")
            time.sleep(1)
    for e in errors:
        print('取得できず:', e)
    if save or not old:
        json.dump(new, open(HASHES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'ハッシュを保存しました（{len(new)}ページ）')
    if changed and not save:
        print('料金ページが更新されています。内容を確認して data/fees を直してください:')
        for c in changed:
            print('  ', c)
        sys.exit(1)
    print('変更なし' if not changed else '保存済み')


if __name__ == '__main__':
    main()
