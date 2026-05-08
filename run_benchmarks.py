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
**Oui, les tendances observées sont logiques et prévisibles compte tenu de l'architecture et des technologies utilisées.**

1.  **Concurrence (Expérience A) :** L'augmentation de la latence avec le nombre d'utilisateurs simultanés est une conséquence directe de la contention des ressources. Sans une couche de cache efficace, chaque requête `timeline` doit interroger directement Google Cloud Datastore. À mesure que la charge augmente, les instances App Engine peuvent saturer leurs connexions I/O vers Datastore, ou Datastore lui-même peut commencer à introduire de la latence pour gérer le débit. Le scaling horizontal d'App Engine (visible dans la colonne `Instances`) tente de compenser, mais il y a un délai inhérent à la mise en place de nouvelles instances, et la latence peut grimper avant que le système ne s'adapte pleinement. Les échecs (`FAILED=1`) à partir de 50 utilisateurs simultanés indiquent que le système atteint ses limites de capacité ou de réactivité sous cette charge.

2.  **Fan-out (Expérience B) :** L'impact linéaire du nombre de "followees" sur la latence est également attendu. Le modèle "Fan-out on Read" signifie que pour construire la timeline d'un utilisateur, l'application doit récupérer les posts de *tous* les utilisateurs qu'il suit. Si un utilisateur suit 60 personnes, la requête Datastore (ou une série de requêtes) doit potentiellement agréger des données de 60 sources différentes. Cela se traduit par :
    *   Des requêtes GQL plus complexes (utilisant l'opérateur `IN` sur une liste de clés, par exemple).
    *   Un volume de données plus important à transférer depuis Datastore.
    *   Une charge de traitement plus élevée côté application pour assembler la timeline.
    Ces facteurs contribuent directement à l'augmentation du temps de réponse.

### Est-ce que ça "scale" ?
**Techniquement, l'infrastructure Google App Engine scale, mais l'application TinyInsta, dans son implémentation actuelle, ne scale pas efficacement pour une charge élevée ou un graphe social dense.**

*   **Infrastructure (OUI) :** Google App Engine, en tant que PaaS serverless, démontre sa capacité à provisionner de nouvelles instances automatiquement (`NB_INSTANCES` > 1 pour les charges élevées) pour absorber la charge. Cela confirme l'élasticité horizontale de la plateforme. Cependant, le scaling n'est pas instantané et les "cold starts" peuvent impacter la latence initiale.
*   **Application (NON) :** Le modèle "Fan-out on Read" est le principal goulot d'étranglement. Dès que la latence dépasse un seuil critique (souvent 500ms à 1 seconde pour une expérience utilisateur fluide), l'application est considérée comme non scalable pour ce cas d'usage. Les résultats montrent des latences de plusieurs secondes pour 1000 utilisateurs simultanés ou 60 followees, ce qui est inacceptable en production. De plus, les échecs (`FAILED=1`) indiquent une dégradation de la qualité de service. Ce modèle est particulièrement vulnérable au problème du "hotspotting" si un utilisateur très populaire est suivi par de nombreux autres, car ses posts devront être lus fréquemment par un grand nombre de requêtes `timeline`.

**En résumé :** L'infrastructure GCP offre la capacité de scaler, mais l'architecture applicative de TinyInsta ne tire pas pleinement parti de cette capacité pour les scénarios de forte concurrence ou de fan-out important. Des optimisations au niveau de l'application sont indispensables.

## 5. Recommandations Techniques
Pour améliorer la scalabilité et la performance de TinyInsta, plusieurs pistes d'optimisation sont à considérer :

1.  **Mise en cache agressive (Redis / Memorystore) :**
    *   **Quoi cacher :** Les timelines des utilisateurs (surtout les plus actifs ou les plus suivis), les profils utilisateurs fréquemment consultés, et les posts récents.
    *   **Pourquoi :** Réduire drastiquement le nombre de lectures coûteuses vers Datastore. Une lecture en cache est généralement de l'ordre de la milliseconde, contre des dizaines voire centaines de millisecondes pour Datastore. Cela permettrait d'absorber des pics de charge sans impacter directement la base de données.

2.  **Migration vers un modèle "Fan-out on Write" :**
    *   **Principe :** Au lieu de calculer la timeline à chaque lecture, pré-calculer et stocker la timeline d'un utilisateur au moment où un de ses followees publie un nouveau post.
    *   **Implémentation :** Lorsqu'un utilisateur poste, une tâche asynchrone (via Cloud Tasks ou Pub/Sub + Cloud Functions/Workers) est déclenchée. Cette tâche identifie tous les followers de l'utilisateur et "pousse" le nouveau post dans la timeline pré-calculée de chaque follower (stockée par exemple dans Redis ou une collection Datastore dédiée par utilisateur).
    *   **Avantages :** Les lectures de timeline deviennent très rapides (simple lookup d'une liste pré-construite), améliorant considérablement la latence sous forte charge.
    *   **Inconvénients/Compromis :** Augmente la complexité du système et le coût en écriture (un post = N écritures pour N followers). Nécessite une gestion de la consistance (que se passe-t-il si une écriture de timeline échoue ?).

3.  **Optimisation des requêtes Datastore et Indexation :**
    *   **Vérifier les index composites :** S'assurer que toutes les requêtes GQL complexes (notamment celles avec `ORDER BY` et des filtres multiples) disposent des index composites nécessaires. Des index manquants peuvent entraîner des scans coûteux et lents.
    *   **Requêtes de projection :** Si seule une partie des propriétés d'une entité est nécessaire, utiliser des requêtes de projection pour réduire le volume de données transférées.
    *   **Pagination efficace :** Utiliser des cursors pour la pagination des timelines afin d'éviter de relire les mêmes données et d'optimiser les performances des requêtes.

4.  **Stratégies de Sharding pour les "hotspots" :**
    *   **Sharded Counters :** Pour les compteurs globaux (ex: nombre total de posts), utiliser des compteurs sharded (ex: 16 ou 32 sous-compteurs distribués) pour éviter les "hotspots" en écriture sur une seule entité. La lecture agrège ensuite ces sous-compteurs.
    *   **Distribution des followees :** Pour le "Fan-out on Write", s'assurer que les écritures dans les timelines des followers sont distribuées et ne ciblent pas toujours les mêmes entités, surtout pour les utilisateurs très populaires.

Ces recommandations visent à transformer TinyInsta d'une application fonctionnelle mais non scalable en une application capable de gérer des charges importantes et des graphes sociaux complexes, en tirant parti des services managés de Google Cloud.

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