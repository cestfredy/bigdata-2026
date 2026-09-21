#!/usr/bin/env python3
"""
Génère les jeux de données pédagogiques du cours, en deux variantes de filière.

    Ingénierie Financière (if) : transactions de paiement, comptes, marchands
    Art Numérique         (an) : événements d'interaction, œuvres, utilisateurs

Les données sont synthétiques mais réalistes : distributions déséquilibrées
volontaires (loi de puissance sur les comptes et sur les œuvres), valeurs
manquantes, doublons et anomalies injectés en proportion contrôlée. Ces défauts
ne sont pas des bugs : ils servent aux TP de qualité de données (M2) et de
correction de déséquilibre (M4).

Exécution depuis le conteneur jupyter :

    python /home/tinku/cours/99-Infra/scripts/generate_datasets.py \
        --filiere if --sortie /home/tinku/data --evenements 2000000

Le générateur est déterministe à graine fixée : tous les étudiants obtiennent
exactement le même jeu de données, donc les mêmes résultats numériques.
"""

from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

GRAINE = 20260101

# --------------------------------------------------------------------------
#  Référentiels
# --------------------------------------------------------------------------
PAYS = ["FR", "FR", "FR", "FR", "BE", "DE", "ES", "IT", "GB", "US", "MA", "SN", "CI"]
CANAUX = ["carte_physique", "carte_en_ligne", "virement", "prelevement", "mobile"]
SECTEURS = ["alimentation", "carburant", "restauration", "voyage", "electronique",
            "habillement", "sante", "loisirs", "telecom", "energie", "crypto"]
DEVISES = ["EUR", "EUR", "EUR", "EUR", "USD", "GBP", "XOF"]

TYPES_OEUVRE = ["video", "audio", "image", "modele_3d", "generative", "interactif"]
EVENEMENTS = ["ouverture", "lecture", "pause", "partage", "favori", "fin"]
POIDS_EV = [0.30, 0.28, 0.14, 0.06, 0.07, 0.15]
APPAREILS = ["mobile_ios", "mobile_android", "web_desktop", "tv_connectee", "casque_vr"]
POIDS_APP = [0.28, 0.31, 0.24, 0.13, 0.04]


def zipf_ids(n_ids: int, alpha: float, rng: random.Random):
    """Retourne une fonction tirant un identifiant selon une loi de puissance.

    Sert à créer un déséquilibre réaliste : quelques comptes (ou quelques
    œuvres) concentrent une part disproportionnée de l'activité. C'est ce
    déséquilibre qui provoquera le *skew* étudié au module 4.
    """
    poids = [1.0 / ((i + 1) ** alpha) for i in range(n_ids)]
    total = sum(poids)
    cumul, acc = [], 0.0
    for p in poids:
        acc += p / total
        cumul.append(acc)

    def tirer() -> int:
        u = rng.random()
        lo, hi = 0, n_ids - 1
        while lo < hi:                      # recherche dichotomique
            mid = (lo + hi) // 2
            if cumul[mid] < u:
                lo = mid + 1
            else:
                hi = mid
        return lo

    return tirer


def horodatage(rng: random.Random, debut: datetime, jours: int) -> datetime:
    """Instant aléatoire avec un profil horaire réaliste (creux la nuit)."""
    jour = rng.randrange(jours)
    # profil sur 24 h : pic en soirée, creux entre 2 h et 6 h
    profil = [0.4, 0.25, 0.15, 0.12, 0.12, 0.2, 0.5, 1.0, 1.4, 1.3, 1.2, 1.5,
              1.7, 1.4, 1.2, 1.3, 1.5, 1.9, 2.4, 2.6, 2.2, 1.7, 1.1, 0.7]
    total = sum(profil)
    u = rng.random() * total
    acc, heure = 0.0, 23
    for h, p in enumerate(profil):
        acc += p
        if u <= acc:
            heure = h
            break
    return debut + timedelta(days=jour, hours=heure,
                             minutes=rng.randrange(60), seconds=rng.randrange(60),
                             milliseconds=rng.randrange(1000))


