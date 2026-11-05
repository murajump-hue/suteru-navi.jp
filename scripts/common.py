"""捨てるナビ: 生成で共通に使う定義"""
import re

PREF_ORDER = [
    ('hokkaido', '北海道'), ('aomori', '青森県'), ('iwate', '岩手県'), ('miyagi', '宮城県'), ('akita', '秋田県'),
    ('yamagata', '山形県'), ('fukushima', '福島県'), ('ibaraki', '茨城県'), ('tochigi', '栃木県'), ('gunma', '群馬県'),
    ('saitama', '埼玉県'), ('chiba', '千葉県'), ('tokyo', '東京都'), ('kanagawa', '神奈川県'), ('niigata', '新潟県'),
    ('toyama', '富山県'), ('ishikawa', '石川県'), ('fukui', '福井県'), ('yamanashi', '山梨県'), ('nagano', '長野県'),
    ('gifu', '岐阜県'), ('shizuoka', '静岡県'), ('aichi', '愛知県'), ('mie', '三重県'), ('shiga', '滋賀県'),
    ('kyoto', '京都府'), ('osaka', '大阪府'), ('hyogo', '兵庫県'), ('nara', '奈良県'), ('wakayama', '和歌山県'),
    ('tottori', '鳥取県'), ('shimane', '島根県'), ('okayama', '岡山県'), ('hiroshima', '広島県'), ('yamaguchi', '山口県'),
    ('tokushima', '徳島県'), ('kagawa', '香川県'), ('ehime', '愛媛県'), ('kochi', '高知県'), ('fukuoka', '福岡県'),
    ('saga', '佐賀県'), ('nagasaki', '長崎県'), ('kumamoto', '熊本県'), ('oita', '大分県'), ('miyazaki', '宮崎県'),
    ('kagoshima', '鹿児島県'), ('okinawa', '沖縄県'),
]
PREF_SLUG = {name: slug for slug, name in PREF_ORDER}

# まとめて計算ツールの「よく捨てるもの」ボタン（ラベル, 検索語）
QUICK = [('ソファ', 'ソファ'), ('ベッド', 'ベッド'), ('マットレス', 'マットレス'), ('布団', '布団|ふとん'),
         ('タンス', 'タンス|たんす|箪笥'), ('本棚', '本棚|書棚'), ('食器棚', '食器棚'), ('机', '机'),
         ('椅子', '椅子|いす|イス'), ('テーブル', 'テーブル'), ('こたつ', 'こたつ'), ('カーペット', 'カーペット|じゅうたん'),
         ('自転車', '自転車'), ('電子レンジ', '電子レンジ'), ('扇風機', '扇風機'), ('ストーブ', 'ストーブ'),
         ('カラーボックス', 'カラーボックス'), ('衣装ケース', '衣装'), ('ベビーカー', 'ベビーカー|乳母車'), ('物干し', '物干')]

# 自治体の粗大ごみでは出せない代表的なもの（全国共通の制度）
RECYCLE_LAW = 'テレビ|エアコン|冷蔵庫|冷凍庫|洗濯機|衣類乾燥機'
PC_LAW = 'パソコン|ノートPC|デスクトップPC'

SUFFIX = [('shi', '市'), ('ku', '区'), ('machi', '町'), ('cho', '町'), ('mura', '村'), ('son', '村')]


def city_slug(romaji, name):
    """'setagayaku' → 'setagaya'。末尾の市区町村の読みを外す"""
    for s, kanji in SUFFIX:
        if name.endswith(kanji) and romaji.endswith(s) and len(romaji) > len(s) + 1:
            romaji = romaji[:-len(s)]
            break
    # 長音は一般的なローマ字表記に寄せる（bunkyou → bunkyo、oota → ota、chuuou → chuo）
    return romaji.replace('uu', 'u').replace('ou', 'o').replace('oo', 'o')


def yen(n):
    if n is None:
        return '−'
    return '無料' if n == 0 else f'{n:,}円'
