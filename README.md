# Batterie

**L'état réel de la batterie de ton MacBook, en clair.** macOS se contente d'un « Normal » ; Batterie te montre la vraie santé, les cycles, la consommation, le chargeur branché — et suit l'usure dans le temps.

```
$ python3 batterie.py

  Batterie

  Charge        ████████████████░░░░   80 %  Branché · charge en pause (recharge optimisée)
  Santé         ██████████████████░░  88,8 %  Bonne  (4054 sur 4563 mAh d'origine)
  Cycles        ███████░░░░░░░░░░░░░  335 / 1000  34 % de la durée de vie prévue par Apple
  Consommation  12,6 W  (tout le Mac, en ce moment)
  Chargeur      75 W  (20 V)
  Évolution     -2,7 points de santé et 85 cycles en 147 jours (depuis le 2026-06-01)

  → Tout va bien. Garde la « recharge optimisée » activée pour ménager la batterie.
```

- **Santé réelle** : capacité actuelle comparée à la capacité d'origine, en mAh.
- **Cycles** comparés à la durée de vie prévue par Apple pour ton modèle.
- **Consommation instantanée** de tout le Mac, en watts, et **puissance du chargeur** branché (pratique pour vérifier un câble ou un chargeur USB-C).
- **Explique la charge** : « en pause » à 80 % n'est pas une panne, c'est la recharge optimisée.
- **Suivi de l'usure** : chaque lancement enregistre une mesure par jour dans `~/Library/Application Support/Batterie/historique.csv`, et Batterie affiche l'évolution.
- **Mode direct** : `--direct` affiche la consommation toutes les 2 secondes pour voir quelle app fait chauffer le Mac.
- **JSON** : `--json` pour l'utiliser dans tes propres scripts.
- Un seul fichier Python, aucune dépendance. Lit simplement les informations que macOS expose (`ioreg`), sans privilèges administrateur.

## Utilisation

```bash
python3 batterie.py
python3 batterie.py --direct
python3 batterie.py --json
```

Astuce : ajoute `alias batterie="python3 ~/chemin/vers/batterie.py"` dans ton `~/.zshrc` pour taper simplement `batterie`.

## Licence

MIT