# --------------------------------------------------------------------------
#  Filière Ingénierie Financière
# --------------------------------------------------------------------------
def generer_if(sortie: Path, n_ev: int, jours: int, compresser: bool):
    rng = random.Random(GRAINE)
    n_comptes, n_marchands = 60_000, 8_000
    debut = datetime(2025, 1, 1, tzinfo=timezone.utc)

    # ---- référentiel des comptes
    comptes = []
    for i in range(n_comptes):
        ouverture = debut - timedelta(days=rng.randrange(30, 5000))
        comptes.append({
            "id_compte": f"C{i:07d}",
            "segment": rng.choices(["particulier", "professionnel", "premium"],
                                   weights=[0.78, 0.17, 0.05])[0],
            "pays": rng.choices(PAYS)[0],
            "date_ouverture": ouverture.date().isoformat(),
            "plafond_mensuel": rng.choice([1500, 3000, 5000, 10000, 25000]),
        })
    _ecrire_csv(sortie / "if_comptes.csv", comptes)

    # ---- référentiel des marchands
    marchands = []
    for i in range(n_marchands):
        marchands.append({
            "id_marchand": f"M{i:06d}",
            "secteur": rng.choices(SECTEURS,
                                   weights=[18, 12, 14, 8, 9, 10, 6, 8, 6, 5, 4])[0],
            "pays": rng.choices(PAYS)[0],
            "note_risque": round(min(1.0, abs(rng.gauss(0.18, 0.16))), 3),
        })
    _ecrire_csv(sortie / "if_marchands.csv", marchands)

    # ---- transactions
    tirer_compte = zipf_ids(n_comptes, 0.85, rng)
    tirer_marchand = zipf_ids(n_marchands, 1.05, rng)
    chemin = sortie / ("if_transactions.jsonl.gz" if compresser else "if_transactions.jsonl")
    ouvrir = (lambda p: gzip.open(p, "wt", encoding="utf-8")) if compresser \
        else (lambda p: open(p, "w", encoding="utf-8"))

    n_fraude = 0
    with ouvrir(chemin) as f:
        for k in range(n_ev):
            ts = horodatage(rng, debut, jours)
            ic, im = tirer_compte(), tirer_marchand()
            secteur = marchands[im]["secteur"]

            # montant log-normal, dépendant du secteur
            base = {"alimentation": 3.1, "carburant": 3.9, "restauration": 3.3,
                    "voyage": 5.6, "electronique": 5.2, "habillement": 4.1,
                    "sante": 3.6, "loisirs": 3.5, "telecom": 3.4,
                    "energie": 4.4, "crypto": 6.1}[secteur]
            montant = round(math.exp(rng.gauss(base, 0.85)), 2)

            frauduleuse = rng.random() < 0.0017          # ~0,17 % de fraude
            if frauduleuse:
                montant = round(montant * rng.uniform(4, 30), 2)
                n_fraude += 1

            tx = {
                "id_transaction": f"T{k:09d}",
                "horodatage": ts.isoformat(),
                "id_compte": comptes[ic]["id_compte"],
                "id_marchand": marchands[im]["id_marchand"],
                "montant": montant,
                "devise": rng.choices(DEVISES)[0],
                "canal": rng.choices(CANAUX, weights=[34, 38, 12, 9, 7])[0],
                "pays_transaction": (rng.choices(PAYS)[0] if frauduleuse
                                     else comptes[ic]["pays"]),
                "statut": rng.choices(["acceptee", "refusee", "en_attente"],
                                      weights=[0.94, 0.05, 0.01])[0],
                "est_fraude": frauduleuse,
            }
            # défauts injectés volontairement (TP qualité de données, module 2)
            if rng.random() < 0.004:
                tx["montant"] = None
            if rng.random() < 0.002:
                tx["pays_transaction"] = ""
            f.write(json.dumps(tx, ensure_ascii=False) + "\n")

            # doublons exacts : ~0,1 %
            if rng.random() < 0.001:
                f.write(json.dumps(tx, ensure_ascii=False) + "\n")

    _resume("Ingénierie Financière", sortie, n_ev, n_fraude, chemin,
            [f"if_comptes.csv ({n_comptes:,} lignes)",
             f"if_marchands.csv ({n_marchands:,} lignes)"])


