import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).resolve().parent
OUT = ICI / "annotees"
OUT.mkdir(exist_ok=True)
ROUGE = (228, 60, 30)
VERT = (46, 125, 79)
BLANC = (255, 255, 255)
ORANGE = (232, 120, 26)
GRIS = (110, 116, 120)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def police(t):
    return ImageFont.truetype(FONT, t)


def fleche(d, a, b, w=10, coul=ROUGE):
    ax, ay = a
    bx, by = b
    ang = math.atan2(by - ay, bx - ax)
    L = w * 3.2
    base = (bx - L * math.cos(ang), by - L * math.sin(ang))
    pts = [
        (bx, by),
        (base[0] + L * 0.6 * math.sin(ang), base[1] - L * 0.6 * math.cos(ang)),
        (base[0] - L * 0.6 * math.sin(ang), base[1] + L * 0.6 * math.cos(ang)),
    ]
    d.line([a, base], fill=BLANC, width=w + 6)
    d.line([a, base], fill=coul, width=w)
    d.polygon(pts, fill=coul, outline=BLANC, width=3)


def etiquette(d, xy, texte, taille, coul=ROUGE, ancre="lm"):
    f = police(taille)
    bb = d.textbbox(xy, texte, font=f, anchor=ancre)
    d.rounded_rectangle([bb[0] - 12, bb[1] - 9, bb[2] + 12, bb[3] + 9], 10, fill=BLANC, outline=coul, width=4)
    d.text(xy, texte, font=f, fill=coul, anchor=ancre)
    return bb


def cadre(d, box, w=7, coul=ROUGE):
    d.rounded_rectangle(box, 12, outline=BLANC, width=w + 6)
    d.rounded_rectangle(box, 12, outline=coul, width=w)


def anneau(d, c, r, w=7, coul=ROUGE):
    x, y = c
    d.ellipse([x - r, y - r, x + r, y + r], outline=BLANC, width=w + 6)
    d.ellipse([x - r, y - r, x + r, y + r], outline=coul, width=w)


def pastille(d, c, n, r=34, coul=ROUGE):
    x, y = c
    d.ellipse([x - r, y - r, x + r, y + r], fill=coul, outline=BLANC, width=4)
    d.text((x, y), str(n), font=police(int(r * 1.2)), fill=BLANC, anchor="mm")


def sauver(im, nom, crop=None, maxw=1400):
    if crop:
        im = im.crop(crop)
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(OUT / nom, quality=90)
    print(nom, im.size)


def carte_reperes():
    im = Image.open(ICI / "photos/carte_entiere.png").convert("RGB")
    d = ImageDraw.Draw(im)
    cadre(d, (1235, 185, 1345, 875))
    cadre(d, (1235, 878, 1345, 1072), coul=VERT)
    cadre(d, (1060, 965, 1165, 1145))
    pastille(d, (1395, 530), 1)
    pastille(d, (1395, 975), 2, coul=VERT)
    pastille(d, (1000, 1055), 3)
    etiquette(d, (1290, 1180), "Active", 34, coul=VERT, ancre="mm")
    fleche(d, (1290, 1150), (1290, 1068), coul=VERT)
    etiquette(d, (1000, 1220), "DEBUG", 34, ancre="mm")
    fleche(d, (1050, 1195), (1110, 1135))
    etiquette(d, (960, 930), "U1", 34, ancre="mm")
    fleche(d, (990, 945), (1062, 985))
    sauver(im, "carte_reperes.jpg", crop=(880, 120, 1500, 1290), maxw=1000)


LEVIERS = {
    "tout_off.png": {"debug": (983, 1113), "active": (718, 592)},
    "debug_sans_active.png": {"debug": (1300, 1280), "active": (1021, 762)},
    "active_debug.png": {"debug": (1265, 1051), "active": (1045, 644)},
    "active_seul.png": {"debug": (1145, 1015), "active": (931, 608)},
}


