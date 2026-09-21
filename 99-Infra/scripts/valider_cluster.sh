#!/usr/bin/env bash
# Validation de bout en bout du cluster pedagogique.
# Reconstruit l'image jupyter avec le Dockerfile courant, demarre le cluster,
# puis rejoue les commandes cles du TP1.
set -u
cd "D:/TINKU/Enseignant/2021-2023/cours/Hadoop/BigData-2026/99-Infra/docker" || exit 1

echo "=============================================================="
echo "  1. RECONSTRUCTION DE L'IMAGE JUPYTER"
echo "=============================================================="
docker compose build jupyter
echo "code de sortie du build : $?"
docker image inspect bigdata-m2/jupyter:1.0 --format 'user={{.Config.User}} workdir={{.Config.WorkingDir}}' 2>&1

echo
echo "=============================================================="
echo "  2. DEMARRAGE DU CLUSTER"
echo "=============================================================="
docker compose up -d
sleep 60
docker compose ps

echo
echo "=============================================================="
echo "  3. VERIFICATION HDFS"
echo "=============================================================="
docker compose exec -T jupyter hdfs dfsadmin -report 2>&1 | head -20

echo
echo "--- version des outils ---"
docker compose exec -T jupyter bash -lc 'java -version 2>&1 | head -1; hdfs version | head -1; python -c "import pyspark; print(\"pyspark\", pyspark.__version__)"' 2>&1

echo
echo "--- SPARK_HOME et jars critiques ---"
docker compose exec -T jupyter bash -lc 'echo SPARK_HOME=$SPARK_HOME; ls $SPARK_HOME/jars | grep -E "iceberg|hadoop-aws|kafka|avro" | head' 2>&1

echo
echo "=============================================================="
echo "  4. COMMANDES DU TP1"
echo "=============================================================="
docker compose exec -T jupyter bash -lc '
set -x
hdfs dfs -mkdir -p /user/etudiant/brut
echo "Premier fichier depose sur HDFS." > /tmp/test.txt
hdfs dfs -put -f /tmp/test.txt /user/etudiant/brut/
hdfs dfs -cat /user/etudiant/brut/test.txt
hdfs dfs -stat "nom=%n taille=%b bloc=%o replication=%r" /user/etudiant/brut/test.txt
hdfs fsck /user/etudiant/brut/test.txt -files -blocks
' 2>&1 | tail -30

echo
echo "=============================================================="
echo "  5. GENERATION DES DONNEES + DEPOT + BLOCS"
echo "=============================================================="
docker compose exec -T jupyter bash -lc '
python /home/tinku/cours/99-Infra/scripts/generate_datasets.py \
   --filiere if --sortie /home/tinku/work/data --evenements 300000 2>&1 | tail -8
ls -lh /home/tinku/work/data/if_transactions.jsonl
hdfs dfs -put -f /home/tinku/work/data/if_transactions.jsonl /user/etudiant/brut/
hdfs fsck /user/etudiant/brut/if_transactions.jsonl | tail -20
' 2>&1 | tail -35

echo
echo "=============================================================="
echo "  6. PYSPARK LIT DEPUIS HDFS"
echo "=============================================================="
docker compose exec -T jupyter bash -lc '
cat > /tmp/verif.py <<PYEOF
from pyspark.sql import SparkSession
spark = (SparkSession.builder.appName("verif").master("local[2]")
         .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:8020")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
df = spark.read.json("hdfs://namenode:8020/user/etudiant/brut/if_transactions.jsonl")
print("LIGNES :", df.count())
print("PARTITIONS :", df.rdd.getNumPartitions())
df.select("id_transaction","montant","pays_transaction").show(3, truncate=False)
spark.stop()
PYEOF
python /tmp/verif.py' 2>&1 | grep -vE "^(WARN|[0-9]{2}/)" | tail -25

echo
echo "=============================================================="
echo "  7. ICEBERG SUR MINIO"
echo "=============================================================="
docker compose exec -T jupyter bash -lc '
cat > /tmp/ice.py <<PYEOF
from pyspark.sql import SparkSession
spark = (SparkSession.builder.appName("ice").master("local[2]")
    .config("spark.sql.extensions","org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.lakehouse","org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.lakehouse.type","hadoop")
    .config("spark.sql.catalog.lakehouse.warehouse","s3a://lakehouse/verif")
    .config("spark.hadoop.fs.s3a.endpoint","http://minio:9000")
    .config("spark.hadoop.fs.s3a.access.key","minioadmin")
    .config("spark.hadoop.fs.s3a.secret.key","minioadmin")
    .config("spark.hadoop.fs.s3a.path.style.access","true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled","false")
    .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.t")
spark.sql("DROP TABLE IF EXISTS lakehouse.t.essai")
spark.sql("CREATE TABLE lakehouse.t.essai (id INT, ts TIMESTAMP, m DOUBLE) USING iceberg PARTITIONED BY (days(ts))")
spark.sql("INSERT INTO lakehouse.t.essai VALUES (1, TIMESTAMP \\"2025-06-14 10:00:00\\", 42.5), (2, TIMESTAMP \\"2025-06-15 11:00:00\\", 17.0)")
print("LIGNES :", spark.table("lakehouse.t.essai").count())
spark.sql("ALTER TABLE lakehouse.t.essai RENAME COLUMN m TO montant_eur")
spark.sql("SELECT * FROM lakehouse.t.essai").show()
spark.sql("SELECT snapshot_id, operation FROM lakehouse.t.essai.snapshots").show(truncate=False)
print("ICEBERG OK")
spark.stop()
PYEOF
python /tmp/ice.py' 2>&1 | grep -vE "^(WARN|[0-9]{2}/)" | tail -30

echo
echo "=============================================================="
echo "  8. AVRO ET PARQUET (dependances du TP2)"
echo "=============================================================="
docker compose exec -T jupyter bash -lc '
cat > /tmp/fmt.py <<PYEOF
from pyspark.sql import SparkSession
spark = (SparkSession.builder.appName("fmt").master("local[2]")
         .config("spark.hadoop.fs.defaultFS","hdfs://namenode:8020").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
df = spark.range(1000).toDF("n")
for f in ["parquet","avro","json","csv"]:
    df.write.mode("overwrite").format(f).save(f"hdfs:///user/etudiant/fmt_{f}")
    print(f, "->", spark.read.format(f).load(f"hdfs:///user/etudiant/fmt_{f}").count())
print("FORMATS OK")
spark.stop()
PYEOF
python /tmp/fmt.py' 2>&1 | grep -vE "^(WARN|[0-9]{2}/)" | tail -15

echo
echo "=============================================================="
echo "  VALIDATION TERMINEE"
echo "=============================================================="
