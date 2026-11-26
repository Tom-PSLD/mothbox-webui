import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).resolve().parent
LANGUE = sys.argv[1] if len(sys.argv) > 1 else "fr"
SUFFIXE = "" if LANGUE == "fr" else f"_{LANGUE}"
OUT = ICI / f"annotees_notice{SUFFIXE}"
OUT.mkdir(exist_ok=True)
CAPTURES = ICI / f"captures{SUFFIXE}"
NOIR = (25, 25, 25)
BLANC = (255, 255, 255)
FOND = (255, 255, 255)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def police(t):
    return ImageFont.truetype(FONT, t)


def repere(d, cible, pos, n, r=24, w=3):
    d.line([pos, cible], fill=BLANC, width=w + 4)
    d.line([pos, cible], fill=NOIR, width=w)
    cx, cy = cible
    d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=NOIR, outline=BLANC, width=2)
    x, y = pos
    d.ellipse([x - r, y - r, x + r, y + r], fill=BLANC, outline=NOIR, width=w)
    d.text((x, y + 1), str(n), font=police(int(r * 1.15)), fill=NOIR, anchor="mm")


def zone(d, box, w=3):
    d.rectangle(box, outline=BLANC, width=w + 4)
    d.rectangle([box[0] + 2, box[1] + 2, box[2] - 2, box[3] - 2], outline=NOIR, width=w)


def sauver(im, nom, maxw=1400):
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(OUT / nom, quality=90)
    print(nom, im.size)


def marge(im, gauche=0, droite=0, haut=0, bas=0):
    c = Image.new("RGB", (im.width + gauche + droite, im.height + haut + bas), FOND)
    c.paste(im, (gauche, haut))
    return c


def carte():
    im = Image.open(ICI / "photos/carte_entiere.png").convert("RGB").crop((880, 120, 1500, 1290))
    im = marge(im, gauche=150, droite=150)
    d = ImageDraw.Draw(im)
    ox, oy = 880 - 150, 120
    p = lambda x, y: (x - ox, y - oy)
    zone(d, (*p(1238, 188), *p(1342, 872)))
    zone(d, (*p(1238, 880), *p(1342, 1068)))
    zone(d, (*p(1062, 968), *p(1162, 1142)))
    repere(d, p(1342, 530), (im.width - 60, p(0, 530)[1]), 1)
    repere(d, p(1342, 960), (im.width - 60, p(0, 960)[1]), 2)
    repere(d, p(1300, 1052), (im.width - 60, p(0, 1120)[1]), 3)
    repere(d, p(1108, 988), (60, p(0, 880)[1]), 4)
    repere(d, p(1062, 1055), (60, p(0, 1055)[1]), 5)
    repere(d, p(1108, 1125), (60, p(0, 1230)[1]), 6)
    sauver(im, "carte.jpg", maxw=1000)


def rangee():
    im = Image.open(ICI / "photos/tout_off.png").convert("RGB").crop((440, 860, 1120, 1300))
    sauver(im, "rangee_mode.jpg", maxw=900)


def ecran(src, dst, reperes, debut=1):
    im = Image.open(CAPTURES / src).convert("RGB")
    bord = Image.new("RGB", (im.width + 8, im.height + 8), (170, 170, 170))
    bord.paste(im, (4, 4))
    im = marge(bord, droite=110)
    d = ImageDraw.Draw(im)
    x = im.width - 50
    for n, (cx, cy) in enumerate(reperes, debut):
        repere(d, (cx + 4, cy + 4), (x, cy + 4), n, r=26)
    sauver(im, dst, maxw=900)


def ecrans():
    ecran("etape1.png", "ecran1.jpg", [(700, 782), (700, 1000), (700, 1288)])
    if LANGUE == "en":
        ecran("etape2.png", "ecran2.jpg", [(730, 672), (730, 1086), (730, 1374), (730, 1506), (730, 1714)])
        ecran("etape3.png", "ecran3.jpg", [(720, 606), (720, 1078), (720, 1420)])
    else:
        ecran("etape2.png", "ecran2.jpg", [(730, 710), (730, 1090), (730, 1422), (730, 1552), (730, 1760)])
        ecran("etape3.png", "ecran3.jpg", [(720, 650), (720, 1124), (720, 1420)])
    ecran("etape4.png", "ecran4.jpg", [(720, 1080)])
    ecran("etape4_pret.png", "ecran4_pret.jpg", [(720, 1020)], debut=2)
    ecran("etape2_u1.png", "ecran2_u1.jpg", [(720, 700)])


if __name__ == "__main__":
    if LANGUE == "fr":
        carte()
        rangee()
    ecrans()