def position(src, dst, etat_active, etat_debug, crop):
    im = Image.open(ICI / "photos" / src).convert("RGB")
    d = ImageDraw.Draw(im)
    lv = LEVIERS[src]
    for cle, etat, nom in (("active", etat_active, "Active"), ("debug", etat_debug, "DEBUG")):
        coul = VERT if etat else ROUGE
        x, y = lv[cle]
        anneau(d, (x, y), 46, coul=coul)
        etiquette(d, (x, y + 120), f"{nom} : {'ON' if etat else 'OFF'}", 40, coul=coul, ancre="mm")
        fleche(d, (x, y + 88), (x, y + 52), w=8, coul=coul)
    sauver(im, dst, crop=crop, maxw=900)


def ecran(src, dst, ops):
    im = Image.open(ICI / "captures" / src).convert("RGB")
    d = ImageDraw.Draw(im)
    for op in ops:
        if op[0] == "p":
            pastille(d, op[1], op[2], r=30)
        elif op[0] == "c":
            cadre(d, op[1], w=5)
        elif op[0] == "f":
            fleche(d, op[1], op[2], w=8)
    sauver(im, dst, maxw=780)


def ecrans():
    ecran("etape1.png", "ecran_etape1.jpg", [
        ("c", (34, 892, 746, 1220)), ("p", (740, 900), 1),
        ("c", (60, 1240, 720, 1340)), ("p", (740, 1250), 2)])
    ecran("etape2.png", "ecran_etape2.jpg", [
        ("c", (34, 580, 746, 780)), ("p", (740, 590), 1),
        ("c", (34, 810, 746, 1340)), ("p", (740, 820), 2),
        ("c", (32, 1502, 748, 1602)), ("p", (740, 1510), 3)])
    ecran("etape3.png", "ecran_etape3.jpg", [
        ("c", (34, 580, 746, 1020)), ("p", (740, 590), 1),
        ("c", (34, 1048, 746, 1200)), ("p", (740, 1058), 2),
        ("c", (34, 1230, 746, 1620)), ("p", (740, 1240), 3)])
    ecran("etape4.png", "ecran_etape4.jpg", [("c", (34, 826, 746, 1230)), ("p", (740, 836), 1)])
    ecran("etape4_pret.png", "ecran_etape4_pret.jpg", [("c", (30, 776, 750, 1170)), ("p", (740, 786), 2)])
    ecran("etape2_u1.png", "ecran_etape2_u1.jpg", [("c", (34, 576, 746, 930)), ("p", (740, 586), "!")])
    ecran("etape4_active_off.png", "ecran_etape4_active_off.jpg", [("c", (34, 826, 746, 1080)), ("p", (740, 836), "!")])


def rangee_mode():
    im = Image.open(ICI / "photos/tout_off.png").convert("RGB")
    d = ImageDraw.Draw(im)
    groupes = [
        ((492, 912, 552, 1200), VERT, 1, 522),
        ((558, 912, 618, 1200), ORANGE, 2, 588),
        ((624, 912, 946, 1200), GRIS, 3, 785),
        ((950, 912, 1078, 1200), VERT, 4, 1000),
    ]
    for box, coul, n, cx in groupes:
        d.rounded_rectangle(box, 12, outline=BLANC, width=12)
        d.rounded_rectangle([box[0] + 2, box[1] + 2, box[2] - 2, box[3] - 2], 10, outline=coul, width=8)
        pastille(d, (cx, 1258), n, r=28, coul=coul)
    sauver(im, "rangee_mode.jpg", crop=(440, 860, 1120, 1300), maxw=900)


def main():
    rangee_mode()
    ecrans()
    carte_reperes()
    position("tout_off.png", "pos_tout_off.jpg", False, False, (470, 380, 1370, 1400))
    position("debug_sans_active.png", "pos_debug_sans_active.jpg", False, True, (600, 560, 1500, 1500))
    position("active_debug.png", "pos_active_debug.jpg", True, True, (600, 420, 1500, 1300))
    position("active_seul.png", "pos_active_seul.jpg", True, False, (500, 380, 1400, 1260))


if __name__ == "__main__":
    main()
