# Big Data — Architectures et Traitement Distribué
### Refonte 2025-2026 · M2 / Ingénieur — Art Numérique (N5) & Ingénierie Financière (N4)

64 h sur 16 semaines · CM, TD et TP · Hadoop 3.3.6 · Spark 3.5.3 · ONNX Runtime

---

## Par où commencer

| Vous êtes | Lisez d'abord |
|---|---|
| **Enseignant** | [`00-Syllabus/SYLLABUS.md`](00-Syllabus/SYLLABUS.md) puis la section « Produire les supports » ci-dessous |
| **Étudiant** | [`99-Infra/INSTALLATION.md`](99-Infra/INSTALLATION.md) — à faire avant la séance 2 |

---

## Arborescence

```
BigData-2026/
├── 00-Syllabus/            Programme des 16 séances, compétences, évaluation
├── 01-Module1-Fondations/       86 slides · TD1 · TP1
├── 02-Module2-Stockage/         66 slides · TD2 · TP2, TP3
├── 03-Module3-Calcul/           57 slides · TD3 · TP4, TP5
├── 04-Module4-SparkSQL/         48 slides · TD4 · TP6, TP7
├── 05-Module5-Streaming/        38 slides ·     · TP8, TP9
├── 06-Module6-ML-Gouvernance/   57 slides · TD5 · TP10 (IF), TP11 (AN)
│   Chaque module contient : slides/ polycopie/ td/ tp/
│   Chaque TD et chaque TP existe en énoncé ET en corrigé enseignant.
├── 99-Infra/
│   ├── INSTALLATION.md     Guide étudiant
│   ├── docker/             Cluster complet en docker compose
│   ├── scripts/            Générateurs de données, script de validation
│   └── modeles/            Modèles ONNX du TP11 (à télécharger une fois)
└── _build/                 Scripts de génération des supports (Python)
```

---

## L'environnement de TP

Un cluster conteneurisé, identique pour tous, lancé en une commande.

```bash
cd 99-Infra/docker
docker compose up -d
```

| Service | Adresse | Identifiants |
|---|---|---|
| JupyterLab | http://localhost:8888 | jeton `bigdata` |
| NameNode HDFS | http://localhost:9870 | — |
| YARN ResourceManager | http://localhost:8088 | — |
| MinIO (S3) | http://localhost:9001 | `minioadmin` / `minioadmin` |
| Kafka | `localhost:29092` | — |

Composants : Hadoop 3.3.6 (HDFS + YARN, 2 DataNodes), Spark 3.5.3, Kafka 3.7 en KRaft,
MinIO, Iceberg 1.5, JupyterLab sur Python 3.11.

**Deux réglages sont volontairement non standard** et sont expliqués aux étudiants :
la taille de bloc est fixée à **32 Mio** (au lieu de 128) pour qu'un jeu de données
pédagogique produise plusieurs blocs observables, et la réplication à **2** (au lieu de 3)
puisque la maquette ne compte que deux DataNodes.

---

## Les jeux de données

Générateur déterministe à graine fixée : tous les étudiants d'une même filière obtiennent
le même fichier, donc les mêmes résultats numériques.

```bash
docker compose exec jupyter python \
  /home/tinku/cours/99-Infra/scripts/generate_datasets.py \
  --filiere if --sortie /home/tinku/work/data --evenements 2000000
```

| Filière | Table de faits | Référentiels |
|---|---|---|
| `if` — Ingénierie Financière | `if_transactions.jsonl` (~500 Mio pour 2 M lignes) | comptes, marchands |
| `an` — Art Numérique | `an_evenements.jsonl` (~500 Mio pour 2 M lignes) | utilisateurs, œuvres |

Les données contiennent **volontairement** des défauts : distributions en loi de puissance
(qui provoqueront le *skew* du module 4), valeurs manquantes (0,4 %), doublons exacts (0,1 %),
champs vides (0,2 %), et une classe minoritaire (fraudes à 0,17 %). Ce ne sont pas des bugs :
ils servent aux TP de qualité de données et d'optimisation.

### Le TP différencié du module 6

Le module 6 tient en 8 h. La séance 14 fusionne l'apprentissage distribué et la vision en
**2 h de CM tronc commun**, suivies de **2 h de TP différencié** :

| Filière | TP | Sujet |
|---|---|---|
| Ingénierie Financière | **TP10** | Pipeline de détection de fraude, fuite de données, seuil et coût métier |
| Art Numérique | **TP11** | Vision distribuée : stockage d'images, chargement du modèle, classification et détection |

**Les deux corrigés sont distribués aux deux filières.** Le TP non traité en séance reste au
programme de l'examen **pour ses concepts**, pas pour sa mise en œuvre — c'est écrit en tête
de chaque énoncé.

