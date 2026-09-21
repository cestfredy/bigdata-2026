#!/usr/bin/env python3
"""
Récupère les modèles ONNX pré-entraînés du TP11 (module 6).

Deux modèles, tous deux au format ONNX :

  mobilenetv2   ~14 Mio   CLASSIFICATION — 1 000 classes ImageNet
                          entrée  : 1x3x224x224, float32, normalisation ImageNet
                          sortie  : 1x1000 logits

  ssd-mobilenet ~28 Mio   DÉTECTION D'OBJETS — 90 classes COCO
                          entrée  : 1xHxWx3, uint8
                          sorties : boîtes, classes, scores, nombre de détections

Pourquoi ONNX plutôt que PyTorch ou TensorFlow :
  - un **format ouvert et portable**, indépendant du framework d'entraînement ;
  - un moteur d'exécution léger (~50 Mio) sans dépendance CUDA ;
  - c'est exactement l'argument défendu depuis le module 2 pour les données —
    ONNX est à un modèle ce que Parquet est à une table.

Exécution (une seule fois, sur une connexion confortable) :

    python 99-Infra/scripts/telecharger_modeles.py --sortie 99-Infra/modeles

Si le téléchargement échoue — les URL du ONNX Model Zoo ont changé plusieurs
fois — le script indique précisément quoi récupérer et où le déposer. Le TP11
fonctionne de toute façon **sans modèle**, en mode substitution : voir la
section 0 du notebook.
"""

from __future__ import annotations
import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_ZOO = "https://github.com/onnx/models/raw/main"

MODELES = {
    "mobilenetv2": {
        "fichier": "mobilenetv2-12.onnx",
        "urls": [
            f"{BASE_ZOO}/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx",
            f"{BASE_ZOO}/vision/classification/mobilenet/model/mobilenetv2-12.onnx",
        ],
        "taille_attendue_mio": (10, 20),
        "role": "classification (1 000 classes ImageNet)",
    },
    "ssd-mobilenet": {
        "fichier": "ssd_mobilenet_v1_10.onnx",
        "urls": [
            f"{BASE_ZOO}/validated/vision/object_detection_segmentation/ssd-mobilenetv1/model/ssd_mobilenet_v1_10.onnx",
            f"{BASE_ZOO}/vision/object_detection_segmentation/ssd-mobilenetv1/model/ssd_mobilenet_v1_10.onnx",
        ],
        "taille_attendue_mio": (20, 40),
        "role": "détection d'objets (90 classes COCO)",
    },
}

# Étiquettes ImageNet, utiles pour rendre les prédictions lisibles
ETIQUETTES = {
    "fichier": "imagenet_classes.txt",
    "urls": [
        "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt",
        "https://raw.githubusercontent.com/anishathalye/imagenet-simple-labels/master/imagenet-simple-labels.json",
    ],
    "taille_attendue_mio": (0, 1),
    "role": "noms lisibles des 1 000 classes ImageNet",
}


def telecharger(urls, destination: Path, bornes_mio) -> bool:
    """Essaie chaque URL. Retourne True au premier succès plausible."""
    if destination.exists():
        mio = destination.stat().st_size / 1024**2
        print(f"    déjà présent ({mio:.1f} Mio) — ignoré")
        return True

    destination.parent.mkdir(parents=True, exist_ok=True)
    for url in urls:
        try:
            print(f"    essai : {url[:90]}…")
            temporaire = destination.with_suffix(destination.suffix + ".partiel")
            with urllib.request.urlopen(url, timeout=60) as reponse, \
                 open(temporaire, "wb") as sortie:
                total = 0
                while True:
                    bloc = reponse.read(1 << 16)
                    if not bloc:
                        break
                    sortie.write(bloc)
                    total += len(bloc)
            mio = total / 1024**2
            mini, maxi = bornes_mio
            if not (mini <= mio <= maxi):
                print(f"    taille inattendue ({mio:.1f} Mio, attendu "
                      f"{mini}–{maxi}) — probablement une page d'erreur")
                temporaire.unlink(missing_ok=True)
                continue
            temporaire.rename(destination)
            somme = hashlib.sha256(destination.read_bytes()).hexdigest()[:16]
            print(f"    OK — {mio:.1f} Mio, sha256:{somme}…")
            return True
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            print(f"    échec : {type(e).__name__} {e}")
    return False


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sortie", type=Path,
                    default=Path(__file__).parent.parent / "modeles")
    ap.add_argument("--seulement", choices=list(MODELES) + ["etiquettes"],
                    help="ne récupérer qu'un seul élément")
    a = ap.parse_args()

    a.sortie.mkdir(parents=True, exist_ok=True)
    echecs = []

    elements = dict(MODELES)
    elements["etiquettes"] = ETIQUETTES
    if a.seulement:
        elements = {a.seulement: elements[a.seulement]}

    for nom, spec in elements.items():
        print(f"\n  {nom}  —  {spec['role']}")
        ok = telecharger(spec["urls"], a.sortie / spec["fichier"],
                         spec["taille_attendue_mio"])
        if not ok:
            echecs.append((nom, spec))

    print("\n" + "=" * 70)
    if not echecs:
        print("  Tous les modeles sont en place dans", a.sortie)
        print("  Le TP11 peut etre lance en mode reel.")
        return 0

    print("  ATTENTION — elements non recuperes :")
    for nom, spec in echecs:
        print(f"\n    {nom}  ({spec['role']})")
        print(f"      fichier attendu : {a.sortie / spec['fichier']}")
        print(f"      source          : {spec['urls'][0]}")
    print("""
  Le depot ONNX Model Zoo a change d'organisation plusieurs fois ; ces URL
  peuvent avoir bouge. Deux options :

    1. Recuperer les fichiers a la main depuis https://github.com/onnx/models
       et les deposer aux chemins indiques ci-dessus.

    2. Lancer le TP11 en MODE SUBSTITUTION : le notebook fournit un modele
       factice qui simule le cout d'une inference. Toute la partie sur la
       DISTRIBUTION — chargement du modele, amortissement, lots — reste
       valable et mesurable. Seules les predictions n'ont pas de sens.

  Pour un TP dont l'objet est la distribution, l'option 2 est acceptable.
""")
    return 1


if __name__ == "__main__":
    sys.exit(main())
