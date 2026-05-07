#!/usr/bin/env python3
"""Automation script for TinyInsta performance tests.

Assuming data is already seeded using seed.py
This script ONLY runs the Locust load tests.
"""
import os
import subprocess
import csv
import time
import requests

# Configuration
# Correction du guillemet manquant et ajout automatique du slash final si absent
try:
    PROJECT_ID = subprocess.check_output("gcloud config get-value project", shell=True).decode().strip()
    DEFAULT_URL = f"https://{PROJECT_ID}.nw.r.appspot.com/"
except:
    DEFAULT_URL = 'https://tiny-494020.nw.r.appspot.com/'

TINYINSTA_URL = os.getenv('TINYINSTA_URL', DEFAULT_URL)
if TINYINSTA_URL and not TINYINSTA_URL.endswith('/'):
    TINYINSTA_URL += '/'

OUTPUT_DIR = 'out'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_gcloud_instances():
    """Get number of running instances."""
    try:
        print("  [Cloud] Récupération du nombre d'instances GCP...", end="", flush=True)
        result = subprocess.run(
            ['gcloud', 'app', 'instances', 'list', '--format=value(instanceId)'],
            capture_output=True, text=True, check=True
        )
        instances = result.stdout.strip().split('\n')
        count = len([i for i in instances if i])
        print(f" {count} trouvée(s).")
        return count
    except:
        print(" Erreur (valeur par défaut : 1).")
        return 1


def run_locust_test(concurrent_users: int, duration_seconds: int = 60, label="") -> dict:
    """Run Locust test and return metrics."""
    print(f"\n>>> [Locust] Lancement du test : {concurrent_users} utilisateurs (Durée : {duration_seconds}s)")
    
    # Run Locust in headless mode
    cmd = [
        'locust',
        f'--host={TINYINSTA_URL}',
        f'--users={concurrent_users}',
        f'--spawn-rate={max(1, concurrent_users // 5)}',
        f'--run-time={duration_seconds}s',
        '--headless',
        f'--csv={OUTPUT_DIR}/locust_test',
        '-f', 'locustfile.py'
    ]
    
    try:
        # Locust ajoute '_stats.csv' au préfixe défini dans --csv
        stats_file = os.path.join(OUTPUT_DIR, 'locust_test_stats.csv')
        # Nettoyer l'ancien fichier de résultats pour éviter de lire des données périmées en cas d'échec
        if os.path.exists(stats_file):
            os.remove(stats_file)
        
        # On lance le processus Locust en arrière-plan
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=SCRIPT_DIR)

        # IMPORTANT : On attend que le scaling s'opère pour mesurer les instances. 
        # On augmente le délai pour laisser App Engine avoir le temps de scaler.
        print(f"  [Locust] Test lancé ({duration_seconds}s)... Attente pour le scaling...", end="", flush=True)
        time.sleep(30) # Augmenté de 10s à 30s pour laisser le temps au scaling
        nb_instances = get_gcloud_instances()
        
        # On attend la fin précise du processus sans ajouter de délai inutile
        while process.poll() is None:
            time.sleep(1)
        print(" OK.")

        # Lecture des résultats Locust
        results = {
            'users': concurrent_users,
            'avg_time': 0,
            'failed': 0,
            'instances': get_gcloud_instances()
        }
        
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # On cherche la ligne de résumé "Aggregated"
                    if row.get('Name') == 'Aggregated' or row.get('Type') == 'Aggregated':
                        results['avg_time'] = float(row.get('Average Response Time', '0'))
                        results['failed'] = int(row.get('Failure Count', '0')) > 0 # Convertir en 0 ou 1
        
        print(f"✅ [Locust] Terminé : {results['avg_time']:.1f}ms | Fails: {results['failed']} | Instances: {results['instances']}")
        return results
        
    except Exception as e:
        print(f"❌ [Locust] Erreur pendant le test : {e}")
        return {'users': concurrent_users, 'avg_time': 0, 'failed': 1, 'instances': 1}


