"""data/ から静的サイトを dist/ に生成する。

使い方: python scripts/build_site.py
Cloudflare のビルドコマンドとしても使う。
料金データ（data/fees/<自治体コード>.json）がある自治体だけページを作る。
"""
import csv
import glob
import json
import os
import shutil
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, os.path.dirname(__file__))
from common import PC_LAW, PREF_ORDER, PREF_SLUG, QUICK, RECYCLE_LAW, city_slug, yen  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'dist')
CFG = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))


def load():
    master = {m['code']: m for m in csv.DictReader(open(os.path.join(ROOT, 'data', 'municipalities.csv'), encoding='utf-8'))}
    cities = []
    for path in sorted(glob.glob(os.path.join(ROOT, 'data', 'fees', '*.json'))):
        d = json.load(open(path, encoding='utf-8'))
        m = master.get(d['code'])
        if not m or not d.get('items'):
            continue
        d.update(name=m['name'], pref=m['pref'], pref_slug=PREF_SLUG[m['pref']], slug=city_slug(m['slug'], m['name']))
        d['url'] = f"/{d['pref_slug']}/{d['slug']}/"
        fees = [o['fee'] for i in d['items'] for o in i['options']]
        d['fee_min'], d['fee_max'] = min(fees), max(fees)
        d['fee_levels'] = sorted(set(fees))
        d['ym'] = d['checked_at'][:7].replace('-', '年') + '月'
        cities.append(d)
    return cities


def write(path, text):
    full = os.path.join(DIST, path.lstrip('/'))
    if full.endswith('/'):
        full += 'index.html'
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(text)


def main():
    cities = load()
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    shutil.copytree(os.path.join(ROOT, 'static'), os.path.join(DIST, 'assets'))

    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, 'templates')), autoescape=select_autoescape())
    latest = max(c['checked_at'] for c in cities)
    common = dict(cfg=CFG, yen=yen, quick=QUICK, recycle_law=RECYCLE_LAW, pc_law=PC_LAW, latest=latest,
                  ym=latest[:7].replace('-', '年') + '月', pref_name=dict(PREF_ORDER))

    def render(tpl, path, **kw):
        write(path, env.get_template(tpl).render(path=path, **common, **kw))

    urls = ['/']
    by_pref = {}
    for c in cities:
        by_pref.setdefault(c['pref_slug'], []).append(c)
    pref_list = [(slug, name, by_pref[slug]) for slug, name in PREF_ORDER if slug in by_pref]
    render('index.html', '/', cities=cities, pref_list=pref_list)

    for c in cities:
        others = [o for o in cities if o is not c and o['pref'] == c['pref']][:12] or [o for o in cities if o is not c][:12]
        render('city.html', c['url'], c=c, others=others)
        urls.append(c['url'])

    render('about.html', '/about/')
    urls.append('/about/')
    if CFG.get('contact_form'):
        render('contact.html', '/contact/')
        urls.append('/contact/')
    render('404.html', '/404.html')

    idx = [{'n': c['name'], 'p': c['pref'], 'u': c['url']} for c in cities]
    write('/assets/cities.json', json.dumps(idx, ensure_ascii=False, separators=(',', ':')))

    base = CFG['base_url'].rstrip('/')
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f'<url><loc>{base}{u}</loc><lastmod>{latest}</lastmod></url>' for u in urls]
    sm.append('</urlset>')
    write('/sitemap.xml', '\n'.join(sm))
    write('/robots.txt', f'User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n')
    print(f'生成: {len(urls)}ページ（自治体 {len(cities)}）→ dist/')


if __name__ == '__main__':
    main()
