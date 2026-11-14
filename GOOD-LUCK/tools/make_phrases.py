# Renders each "Good luck" phrase once as a white, transparent PNG.
# A browser is used because it shapes every script correctly (Arabic, Devanagari, Thai, ...).
#   pip install playwright && playwright install chromium
#   python tools/make_phrases.py
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent.parent
OUT = HERE / "sprites"

PHRASES = [
    ("English", "Good luck"), ("Korean", "행운을 빌어"), ("Japanese", "幸運を祈る"), ("Chinese", "祝你好运"),
    ("Hindi", "शुभकामनाएँ"), ("Portuguese", "Boa sorte"), ("Spanish", "Buena suerte"), ("French", "Bonne chance"),
    ("German", "Viel Glück"), ("Italian", "Buona fortuna"), ("Russian", "Удачи"), ("Arabic", "حظاً سعيداً"),
    ("Thai", "โชคดี"), ("Vietnamese", "Chúc may mắn"), ("Turkish", "İyi şanslar"), ("Greek", "Καλή τύχη"),
    ("Hebrew", "בהצלחה"), ("Dutch", "Veel geluk"), ("Swedish", "Lycka till"), ("Norwegian", "Lykke til"),
    ("Danish", "Held og lykke"), ("Finnish", "Onnea"), ("Polish", "Powodzenia"), ("Czech", "Hodně štěstí"),
    ("Slovak", "Veľa šťastia"), ("Hungarian", "Sok szerencsét"), ("Romanian", "Mult noroc"), ("Indonesian", "Semoga beruntung"),
    ("Malay", "Semoga berjaya"), ("Swahili", "Bahati njema"), ("Persian", "موفق باشی"), ("Bengali", "শুভকামনা"),
    ("Tamil", "நல்வாழ்த்துகள்"), ("Ukrainian", "Удачі"), ("Irish", "Ádh mór"), ("Icelandic", "Gangi þér vel"),
    ("Esperanto", "Bonŝancon"), ("Latin", "Feliciter"), ("Armenian", "Հաջողություն"), ("Georgian", "წარმატებები"),
    ("Catalan", "Bona sort"), ("Basque", "Zorte on"), ("Welsh", "Pob lwc"), ("Croatian", "Sretno"),
    ("Serbian", "Срећно"), ("Bulgarian", "Успех"), ("Lithuanian", "Sėkmės"), ("Latvian", "Veiksmi"),
    ("Estonian", "Edu"), ("Albanian", "Paç fat"), ("Slovenian", "Srečno"), ("Macedonian", "Среќно"),
    ("Belarusian", "Поспехаў"), ("Kazakh", "Сәттілік"), ("Kyrgyz", "Ийгилик"), ("Uzbek", "Omad"),
    ("Azerbaijani", "Uğurlar"), ("Mongolian", "Амжилт"), ("Nepali", "शुभकामना"), ("Marathi", "शुभेच्छा"),
    ("Gujarati", "શુભેચ્છા"), ("Punjabi", "ਸ਼ੁਭ ਕਾਮਨਾਵਾਂ"), ("Telugu", "శుభాకాంక్షలు"), ("Kannada", "ಶುಭವಾಗಲಿ"),
    ("Malayalam", "ആശംസകൾ"), ("Sinhala", "සුබ පැතුම්"), ("Khmer", "សំណាងល្អ"), ("Lao", "ໂຊກດີ"),
    ("Burmese", "ကံကောင်းပါစေ"), ("Amharic", "መልካም ዕድል"), ("Somali", "Nasiib wanaagsan"), ("Zulu", "Inhlanhla enhle"),
    ("Afrikaans", "Sterkte"), ("Maori", "Kia waimarie"), ("Luxembourgish", "Vill Gléck"), ("Cantonese", "祝你好運"),
    ("Galician", "Moita sorte"),
]

FONTS = ("'Segoe UI', 'Malgun Gothic', 'Yu Gothic', 'Microsoft YaHei', 'Microsoft JhengHei', 'Nirmala UI', "
         "'Leelawadee UI', 'Myanmar Text', 'Ebrima', 'Microsoft Himalaya', 'Gadugi', 'Segoe UI Symbol', sans-serif")


def main():
    OUT.mkdir(exist_ok=True)
    spans = "".join(f'<div><span id="p{i}">{text}</span></div>' for i, (_, text) in enumerate(PHRASES))
    html = (f"<html><body style='margin:0;background:transparent'>"
            f"<style>span{{font-family:{FONTS};font-size:72px;color:#fff;line-height:1.35;"
            f"padding:6px 10px;display:inline-block;white-space:nowrap}}</style>{spans}</body></html>")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        page = b.new_page(device_scale_factor=1)
        page.set_content(html)
        page.wait_for_timeout(500)
        for i, (lang, _) in enumerate(PHRASES):
            page.locator(f"#p{i}").screenshot(path=str(OUT / f"{i:02d}.png"), omit_background=True)
        b.close()
    (OUT / "phrases.json").write_text(json.dumps(PHRASES, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(PHRASES), "sprites")


if __name__ == "__main__":
    main()