def seed_app(users, posts, follows, clear=True):
    """Appelle l'endpoint de seed pour préparer les données."""
    print(f"\n[SEEDING] Basculement sur seed.py (local) pour gérer le volume de données...")
    
    cmd = [
        "python3", "seed.py",
        "--users", str(users),
        "--posts", str(posts),
        "--follows-min", str(follows),
        "--follows-max", str(follows)
    ]
    if clear:
        cmd.append("--clear")

    try:
        subprocess.run(cmd, check=True, cwd=SCRIPT_DIR)
        print("  [Seeding] Succès.")
    except subprocess.CalledProcessError as e:
        print(f"  [Seeding] ÉCHEC : {e}")




def run_concurrency_tests():
    """Exécute les tests de concurrence (1 à 1000 utilisateurs)."""
    print(f"\n{'='*60}\nEXPÉRIENCE 1 : CONCURRENCE\n{'='*60}")
    concurrency_levels = [1, 10, 20, 50, 100, 1000]
    results = []
    
    # TP : 1000 users, 50 posts/user (50k total), 20 follows. On FORCE le clear.
    seed_app(1000, 50000, 20, clear=True)
    # Pause cruciale : laisse l'instance respirer après les écritures massives
    print("  [Cooldown] Pause de 15s après le seeding et avant de lancer Locust...")
    time.sleep(15)


    for param in concurrency_levels:
        for run in range(1, 4):  # 3 runs
            print(f"\n# CONCURRENCE : {param} users | Run {run}/3")
            metrics = run_locust_test(param, duration_seconds=60)
            result = {
                'PARAM': param,
                'AVG_TIME': f"{metrics.get('avg_time', 0):.1f}ms",
                'RUN': run,
                'FAILED': metrics.get('failed', 0),
                'NB_INSTANCES': metrics.get('instances', 1)
            }
            results.append(result)
            time.sleep(10)
    
    # Sauvegarde CSV
    csv_file = f'{OUTPUT_DIR}/conc.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['PARAM', 'AVG_TIME', 'RUN', 'FAILED', 'NB_INSTANCES'])
        writer.writeheader()
        writer.writerows(results)
    return results


def run_fanout_tests():
    """Exécute les tests de fanout (variation du nombre de followers)."""
    print(f"\n{'='*60}\nEXPÉRIENCE 2 : FANOUT\n{'='*60}")
    follow_counts = [20, 40, 60]
    results = []
    
    # Automate seeding for Fanout (1000 users, 100 posts, vary followers)
    for param in follow_counts:
        # TP : 1000 users, 100 posts/user (100k total), 50 users simultanés, follows variables.
        seed_app(1000, 100000, param, clear=True)
        # Pause cruciale : laisse l'instance respirer après les écritures massives
        print("  [Cooldown] Pause de 15s après le seeding et avant de lancer Locust...")
        time.sleep(15)
        
        for run in range(1, 4):  # 3 runs
            print(f"\n# FANOUT : {param} followers | Run {run}/3")
            # Fixed: 50 concurrent users
            metrics = run_locust_test(concurrent_users=50, duration_seconds=60)
            result = {
                'PARAM': param,
                'AVG_TIME': f"{metrics.get('avg_time', 0):.1f}ms",
                'RUN': run,
                'FAILED': metrics.get('failed', 0),
                'NB_INSTANCES': metrics.get('instances', 1)
            }
            results.append(result)
            time.sleep(10)
    
    # Sauvegarde CSV
    csv_file = f'{OUTPUT_DIR}/fanout.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['PARAM', 'AVG_TIME', 'RUN', 'FAILED', 'NB_INSTANCES'])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n[Fanout] Résultats sauvegardés dans {csv_file}")
    return results


if __name__ == '__main__':
    print(f"[Start] TinyInsta Performance Testing")
    
    # Run both experiments
    conc_results = run_concurrency_tests()
    fanout_results = run_fanout_tests()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print(f"Results saved in {OUTPUT_DIR}/")
    print("="*60)
