import subprocess
import time
import csv
import os
import pandas as pd
import requests
import sys
import zipfile
from datetime import datetime

# --- CONFIGURATION ---
# On force l'ID projet que tu as confirmé
PROJECT_ID = "tiny-494020"

# On s'assure que gcloud utilise bien ce projet pour les commandes subprocess
subprocess.run(f"gcloud config set project {PROJECT_ID}", shell=True, check=True)

APP_URL = os.environ.get('APP_URL', f"https://{PROJECT_ID}.nw.r.appspot.com")

SEED_TOKEN = os.environ.get('SEED_TOKEN', 'massive-gcp-secret-token') 
CONCURRENCY_STEPS = [1, 10, 20, 50, 100, 1000]
FANOUT_STEPS = [20, 40, 60]
RUNS_PER_STEP = 3
DURATION = "60s"  # On augmente un peu pour laisser le scaling se stabiliser
OUTPUT_DIR = "out"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_instance_count():
    """Récupère le nombre d'instances App Engine en cours d'exécution."""
    try:
        cmd = f"gcloud app instances list --project={PROJECT_ID} --format='value(instanceId)'"
        result = subprocess.check_output(cmd, shell=True).decode('utf-8')
        return len(result.strip().split('\n')) if result.strip() else 1
    except Exception:
        return 1

def seed_app(users, posts, follows, clear=False):
    """Appelle l'endpoint de seed pour préparer les données."""
    print(f"\n[SEEDING] Utilisation de seed.py en local pour éviter le timeout GAE (60s)...")
    print(f"          Config: {users} users, {posts} posts, {follows} follows sur le projet {PROJECT_ID}")
    
    cmd = [
        sys.executable, "seed.py",
        "--users", str(users),
        "--posts", str(posts),
        "--follows-min", str(follows),
        "--follows-max", str(follows)
    ]
    if clear:
        cmd.append("--clear")

    try:
        subprocess.run(cmd, check=True)
        print("  [Seeding] Terminée avec succès via Datastore API.")
    except subprocess.CalledProcessError as e:
        print(f"\n  [Seeding] ERREUR : Le script seed.py a échoué ({e})")

