#!/usr/bin/env python3
"""
Génère le jeu d'images synthétiques du TP11 (module 6).

Pourquoi des images synthétiques plutôt qu'un jeu réel :

  1. Aucun téléchargement, aucune question de licence ni de données personnelles.
  2. La **vérité terrain est connue** — on sait exactement quelles formes se
     trouvent où. On peut donc vérifier qu'une chaîne de détection fonctionne,
     indépendamment de la qualité du modèle.
  3. Et surtout : un modèle pré-entraîné sur ImageNet appliqué à ces images
     produira des prédictions **confiantes et absurdes**. C'est délibéré. Cela
     donne à observer, en conditions réelles, le décalage de distribution
     (*domain shift*) évoqué au module 6 — un modèle hors de son domaine
     d'entraînement ne dit pas « je ne sais pas », il se trompe avec assurance.

Exécution depuis le conteneur jupyter :

    python /home/tinku/cours/99-Infra/scripts/generate_images.py \
        --sortie /home/tinku/work/images --nombre 4000

Le générateur est déterministe à graine fixée.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import random
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    raise SystemExit(
        "Pillow est requis.  Dans le conteneur : pip install pillow\n"
        "Il figure dans 99-Infra/docker/requirements.txt.")

GRAINE = 20260601

# Les cinq classes du jeu, et leur couleur dominante
CLASSES = ["cercle", "carre", "triangle", "etoile", "anneau"]

FONDS = [
    (238, 238, 238), (250, 245, 235), (232, 240, 244),
    (245, 235, 240), (235, 244, 236),
]

PALETTE = [
    (0x00, 0x79, 0x6B), (0xD9, 0x56, 0x3F), (0xC4, 0xA1, 0x5A),
    (0x3D, 0x45, 0x94), (0x23, 0x3A, 0x44), (0xAF, 0x7B, 0x51),
]


def _etoile(cx, cy, r_ext, r_int, branches=5, rotation=0.0):
    points = []
    for i in range(branches * 2):
        r = r_ext if i % 2 == 0 else r_int
        a = rotation + i * math.pi / branches
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return points


def dessiner(rng: random.Random, taille: int):
    """Retourne (image, liste d'objets) — chaque objet porte sa boîte englobante."""
    img = Image.new("RGB", (taille, taille), rng.choice(FONDS))
    d = ImageDraw.Draw(img)
    objets = []

    for _ in range(rng.randint(1, 4)):
        classe = rng.choice(CLASSES)
        couleur = rng.choice(PALETTE)
        r = rng.randint(taille // 10, taille // 4)
        cx = rng.randint(r + 2, taille - r - 2)
        cy = rng.randint(r + 2, taille - r - 2)
        boite = [cx - r, cy - r, cx + r, cy + r]

        if classe == "cercle":
            d.ellipse(boite, fill=couleur)
        elif classe == "carre":
            d.rectangle(boite, fill=couleur)
        elif classe == "triangle":
            d.polygon([(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)], fill=couleur)
        elif classe == "etoile":
            d.polygon(_etoile(cx, cy, r, r * 0.45, 5, rng.random() * math.pi),
                      fill=couleur)
        else:  # anneau
            d.ellipse(boite, outline=couleur, width=max(3, r // 4))

        objets.append({
            "classe": classe,
            # boîte normalisée, convention (x_min, y_min, x_max, y_max) dans [0,1]
            "boite": [round(v / taille, 4) for v in boite],
        })

    # un peu de bruit, pour que les images ne se compressent pas trivialement
    if rng.random() < 0.4:
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 1.2)))
    return img, objets


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sortie", type=Path, default=Path("/home/tinku/work/images"))
    ap.add_argument("--nombre", type=int, default=4000,
                    help="nombre d'images à produire")
    ap.add_argument("--taille", type=int, default=224,
                    help="côté de l'image en pixels (224 = entrée usuelle des "
                         "modèles de classification)")
    ap.add_argument("--qualite", type=int, default=88, help="qualité JPEG")
    ap.add_argument("--sous-dossiers", type=int, default=0,
                    help="répartir en N sous-dossiers ; 0 = tout à plat")
    a = ap.parse_args()

    rng = random.Random(GRAINE)
    racine = a.sortie
    racine.mkdir(parents=True, exist_ok=True)

    verite = []
    print(f"Génération de {a.nombre:,} images {a.taille}x{a.taille} "
          f"(graine {GRAINE})")

    for i in range(a.nombre):
        img, objets = dessiner(rng, a.taille)
        if a.sous_dossiers:
            d = racine / f"lot_{i % a.sous_dossiers:03d}"
            d.mkdir(exist_ok=True)
        else:
            d = racine
        nom = f"img_{i:06d}.jpg"
        img.save(d / nom, "JPEG", quality=a.qualite)
        verite.append({
            "fichier": nom,
            "chemin_relatif": str((d / nom).relative_to(racine)).replace("\\", "/"),
            "nb_objets": len(objets),
            # classe dominante = celle du plus gros objet, pour la classification
            "classe_dominante": max(
                objets,
                key=lambda o: (o["boite"][2] - o["boite"][0]))["classe"],
            "objets": objets,
        })
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1:,} images…")

    # Vérité terrain : un JSON Lines, lisible par Spark
    chemin_verite = racine.parent / (racine.name + "_verite.jsonl")
    with open(chemin_verite, "w", encoding="utf-8") as f:
        for v in verite:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    # Et un CSV léger pour les inspections rapides
    with open(racine.parent / (racine.name + "_verite.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fichier", "chemin_relatif", "nb_objets", "classe_dominante"])
        for v in verite:
            w.writerow([v["fichier"], v["chemin_relatif"],
                        v["nb_objets"], v["classe_dominante"]])

    total = sum((racine / v["chemin_relatif"]).stat().st_size for v in verite)
    print(f"\n  Images   : {racine}  ({a.nombre:,} fichiers, "
          f"{total / 1024**2:.1f} Mio, moyenne {total / a.nombre / 1024:.1f} Kio)")
    print(f"  Verite   : {chemin_verite}")
    repartition = {}
    for v in verite:
        repartition[v["classe_dominante"]] = repartition.get(v["classe_dominante"], 0) + 1
    print(f"  Classes  : {repartition}")
    print("\nTermine.")


if __name__ == "__main__":
    main()
