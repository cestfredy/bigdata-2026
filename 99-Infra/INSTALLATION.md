# Mise en place de l'environnement de TP

> À faire **avant la séance 2**. Comptez 30 à 45 minutes, dont l'essentiel en téléchargement.
> Si vous bloquez, ouvrez un ticket sur l'espace de cours en joignant la sortie de `docker compose logs`.

---

## 1. Prérequis matériels

| | Minimum | Confortable |
|---|---|---|
| RAM | 8 Go | 16 Go |
| Disque libre | 20 Go | 40 Go |
| Processeur | 4 cœurs | 8 cœurs |

Sur 8 Go de RAM, allouez au moins 6 Go à Docker et fermez votre navigateur pendant les TP lourds (modules 4 et 5).

## 2. Installation de Docker

- **Windows** — [Docker Desktop](https://www.docker.com/products/docker-desktop/) avec le moteur WSL 2.
  Vérifiez dans *Settings → Resources* que la mémoire allouée est d'au moins 6 Go.
- **macOS** — Docker Desktop (choisissez la variante Apple Silicon ou Intel selon votre machine).
- **Linux** — `docker` et le greffon `docker compose` depuis les dépôts de votre distribution.

Vérification :

```bash
docker --version && docker compose version
```

## 3. Première construction du cluster

```bash
cd BigData-2026/99-Infra/docker
docker compose build
docker compose up -d
```

La première commande télécharge les images du cluster et construit le poste de travail :
comptez 5 à 10 minutes **la première fois seulement**. Les fois suivantes, `docker compose up -d`
démarre en moins d'une minute.

> Si votre connexion coupe pendant l'opération, relancez simplement les deux commandes :
> Docker reprend là où il s'était arrêté, et les téléchargements restants réessaient d'eux-mêmes.

## 4. Vérification

```bash
docker compose ps
```

Sept services doivent être en état `running` (`minio-init` apparaît en `exited (0)` : c'est normal,
il a fini de créer les buckets et s'est arrêté).

Ouvrez ensuite ces adresses :

| Service | Adresse | Ce que vous devez voir |
|---|---|---|
| JupyterLab | http://localhost:8888 (jeton `bigdata`) | l'arborescence du cours |
| NameNode HDFS | http://localhost:9870 | onglet *Datanodes* avec **2 nœuds vivants** |
| YARN | http://localhost:8088 | *Active Nodes : 1* |
| MinIO | http://localhost:9001 (`minioadmin` / `minioadmin`) | les buckets `lakehouse`, `raw`, `warehouse` |

Test en ligne de commande :

```bash
docker compose exec jupyter hdfs dfs -mkdir -p /user/etudiant
docker compose exec jupyter hdfs dfs -ls /user
```

## 5. Avant le module 6 — les modèles du TP11

Le TP11 utilise deux modèles pré-entraînés au format ONNX, environ 45 Mio au total.
À récupérer **une seule fois**, sur une connexion confortable :

```bash
python 99-Infra/scripts/telecharger_modeles.py --sortie 99-Infra/modeles
```

Si le téléchargement échoue, le TP11 bascule automatiquement en *mode substitution* : les
exercices sur la distribution restent faisables, seules les prédictions perdent leur sens.
Le notebook le détecte et vous l'indique en section 0.

## 6. Commandes du quotidien

```bash
docker compose up -d          # démarrer
docker compose stop           # arrêter en conservant les données
docker compose logs -f kafka  # suivre les journaux d'un service
docker compose exec jupyter bash   # obtenir un shell dans le poste de travail
docker compose down -v        # TOUT effacer et repartir de zéro
```

---

## 7. Pannes courantes

**`port is already allocated`**
Un service occupe déjà le port (souvent 8888 par un Jupyter local, ou 9000 par un autre outil).
Arrêtez-le, ou changez le port de gauche dans `docker-compose.yml` — par exemple `"8889:8888"`.

**Le NameNode affiche 0 DataNode**
Les DataNodes ont démarré avant que le NameNode soit prêt. Relancez-les :
`docker compose restart datanode1 datanode2`, puis rechargez la page après une trentaine de secondes.

**`SafeModeException` au démarrage**
HDFS attend qu'un pourcentage de blocs soit signalé avant d'accepter les écritures. Patientez une
minute. Si l'état persiste : `docker compose exec namenode hdfs dfsadmin -safemode leave`.

**Le conteneur `jupyter` redémarre en boucle**
Presque toujours un manque de mémoire. Augmentez l'allocation de Docker Desktop, ou réduisez
`spark.driver.memory` dans `docker/spark-defaults.conf`.

**Job Spark bloqué en `ACCEPTED` sur YARN**
Le cluster n'a plus de ressources : une application précédente tourne toujours. Listez-les avec
`docker compose exec resourcemanager yarn application -list` puis tuez-les avec
`yarn application -kill <applicationId>`.

**Windows : erreurs de fins de ligne dans les scripts**
Configurez Git avant de cloner : `git config --global core.autocrlf input`.