Le support de 57 slides est prévu pour 2 h de CM : **six slides sont marquées « SURVOL »**
dans les commentaires du présentateur, à passer en moins d'une minute, leur contenu figurant
intégralement dans le polycopié. La feuille de route minutée, et la liste de ce qu'il ne faut
pas sacrifier, se trouvent dans les commentaires de la **deuxième slide** du support.

### Les images du TP11

```bash
docker compose exec jupyter python   /home/tinku/cours/99-Infra/scripts/generate_images.py   --sortie /home/tinku/work/images --nombre 4000
```

Images de synthèse — formes géométriques colorées de 224×224 — accompagnées d'une **vérité
terrain** en JSON Lines : classe dominante et boîte englobante de chaque objet. Aucun
téléchargement, aucune question de licence, et la position exacte de chaque forme est connue,
ce qui permet de vérifier une chaîne de détection.

Le choix du synthétique est **délibéré** : un modèle pré-entraîné sur ImageNet appliqué à ces
images produit des prédictions confiantes et absurdes. Le TP11 en fait un exercice — c'est le
décalage de distribution, observé en conditions réelles.

### Les modèles du TP11

À lancer **une seule fois**, sur une connexion confortable — environ 45 Mio au total :

```bash
python 99-Infra/scripts/telecharger_modeles.py --sortie 99-Infra/modeles
```

| Modèle | Taille | Rôle |
|---|---|---|
| `mobilenetv2-12.onnx` | ~14 Mio | Classification, 1 000 classes ImageNet |
| `ssd_mobilenet_v1_10.onnx` | ~28 Mio | Détection d'objets, 90 classes COCO |

> **Le TP11 fonctionne sans ces modèles.** En leur absence il bascule en *mode substitution* :
> un modèle factice simule le coût d'un chargement (0,6 s) et d'une inférence (25 ms/image).
> Les exercices sur la **distribution** — empaquetage, amortissement du chargement, taille des
> lots, dimensionnement — restent entièrement valables et mesurables. Seules les prédictions
> perdent leur sens.

---

## Produire les supports

Les PPTX et DOCX ne sont pas édités à la main : ils sont **générés** par des scripts Python,
de sorte que la charte graphique reste homogène sur les six modules et qu'une correction de
fond se propage sans reprise manuelle.

```bash
cd _build
# Tout regenerer, dans l'ordre
for f in gen_m1_slides_shift gen_m2_slides gen_m3_slides gen_m4_slides gen_m5_slides gen_m6_slides; do
  uv run --python 3.12 --with python-pptx --no-project python $f.py
done
for f in gen_module1_poly gen_module1_td gen_m2_poly gen_m2_td gen_m3_poly gen_m3_td          gen_m4_poly gen_m4_td gen_m5_poly gen_m6_poly gen_m6_td; do
  uv run --python 3.12 --with python-docx --no-project python $f.py
done
for f in gen_module1_tp gen_m2_tp gen_m3_tp gen_m4_tp gen_m5_tp gen_m6_tp gen_m6_tp11; do
  uv run --python 3.12 --no-project python $f.py
done
```

> Ajoutez `--offline` après `uv run` pour travailler sans réseau, sur le cache local.

> **Fermez le fichier dans PowerPoint ou Word avant de régénérer.** Pour les slides, le script
> se rabat automatiquement sur un fichier `…-NOUVEAU.pptx` et vous le signale ; pour les
> documents Word, l'écriture échoue avec `PermissionError`.

| Fichier | Rôle |
|---|---|
| `_build/template-shift.pptx` | **Gabarit** : la présentation *Introduction Au Big Data* de l'enseignant. Masque, dispositions, couleurs et polices en sont hérités |
| `_build/theme_shift.py` | Briques de slides posées sur ce gabarit (titre, section, puces, deux colonnes, affirmation, chiffre-clé, encadré, tableau, code, schéma, couches) |
| `_build/docxtheme.py` | Mise en page des polycopiés (page de garde, encadrés, tableaux, code) |
| `_build/gen_m1_*.py`, `gen_module1_*.py` | Contenu du module 1 |
| `_build/render.ps1` | Export des slides en PNG via PowerPoint, pour vérifier le rendu réel |

Pour créer le module 2, dupliquez `gen_m1_slides_shift.py` : le moteur est réutilisable tel quel.

### La charte « shift »

Tout vient du gabarit, rien n'est recréé à la main :

| | |
|---|---|
| Format | 10 × 5,625 po (16:9) |
| Fond | carton blanc posé sur un fond bleu-vert `#233A44`, triangles décoratifs |
| Titres | Nunito 28 pt, cuivre `#AF7B51` |
| Corps | Calibri 13 pt (niveau 1) / 11 pt (niveaux suivants), `#233A44` |
| Puces | ● ○ ■ |
| Accents | teal `#00796B`, terracotta `#D9563F`, or `#C4A15A`, indigo `#3D4594` |

