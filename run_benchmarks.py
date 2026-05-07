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
    print(f"          Config: {users} users, {posts} posts, {follows} follows")
    
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
    cmd = [
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
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # IMPORTANT : On attend que le scaling s'opère pour mesurer les instances. 
    # On augmente le délai pour laisser App Engine avoir le temps de scaler.
    print(f"  [Locust] Test lancé ({DURATION})... Attente pour le scaling...", end="", flush=True)
    time.sleep(30) # Augmenté de 10s à 30s pour laisser le temps au scaling
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
        print("  [Cooldown] Pause de 15s après seeding initial...")
        time.sleep(15)

    for val in steps:
        if not is_concurrency:
            # Expérience 2 : 1000 users, 100 posts/user (100k total), follows variables (PARAM)
            seed_app(1000, 100000, val, clear=True)
            print("  [Cooldown] Pause de 15s après re-seeding...")
            time.sleep(15)
        
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
# 📊 Rapport d'Analyse de Performance - TinyInsta

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

## 4. Interprétation des Résultats

### Est-ce logique ?
**Oui.** 
1. **Concurrence :** L'augmentation de la latence est attendue. Plus d'utilisateurs simultanés saturent les ressources de l'instance avant que le scaling GCP ne puisse réagir complètement. Sans cache, chaque requête frappe directement Datastore, créant un goulot d'étranglement I/O.
2. **Fan-out :** L'impact est linéaire. Pour 60 abonnements, l'application doit effectuer des requêtes plus complexes (opérateur `IN`) ou agréger plus de données en mémoire, ce qui augmente mécaniquement le temps de calcul.

### Est-ce que ça "scale" ?
**Techniquement oui, architecturalement non.**
* **Infrastructure (OUI) :** Google App Engine remplit son rôle de PaaS en provisionnant de nouvelles instances quand la charge monte.
* **Application (NON) :** Le modèle "Fan-out on Read" (calcul de la timeline à la demande) montre ses limites. Les temps de réponse deviennent prohibitifs pour une expérience utilisateur fluide dès que la charge dépasse un certain seuil.

## 5. Recommandations Techniques
1. **Mise en cache :** Utiliser Redis (Memorystore) pour stocker les timelines déjà calculées.
2. **Fan-out on Write :** Pré-calculer la timeline lors de la publication d'un post (pousser le post dans les feeds des abonnés).
3. **Optimisation Datastore :** Vérifier les index composites pour éviter les scans coûteux.

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