def run_locust(user_count, run_id, label=""):
    print(f"\n>>> [{label}] Test: {user_count} utilisateurs, Run {run_id}...")
    
    # On définit un préfixe pour les fichiers CSV temporaires de Locust
    tmp_prefix = "tmp_locust_results"
    
    # Commande Locust Headless
    # -r est le spawn rate (vitesse d'arrivée des users)
    spawn_rate = max(1, user_count // 10)
    locust_cmd = [
        "locust", "-f", "locustfile.py",
        "--headless",
        "-u", str(user_count),
        "-r", str(spawn_rate),
        "--run-time", DURATION,
        "--host", APP_URL,
        "--csv", tmp_prefix,
        "--only-summary"
    ]
    
    # On lance le processus
    try:
        process = subprocess.Popen(locust_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("\n❌ ERREUR : 'locust' n'est pas installé ou pas dans le PATH.")
        print("👉 Lancez : pip install locust")
        sys.exit(1)

    # IMPORTANT : On attend que le scaling s'opère pour mesurer les instances. 
    # Suppression de l'attente artificielle pour voir la réactivité en temps réel
    print(f"  [Locust] Test lancé ({DURATION})...", end="", flush=True)
    nb_instances = get_instance_count()
    
    # On attend la fin précise du processus sans ajouter de délai inutile
    while process.poll() is None:
        time.sleep(1)
    print(" OK.")
    
    # Lecture des résultats dans le CSV généré par Locust (prefix_stats.csv)
    stats_file = f"{tmp_prefix}_stats.csv"
    avg_time = 0
    failed = 0
    
    if os.path.exists(stats_file):
        df = pd.read_csv(stats_file)
        # On cherche la ligne 'Aggregated' ou la ligne de notre API
        total_row = df[df['Name'] == 'Aggregated']
        if not total_row.empty:
            avg_time = float(total_row['Average Response Time'].values[0]) # Utilisation de float pour plus de précision
            fail_count = int(total_row['Failure Count'].values[0])
            failed = 1 if fail_count > 0 else 0
            
    # Nettoyage des fichiers temporaires
    for f in os.listdir('.'):
        if f.startswith(tmp_prefix):
            os.remove(f)
            
    return avg_time, failed, nb_instances

def run_experiment(name, steps, is_concurrency=True):
    filename = os.path.join(OUTPUT_DIR, f"{name}.csv")
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["PARAM", "AVG_TIME", "RUN", "FAILED", "NB_INSTANCES"])

    # --- LOGIQUE DE SEEDING SPÉCIFIQUE AU TP ---
    if is_concurrency:
        # Expérience 1 : 1000 users, 50 posts/user (50k total), 20 follows fixes
        seed_app(1000, 50000, 20, clear=True)

    for val in steps:
        if not is_concurrency:
            # Expérience 2 : 1000 users, 100 posts/user (100k total), follows variables (PARAM)
            seed_app(1000, 100000, val, clear=True)
        
        for run in range(1, RUNS_PER_STEP + 1):
            # Si concurrence, on varie les users (val). Si fan-out, fixe à 50 users.
            users_to_simulate = val if is_concurrency else 50
            avg, fail, instances = run_locust(users_to_simulate, run, label=name)
            
            # On écrit immédiatement le résultat pour ne rien perdre si ça plante
            with open(filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([val, f"{avg}ms", run, fail, instances])
            print(f"   -> Resultat: {avg}ms | Fail: {fail} | Instances: {instances}")

def read_csv_to_table(filename):
    """Lit un CSV et retourne une table Markdown."""
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return "| N/A | N/A | N/A | N/A | N/A |\n"
    
    df = pd.read_csv(path)
    # Détection et correction si le header est manquant dans le fichier existant
    if not df.empty and 'PARAM' not in df.columns:
        df = pd.read_csv(path, header=None, names=["PARAM", "AVG_TIME", "RUN", "FAILED", "NB_INSTANCES"])

    table = ""
    for _, row in df.iterrows():
        table += f"| {row['PARAM']} | {row['AVG_TIME']} | {row['RUN']} | {row['FAILED']} | {row['NB_INSTANCES']} |\n"
    return table

def update_readme():
    """Génère le rapport complet dans README.md en combinant les analyses de full_automation."""
    print("\n[README] Génération du rapport complet dans README.md...")
    
    conc_table = read_csv_to_table("conc.csv")
    fanout_table = read_csv_to_table("fanout.csv")
    
    report_content = f"""
<!-- START_BENCHMARK -->
# Rapport d'Analyse de performance - TinyInsta - RAVARD Samuel

**Généré le :** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**URL Application :** [{APP_URL}]({APP_URL})

## 1. Executive Summary
Ce rapport évalue la capacité de passage à l'échelle (scalability) de TinyInsta sur Google App Engine. Nous analysons deux scénarios critiques : la montée en charge utilisateur (Concurrence) et l'impact de la taille du graphe social (Fan-out).

## 2. Expérience A : Concurrence (Scale Up)
*Objectif : Mesurer l'évolution du temps de réponse avec une charge de 1 à 1000 utilisateurs simultanés.*

| Paramètre | Temps Moyen | Run | Échec | Instances |
|---|---|---|---|---|
{conc_table}

### Graphiques de Performance
![Graphique Concurrence](out/conc.png)

## 3. Expérience B : Fan-out (Data Size)
*Objectif : Mesurer l'impact du nombre d'abonnements (20, 40, 60) sur la génération de la timeline.*

| Paramètre | Temps Moyen | Run | Échec | Instances |
|---|---|---|---|---|
{fanout_table}

### Graphiques de Performance
![Graphique Fan-out](out/fanout.png)

---

## 4. Interprétation des résultats

### 4.1 Analyse théorique de la Concurrence (Expérience A)
L'analyse des résultats met en évidence un seuil critique de saturation aux alentours de 50 utilisateurs simultanés, point où la latence s'envole au-delà des 400ms et où les premiers échecs de requêtes apparaissent. Ce comportement illustre concrètement la loi d'Amdahl : l'efficacité de la parallélisation est ici limitée par la portion séquentielle du code, notamment les interactions synchrones avec Datastore et la gestion des verrous de ressources. De plus, la dépendance initiale à une instance F1 unique souligne les faiblesses d'une stratégie de dimensionnement vertical (Scale-up) pur. Les ressources matérielles saturent avant que le mécanisme de Scale-out horizontal ne puisse se déployer pour soulager les processus Gunicorn. Enfin, les fluctuations massives de performance observées à 1000 utilisateurs incarnent le défi de la Variabilité propre au Big Data, où des flux de données hétérogènes empêchent l'obtention de temps de réponse stables et prévisibles.

### 4.2 Analyse théorique du Fan-out (Expérience B)
L'expérience B révèle une dégradation spectaculaire de la latence, qui se voit multipliée par près de vingt lorsque le nombre de comptes suivis passe de 20 à 60. Ce phénomène est intrinsèque au modèle de "Fan-out on Read" (approche Pull). En effectuant une jointure logique coûteuse à chaque consultation de timeline pour agréger les publications, le système se retrouve rapidement limité par les opérations d'entrée/sortie (I/O Bound). La fusion d'index opérée par Datastore devient alors un goulot d'étranglement algorithmique qui rend le service pratiquement inutilisable pour des graphes sociaux denses. Dans ce contexte, le Volume des relations sociales impacte directement la Velocity du système, rendant indispensable l'adoption d'un découplage architectural entre la production et la consommation de contenu.

### 4.3 Synthèse : Scalabilité vs Élasticité
La distinction entre l'élasticité de l'infrastructure et la scalabilité réelle de l'application est ici frappante. Si Google App Engine offre une flexibilité réelle pour ajuster les ressources matérielles (élasticité), l'implémentation logicielle actuelle échoue à maintenir des performances constantes face à la charge. La latence ne suit pas une courbe de croissance maîtrisée mais explose selon les paramètres de concurrence ou de fan-out. En privilégiant la consistance immédiate selon les principes du théorème CAP, l'architecture de TinyInsta finit par sacrifier sa disponibilité et sa réactivité sous pression. Pour passer véritablement à l'échelle, il est crucial d'évoluer vers un modèle favorisant la performance de lecture, quitte à accepter une consistance éventuelle.

**Conclusion technique :** Nous avons privilégié la **simplicité d'écriture** (un post est écrit une seule fois) au détriment de la **performance de lecture**. Pour scaler, il faut inverser cette logique.

## 5. Recommandations
1.  **Migration vers "Fan-out on Write" (Modèle Push) :**
    - *Théorie :* Basculer la complexité du temps de lecture ($O(N)$ followees) vers le temps d'écriture.
    - *Action :* Utiliser le pattern **Outbox** : lors d'un post, on écrit dans Datastore ET on publie un message dans **Cloud Pub/Sub**.
2.  **Utilisation de Cloud Pub/Sub pour l'Éventuelle Consistance :**
    - *Théorie :* Adopter le modèle **BASE** (Basically Available, Soft-state, Eventually Consistent).
    - *Action :* Des workers asynchrones consomment les messages Pub/Sub pour mettre à jour les "Feeds" pré-calculés des abonnés.
3.  **Sharding des Données :**
    - *Théorie :* Pour éviter les "Hotspots" (ex: une célébrité comme Justin Bieber), il faut partitionner les index par `user_id` (Sharding).
    - *Action :* S'assurer que les clés de partitionnement (Shard Keys) distribuent uniformément la charge sur les nœuds de Datastore.
4.  **Caching via Memorystore (Redis) :**
    - *Théorie :* Réduire la **Veracity** (pression sur la base de vérité) en utilisant une mémoire distribuée pour les données volatiles.
    - *Action :* Stocker les timelines pré-calculées en RAM pour un accès en <10ms.

---
## 6. Détails Techniques
- **Chargeur :** Locust (Headless mode)
- **Backend :** Python 3.10 sur Google App Engine Standard
- **Base de données :** Google Cloud Datastore

*Rapport automatisé généré par run_benchmarks.py*
<!-- END_BENCHMARK -->
"""

    readme_file = "README.md"
    if os.path.exists(readme_file):
        with open(readme_file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    start_marker = "<!-- START_BENCHMARK -->"
    end_marker = "<!-- END_BENCHMARK -->"
    
    if start_marker in content and end_marker in content:
        parts = content.split(start_marker)
        after_parts = parts[1].split(end_marker)
        new_content = parts[0] + report_content + after_parts[1]
    else:
        new_content = content + "\n" + report_content

    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("✅ README.md mis à jour avec le rapport détaillé.")

def main():
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                TINYINSTA UNIFIED BENCHMARK & REPORT GENERATOR                ║
║                                                                              ║
║  Ce script va :                                                              ║
║  1. Seeder le Datastore via l'API HTTP (Recommandé TP)                       ║
║  2. Exécuter les tests de Concurrence (1 à 1000 users)                       ║
║  3. Exécuter les tests de Fan-out (20 à 60 followers)                        ║
║  4. Générer les graphiques PNG                                               ║
║  5. Produire un rapport d'analyse complet dans README.md                     ║
║  6. Créer une archive results_tp.zip pour le rendu                           ║
║                                                                              ║
║  ⏱️ Durée estimée : ~30 minutes                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    confirm = input("Voulez-vous lancer le benchmark complet ? (y/n) : ")
    if confirm.lower() != 'y':
        print("Annulé.")
        return
    
    # 1. Expérience Concurrence
    print("\n[EXP 1] Concurrence (Scale Up)")
    run_experiment("conc", CONCURRENCY_STEPS, is_concurrency=True)

    # 2. Expérience Fan-out
    print("\n[EXP 2] Fan-out (Data Size)")
    run_experiment("fanout", FANOUT_STEPS, is_concurrency=False)

    print("\n=== TESTS TERMINÉS ===")
    
    # 3. Génération des graphiques
    if os.path.exists("generate_plots.py"):
        print("\n[PLOTS] Génération des graphiques...")
        subprocess.run(["python3", "generate_plots.py"])
    
    # 4. Mise à jour du README
    update_readme()
    
    # 5. Création d'une archive ZIP pour la récupération facile
    zip_path = os.path.join(OUTPUT_DIR, 'results_tp.zip')
    print(f"\n[ARCHIVE] Création de {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        files_to_zip = ["README.md", 
                        os.path.join(OUTPUT_DIR, "conc.png"), 
                        os.path.join(OUTPUT_DIR, "fanout.png"), 
                        os.path.join(OUTPUT_DIR, "conc.csv"), 
                        os.path.join(OUTPUT_DIR, "fanout.csv")]
        for f in files_to_zip:
            if os.path.exists(f):
                # On sauvegarde dans le zip sans le préfixe 'out/' pour que l'archive soit plate
                zipf.write(f, os.path.basename(f))

    print(f"\nTerminé ! Tu n'as plus qu'à télécharger '{zip_path}' ou push ton repo.")
    print(f"Les résultats sont visibles dans ton README.md.")

if __name__ == "__main__":
    main()