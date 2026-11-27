# Mothbox WebUI

**Français** · [English](#english)

Page web de paramétrage terrain pour la [Mothbox](https://digital-naturalism-laboratories.github.io/Mothbox/) (Pro, Raspberry Pi 5, logiciel 5.2.1).

Sur le terrain, plus besoin de VNC ni de modifier un fichier CSV : on bascule le switch **Debug** sur ON, on se connecte avec son téléphone au wifi de la Mothbox, et une page s'ouvre toute seule. Elle guide en 4 étapes :

1. **Heure et lieu** : l'heure et le fuseau horaire du téléphone sont envoyés à la Mothbox.
2. **Planning** : jours, heures et durée des sessions (écrit dans `mothbox_settings.csv`, compatible avec `Scheduler.py`). Si le switch U1 est sur ON, la page indique que ce sont les switches de la carte qui commandent.
3. **Tester** : attracteur UV, flash, 12 V, photo test affichée sur le téléphone (mise au point, cadrage), batterie, température, espace libre, GPS.
4. **Terminer** : récapitulatif, puis Debug sur OFF et redémarrage.

Boutons **Redémarrer** et **Éteindre** toujours visibles en bas de page (confirmation, avec l'heure du prochain réveil automatique).

Interface en français et en anglais (langue du téléphone détectée). Le wifi de chaque box s'appelle `Mothbox-<nom>` pour distinguer plusieurs boxes sur un même site.

## Installation : image prête à flasher

Télécharger l'image dans les [Releases](../../releases) et l'écrire sur la carte microSD avec **Raspberry Pi Imager** (Utiliser une image personnalisée). Inutile de décompresser le fichier.

L'image contient le système Mothbox 5.2.1 d'origine, complété par la page de réglage, et **aucun réseau wifi enregistré** (seul le hotspot `Mothbox-<nom>` est préconfiguré).

## Guides

| | Français | English |
|---|---|---|
| Guide de terrain illustré | [guide-mothbox.pdf](docs/guide/guide-mothbox.pdf) · [paysage](docs/guide/guide-mothbox-paysage.pdf) | |
| Notice de paramétrage | [notice-mothbox.pdf](docs/guide/notice-mothbox.pdf) | [notice-mothbox-en.pdf](docs/guide/notice-mothbox-en.pdf) |

## Installer sur une Mothbox existante

Sur la box (mode Debug, connectée en SSH ou VNC) :

```bash
git clone https://github.com/Tom-PSLD/mothbox-webui.git
cd mothbox-webui
sudo deploy/install.sh
```

Le script copie la page dans `~/Desktop/Mothbox/webui`, installe le service `mothbox-webui` (lancé uniquement en mode Debug), le portail captif, renomme le hotspot en `Mothbox-<nom>`, remplace les réseaux wifi enregistrés par un profil hotspot propre, et corrige deux défauts de Mothbox 5.2.1 : la réécriture de l'EEPROM (`BOOT_ORDER`) par `Scheduler.py` et la suppression du profil hotspot par `accesspopup` quand le wifi n'est pas encore prêt. Il peut être rejoué sans risque. `--root DIR` permet de l'appliquer sur une image montée.

## Essayer sur un PC (simulation)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m webui --sim      # http://localhost:8080
.venv/bin/python -m pytest           # 115 tests
```

## Contenu

- `webui/` : application Flask et page web (`static/`)
- `deploy/` : script d'installation, service systemd, configuration du portail captif
- `docs/` : conception et guides (sources LaTeX + PDF)
- `tests/` : tests automatiques
- `reference_v5.2.1/` : scripts Mothbox 5.2.1 d'origine, utilisés par la simulation et les tests

## Licence

Code et guides sous licence MIT (voir [LICENSE](LICENSE)).
`reference_v5.2.1/` contient des fichiers tiers sous leur propre licence : scripts Mothbox © Digital Naturalism Laboratories (MIT), `accesspopup` © Graeme Richards, RaspberryConnect.com (GPL v3).

---

<a id="english"></a>

# Mothbox WebUI (English)

Field setup web page for the [Mothbox](https://digital-naturalism-laboratories.github.io/Mothbox/) (Pro, Raspberry Pi 5, software 5.2.1).

No more VNC or CSV editing in the field: flip the **Debug** switch ON, join the Mothbox wifi with your phone, and a page opens by itself. It guides you through 4 steps:

1. **Time and place**: the phone's time and time zone are sent to the Mothbox.
2. **Schedule**: days, hours and session length (written to `mothbox_settings.csv`, compatible with `Scheduler.py`). If switch U1 is ON, the page shows that the board switches are in control.
3. **Test**: UV attractor, flash, 12 V, test photo shown on the phone (focus, framing), battery, temperature, free space, GPS.
4. **Finish**: summary, then Debug OFF and reboot.

**Restart** and **Shut down** buttons always visible at the bottom of the page (with confirmation and the next automatic wake-up time).

French and English interface (phone language detected). Each box's wifi is named `Mothbox-<name>` to tell several boxes apart on one site.

## Install: ready-to-flash image

Download the image from the [Releases](../../releases) and write it to the microSD card with **Raspberry Pi Imager** (Use custom image). No need to unzip it.

The image contains the original Mothbox 5.2.1 system plus the setup page, and **no saved wifi network** (only the `Mothbox-<name>` hotspot is preconfigured).

## Guides

- Setup guide: [notice-mothbox-en.pdf](docs/guide/notice-mothbox-en.pdf)
- French: [illustrated field guide](docs/guide/guide-mothbox.pdf), [setup guide](docs/guide/notice-mothbox.pdf)

## Install on an existing Mothbox

On the box (Debug mode, via SSH or VNC):

```bash
git clone https://github.com/Tom-PSLD/mothbox-webui.git
cd mothbox-webui
sudo deploy/install.sh
```

The script copies the page to `~/Desktop/Mothbox/webui`, installs the `mothbox-webui` service (runs in Debug mode only) and the captive portal, renames the hotspot to `Mothbox-<name>`, replaces saved wifi networks with a clean hotspot profile, and fixes two Mothbox 5.2.1 defects: `Scheduler.py` rewriting the EEPROM (`BOOT_ORDER`) and `accesspopup` deleting the hotspot profile when the wifi is not ready yet. It is safe to run again. `--root DIR` applies it to a mounted image.

## Try it on a PC (simulation)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m webui --sim      # http://localhost:8080
.venv/bin/python -m pytest           # 115 tests
```

## License

Code and guides under the MIT license (see [LICENSE](LICENSE)).
`reference_v5.2.1/` holds third-party files under their own licenses: Mothbox scripts © Digital Naturalism Laboratories (MIT), `accesspopup` © Graeme Richards, RaspberryConnect.com (GPL v3).