# --------------------------------------------------------------------------
#  Filière Art Numérique
# --------------------------------------------------------------------------
def generer_an(sortie: Path, n_ev: int, jours: int, compresser: bool):
    rng = random.Random(GRAINE)
    n_users, n_oeuvres = 80_000, 12_000
    debut = datetime(2025, 1, 1, tzinfo=timezone.utc)

    utilisateurs = []
    for i in range(n_users):
        utilisateurs.append({
            "id_utilisateur": f"U{i:07d}",
            "pays": rng.choices(PAYS)[0],
            "abonnement": rng.choices(["gratuit", "standard", "premium"],
                                      weights=[0.62, 0.29, 0.09])[0],
            "date_inscription": (debut - timedelta(days=rng.randrange(1, 2200))
                                 ).date().isoformat(),
        })
    _ecrire_csv(sortie / "an_utilisateurs.csv", utilisateurs)

    oeuvres = []
    for i in range(n_oeuvres):
        t = rng.choices(TYPES_OEUVRE, weights=[30, 22, 18, 10, 14, 6])[0]
        oeuvres.append({
            "id_oeuvre": f"O{i:06d}",
            "type": t,
            "duree_s": (rng.randrange(30, 5400) if t in ("video", "audio") else 0),
            "annee": rng.randrange(1998, 2026),
            "taille_mio": round(abs(rng.gauss({"video": 900, "audio": 45, "image": 28,
                                               "modele_3d": 320, "generative": 140,
                                               "interactif": 260}[t], 60)), 1),
            "pays_origine": rng.choices(PAYS)[0],
        })
    _ecrire_csv(sortie / "an_oeuvres.csv", oeuvres)

    tirer_user = zipf_ids(n_users, 0.75, rng)
    tirer_oeuvre = zipf_ids(n_oeuvres, 1.15, rng)   # quelques œuvres très populaires
    chemin = sortie / ("an_evenements.jsonl.gz" if compresser else "an_evenements.jsonl")
    ouvrir = (lambda p: gzip.open(p, "wt", encoding="utf-8")) if compresser \
        else (lambda p: open(p, "w", encoding="utf-8"))

    n_abandon = 0
    with ouvrir(chemin) as f:
        for k in range(n_ev):
            ts = horodatage(rng, debut, jours)
            iu, io = tirer_user(), tirer_oeuvre()
            oe = oeuvres[io]
            ev = rng.choices(EVENEMENTS, weights=POIDS_EV)[0]

            duree = oe["duree_s"] or 120
            position = (0 if ev == "ouverture"
                        else duree if ev == "fin"
                        else rng.randrange(0, max(1, duree)))
            abandon = ev == "pause" and position < 0.1 * duree
            n_abandon += abandon

            e = {
                "id_evenement": f"E{k:09d}",
                "horodatage": ts.isoformat(),
                "id_utilisateur": utilisateurs[iu]["id_utilisateur"],
                "id_oeuvre": oe["id_oeuvre"],
                "type_evenement": ev,
                "position_s": position,
                "appareil": rng.choices(APPAREILS, weights=POIDS_APP)[0],
                "pays": utilisateurs[iu]["pays"],
                "qualite": rng.choices(["360p", "720p", "1080p", "4k"],
                                       weights=[8, 34, 44, 14])[0],
                "ms_mise_en_tampon": max(0, int(rng.gauss(180, 260))),
            }
            if rng.random() < 0.004:
                e["position_s"] = None
            if rng.random() < 0.002:
                e["appareil"] = ""
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            if rng.random() < 0.001:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    _resume("Art Numérique", sortie, n_ev, n_abandon, chemin,
            [f"an_utilisateurs.csv ({n_users:,} lignes)",
             f"an_oeuvres.csv ({n_oeuvres:,} lignes)"])


# --------------------------------------------------------------------------
def _ecrire_csv(chemin: Path, lignes: list[dict]):
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)


def _resume(filiere, sortie, n_ev, n_special, chemin, autres):
    taille = chemin.stat().st_size
    print(f"\n  Filière : {filiere}")
    print(f"  Dossier : {sortie}")
    print(f"   - {chemin.name}  ({n_ev:,} lignes, {taille/1024**2:.1f} Mio)")
    for a in autres:
        print(f"   - {a}")
    print(f"   - dont {n_special:,} lignes remarquables "
          f"({100*n_special/n_ev:.2f} %)\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--filiere", choices=["if", "an", "les-deux"], default="les-deux",
                    help="if = Ingénierie Financière, an = Art Numérique")
    ap.add_argument("--sortie", type=Path, default=Path("/home/tinku/data"),
                    help="répertoire de sortie")
    ap.add_argument("--evenements", type=int, default=2_000_000,
                    help="nombre de lignes de la table de faits")
    ap.add_argument("--jours", type=int, default=90,
                    help="profondeur d'historique simulée")
    ap.add_argument("--compresser", action="store_true",
                    help="écrire en .jsonl.gz (attention : gzip n'est pas splittable)")
    a = ap.parse_args()

    a.sortie.mkdir(parents=True, exist_ok=True)
    print(f"Génération — graine {GRAINE}, {a.evenements:,} événements sur {a.jours} jours")
    if a.filiere in ("if", "les-deux"):
        generer_if(a.sortie, a.evenements, a.jours, a.compresser)
    if a.filiere in ("an", "les-deux"):
        generer_an(a.sortie, a.evenements, a.jours, a.compresser)
    print("Terminé.")


if __name__ == "__main__":
    main()
