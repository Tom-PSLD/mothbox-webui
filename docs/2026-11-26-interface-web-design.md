# Interface web de paramétrage Mothbox — conception

Date : 2026-11-26 · Base : image `mothbox_Pro_Pi5_v5.2.1_2026_04_04`

## 1. Pourquoi

Les clients qui reçoivent une Mothbox n'arrivent pas à la paramétrer sur le terrain. Aujourd'hui il faut soit
les switches de la carte, soit passer en mode Debug puis VNC (logiciel à installer, identifiants, savoir que les
réglages sont dans `/boot/firmware/mothbox_custom/mothbox_settings.csv`). Objectif : le client bascule le switch
Debug sur ON, se connecte avec son téléphone au wifi de la Mothbox, une page s'ouvre, il règle et teste tout,
puis rebascule Debug sur OFF : la Mothbox est opérationnelle.

## 2. Objectifs

- Page web servie par la Mothbox elle-même, en mode Debug uniquement, accessible depuis n'importe quel téléphone
  ou PC sans rien installer.
- Utilisable par tous les niveaux : parcours guidé en 4 étapes, réglages fins repliés dans « Réglages avancés ».
- Bilingue français / anglais : langue du téléphone détectée, bouton pour basculer.
- Étapes :

    1. **Heure & lieu** — l'heure du téléphone est envoyée à la Mothbox ; le fuseau horaire du téléphone est
       présélectionné, modifiable par deux listes déroulantes (région → ville) alimentées par `timezone_list.txt`.
    2. **Planning** — jours, heures, minute de départ, durée de session ; écrit dans `mothbox_settings.csv`.
       La page lit les switches et indique clairement quelle source commande : si U1 = ON, les switches de la carte
       priment (comportement actuel de `Scheduler.py`, inchangé) ; la page affiche alors le planning des switches
       et signale que ses propres réglages sont ignorés. Affiche « prochaine session : … ».
    3. **Tester** — boutons marche/arrêt : attracteur UV, flash, 12 V ; bouton « photo test » qui affiche l'image
       sur le téléphone (vérifier mise au point et cadrage) ; mesures en direct : batterie (V et %), température,
       espace libre, GPS.
    4. **Terminer** — récapitulatif ; consigne « basculez le switch Debug sur OFF ». La page surveille l'état du
       switch ; quand Debug passe à OFF, elle propose « Redémarrer maintenant » (les switches ne sont lus qu'au
       démarrage par `Scheduler.py`) et explique ce qui va se passer (veille jusqu'à la prochaine session).

- Réglages avancés : nom de la Mothbox (`autoname`/`name`), paramètres batterie (`bat_voltage`, `bat_Wh`,
  `bat_80perVolts`, `bat_20perVolts`).

## 3. Non-objectifs (v1)

- Modifier la logique de `Scheduler.py`, des modes ou du réveil.
- Éditer les réglages caméra (`camera_settings.csv`).
- Parcourir / télécharger les photos de session, envoi vers internet, mode HI_POW, programmation par QR code.
- Authentification au-delà du mot de passe wifi.
- Accès à la page en mode Active (option B écartée).

## 4. Anti-objectifs (échec même si « ça marche »)

- Une Mothbox qui ne se réveille plus ou rate ses sessions à cause d'un CSV mal réécrit.
- Un UV / flash / 12 V laissé allumé qui vide la batterie après une séance de test.
- Une page qui charge des ressources sur internet (il n'y a pas d'internet sur le terrain).
- Une interface qui suppose des connaissances Linux (chemins, cron, UTC…).
- Une modification de l'image qui empêche de reprendre les futures versions publiées par l'équipe Mothbox.

## 5. Contraintes

- Matériel : Raspberry Pi 5, carte Mothbox (PCA9555 ×3 pour les switches, GPIO 5/6/9/19/22 + GPIO7 via `pinctrl`).
- Logiciel existant réutilisé tel quel : `Attract_On/Off.py`, `Flash_On/Off.py`, `scripts/12vOn/Off.py`,
  `GetConfigSwitches.py` (écrit `system/controls/switches.txt`), scripts de mesure de `scripts/`.
- Flask est déjà installé dans l'image. Tout le front (HTML/CSS/JS, polices) est embarqué localement.
- Le hotspot existe déjà : AccessPopup crée `mothboxwifi` (mdp `lunaluna`) quand aucun wifi connu n'est à portée ;
  le mode Debug garde le wifi allumé (`stop_lowpower.sh`).
- `mothbox_settings.csv` a un format particulier (valeurs multiples réparties sur plusieurs colonnes, ex.
  `weekday,1,2,3,4,5,6,7,...`). La réécriture doit produire exactement ce que `load_settings()` de
  `Scheduler.py` sait relire, préserver les autres lignes et la colonne DETAILS, et être atomique
  (fichier temporaire + `os.replace`, comme le reste du code).
- `TakePhoto.py` refuse de photographier en mode DEBUG : la photo test passe par une capture dédiée
  (picamera2 / `rpicam-still`, basse résolution, flash allumé pendant la prise) et ne va pas dans `photos/`.
- La page doit fonctionner sur Safari iOS et Chrome Android, écran de téléphone.

## 6. Approches envisagées

- **A. Serveur Flask sur le Pi, actif seulement en mode Debug, avec portail captif — retenue.** Aucun coût
  énergétique ni exposition en service ; demande de basculer le switch pour paramétrer.
- B. Idem mais accessible aussi en début de session Active : plus pratique pour vérifier une box en service, mais
  consommation, serveur exposé en fonctionnement, risque de modifier le planning en pleine session.
- C. Simplifier les fichiers à éditer en sortant la carte SD : quasi gratuit, mais ne règle ni les tests ni
  l'heure, et reste difficile pour un débutant.
- Écartées : Bluetooth (Web Bluetooth absent de Safari iOS), application mobile native (installation, maintenance).

## 7. Conception retenue

### Démarrage
- Service systemd `mothbox-webui.service` (root, car les scripts matériels et `date`/`hwclock` l'exigent),
  **non activé au boot**. `DebugMode.py` le démarre (une ligne ajoutée à la fin : `systemctl start mothbox-webui`).
  Ainsi il ne tourne qu'en DEBUG / PARTY.
- Écoute sur le port 80.

### Réseau
- Portail captif : en mode hotspot, le dnsmasq de NetworkManager répond l'IP du Pi à toutes les requêtes DNS
  (fichier dans `/etc/NetworkManager/dnsmasq-shared.d/`), et Flask répond aux URL de détection
  (`/generate_204`, `/hotspot-detect.html`, …) par une redirection vers la page. Le téléphone ouvre la page seul.
- Sur un réseau connu (chez nous, en test) : accès par `http://<nom-hôte>.local`.
- SSID propre à chaque box (`Mothbox-<nom>`) pour distinguer plusieurs boxes sur un même site ; même mot de
  passe pour toutes, imprimé sur l'étiquette. *(choix proposé)*
- L'image livrée ne contient plus aucun profil wifi enregistré (aujourd'hui : STARLINK, Tigo, LIB…).

### Heure & fuseau
- Le navigateur envoie `Date.now()` (UTC) et `Intl.DateTimeFormat().resolvedOptions().timeZone`.
- Le serveur règle l'horloge système (`date -s @epoch`) puis la RTC (`hwclock -w`), applique le fuseau
  (`timedatectl set-timezone`) et l'écrit dans le CSV (`timezone`) ; `autoSystemTime` reste à `True` pour ne pas
  déclencher la logique `manualTime`. L'écart avant/après est affiché au client.
- Si le fuseau du téléphone n'est pas dans `timezone_list.txt`, rien n'est présélectionné.

### Sécurité d'usage des tests
- Chaque sortie allumée depuis la page s'éteint automatiquement après 5 min, et toutes s'éteignent si la page
  n'envoie plus de signal de vie pendant 30 s (onglet fermé, téléphone parti).
- Un seul test matériel à la fois côté serveur (verrou) pour éviter les conflits GPIO.

### Organisation du code
- `Mothbox/webui/` : `app.py` (routes), un module par domaine (`settings_csv`, `hardware`, `clock`, `sensors`),
  `static/` (une page, JS sans framework externe, dictionnaire `i18n.json` FR/EN), `install.sh`.
- Une couche « matériel simulé » activable par variable d'environnement pour développer et tester sur PC.

### Livraison
- `install.sh` : copie `webui/`, installe le service et la config dnsmasq, ajoute la ligne à `DebugMode.py`,
  règle le SSID AccessPopup, purge les profils wifi. Idempotent, rejouable sur une future image Mothbox.
- Puis nouvelle image dérivée de 5.2.1 (checklist `zzzz_NewImageChecklist.txt` + étapes ci-dessus).
- Seules les Mothbox expédiées avec la nouvelle image reçoivent l'interface : pas de mise à jour des boxes déjà
  livrées, pas de procédure d'installation hors ligne à prévoir.

### Horloge
- Les Pi 5 des Mothbox ont une pile RTC : l'heure réglée depuis le téléphone est conservée hors tension.
  Aucun avertissement particulier à afficher.

## 8. Laissé au développeur

- Choix exact des scripts de mesure batterie / température (INA219 interne, `cpuTemp.py`, …) et fréquence de
  rafraîchissement.
- Mise en page détaillée, dans le respect du parcours en 4 étapes et de la lisibilité sur téléphone.
- Détail des routes HTTP et du format JSON.
- Méthode de capture de la photo test et résolution.