La zone de contenu utile n'est que de 8,21 × 2,68 po. Les slides doivent donc rester
**légères — 8 à 10 lignes au maximum** — quitte à en produire davantage. C'est pourquoi le
module 1 compte 86 slides et non 51.

### Règle de rédaction des slides

**Aucune consigne destinée à l'enseignant n'apparaît sur une slide.** Les étudiants lisent les
slides : ils n'ont pas à y trouver « faire réagir la salle » ou « ne pas donner la réponse ».
Toute indication d'animation va dans le paramètre `notes=`, c'est-à-dire dans les commentaires
du présentateur — visibles en mode Présentateur et à l'impression « Pages de commentaires ».

Les slides ne portent que du contenu de cours, et les consignes qui s'adressent réellement aux
étudiants : lectures à faire, travail à rendre, installation à réaliser.

### Vérifier le rendu

```bash
powershell -File _build/render.ps1 -Src <fichier.pptx> -Out <dossier_images>
```

Exporte chaque slide en PNG en pilotant PowerPoint. Si PowerPoint est déjà ouvert, l'instance
existante est réutilisée et n'est pas fermée : vos documents ne sont pas touchés.

**Après ouverture d'un polycopié dans Word :** clic droit sur la table des matières →
*Mettre à jour les champs* (ou F9) pour la générer.

---

## Ce qui a changé par rapport à la version précédente

| | Avant | Maintenant |
|---|---|---|
| Environnement de TP | Sandbox Hortonworks HDP | Docker Compose |
| Spark | 1.x / 2.x, chemins `maria_dev` en dur | 3.5.3, chemins paramétrés |
| Streaming | DStreams + Flume (`FlumeUtils` supprimé de Spark 3) | Kafka + Structured Streaming |
| MapReduce | `mrjob` | Concept enseigné, Spark en pratique |
| Stockage | HDFS seul | HDFS + stockage objet + Iceberg |
| Formats | CSV / texte | Parquet, comparaison mesurée |
| Technologies mortes | Pig, Storm, Tez, Oozie, Flume, Mesos, Drill enseignés | Traités en perspective historique |
| Python | Code Python 2 (`.decode('ascii')`) | Python 3.11 |
| TP | Scripts de démonstration sans consigne | Objectifs, barème publié, corrigé séparé |

---

## État d'avancement

**Contenu pédagogique — terminé.** 46 fichiers livrables.

| Module | Slides | Notes du présentateur | Polycopié | TD | TP |
|---|---|---|---|---|---|
| M1 — Fondations | 86 | 23 000 car. | ✅ | TD1 + corrigé | TP1 + corrigé |
| M2 — Stockage | 66 | 26 000 car. | ✅ | TD2 + corrigé | TP2, TP3 + corrigés |
| M3 — Calcul | 57 | 21 000 car. | ✅ | TD3 + corrigé | TP4, TP5 + corrigés |
| M4 — Spark SQL | 48 | 16 000 car. | ✅ | TD4 + corrigé | TP6, TP7 + corrigés |
| M5 — Streaming | 38 | 14 000 car. | ✅ | — | TP8, TP9 + corrigés |
| M6 — ML et gouvernance | 57 | 25 000 car. | ✅ | TD5 + corrigé | TP10 (IF), TP11 (AN) + corrigés |
| **Total** | **352** | **127 000 car.** | **6** | **5 × 2** | **11 × 2** |

Contrôles automatiques passés sur les six supports : aucun débordement de la zone de contenu,
aucun titre trop long, aucun balisage non interprété, **aucune consigne destinée à l'enseignant
visible sur une slide**.

### Reste à faire

- [ ] **Valider le cluster Docker** — voir ci-dessous
- [ ] Sujet de projet et grille de soutenance
- [ ] Annales d'examen écrit

---

## Validation de l'infrastructure — à faire

Le cluster n'a **pas encore été validé de bout en bout**. Un premier essai a permis de corriger
un bug réel (le NameNode plantait sur un `chmod` d'un volume monté en lecture seule) et de
restructurer le Dockerfile pour supprimer 1,1 Gio de téléchargements, mais la validation
complète n'est pas allée à son terme.

Un script rejoue toute la séquence :

```bash
bash 99-Infra/scripts/valider_cluster.sh
```

Il enchaîne : construction de l'image, démarrage du cluster, rapport HDFS, versions des outils,
commandes du TP1, génération et dépôt d'un jeu de données, lecture PySpark depuis HDFS, table
Iceberg sur MinIO, et écriture dans les quatre formats du TP2.

**Ce qui est déjà vérifié :** le Dockerfile multi-étages fonctionne, `SPARK_HOME` est bien
fourni par le paquet `pyspark`, MinIO et Kafka démarrent correctement.

**Ce qui reste à vérifier :** HDFS, PySpark sur HDFS, Iceberg sur MinIO, et les formats Avro
et Parquet.
