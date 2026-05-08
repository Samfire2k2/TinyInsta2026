#!/usr/bin/env python3
"""
Générateur de rapport TinyInsta - Post-traitement uniquement.
Lit les fichiers CSV existants pour générer les PNG et le README.
"""
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime

OUTPUT_DIR = 'out'
README_FILE = 'README.md'

def load_data_robustly(filename):
    """Charge un CSV et ajoute les headers s'ils sont manquants."""
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        print(f"Fichier introuvable : {path}")
        return None
    
    df = pd.read_csv(path)
    # Si la première colonne n'est pas 'PARAM', on considère que le header manque
    if 'PARAM' not in df.columns:
        df = pd.read_csv(path, header=None, names=["PARAM", "AVG_TIME", "RUN", "FAILED", "NB_INSTANCES"])
    
    # Nettoyage de la colonne AVG_TIME (retrait du 'ms' et conversion en float)
    df['AVG_TIME_FLOAT'] = df['AVG_TIME'].astype(str).str.replace('ms', '').astype(float)
    return df

def generate_plot(df, title, xlabel, output_name, color):
    """Génère un barplot avec barres d'erreur (variance)."""
    if df is None: return

    # Groupement par paramètre pour calculer moyenne et écart-type (variance des 3 runs)
    grouped = df.groupby('PARAM')['AVG_TIME_FLOAT'].agg(['mean', 'std']).fillna(0)
    
    plt.figure(figsize=(10, 6))
    grouped['mean'].plot(kind='bar', yerr=grouped['std'], capsize=5, color=color, edgecolor='black', alpha=0.8)
    
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel(xlabel)
    plt.ylabel('Temps moyen (ms)')
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    out_path = os.path.join(OUTPUT_DIR, output_name)
    plt.savefig(out_path, dpi=150)
    print(f"✅ Graphique généré : {out_path}")
    plt.close()

def df_to_markdown_table(df):
    """Transforme un DataFrame en tableau Markdown pour le rapport."""
    if df is None: return "| N/A | N/A | N/A | N/A | N/A |\n"
    
    table = ""
    for _, row in df.iterrows():
        table += f"| {row['PARAM']} | {row['AVG_TIME']} | {row['RUN']} | {row['FAILED']} | {row['NB_INSTANCES']} |\n"
    return table

def main():
    print("📊 Début du post-traitement des données...")

    # 1. Chargement des données
    df_conc = load_data_robustly("conc.csv")
    df_fanout = load_data_robustly("fanout.csv")

    # 2. Génération des graphiques
    generate_plot(df_conc, "Évolution de la latence selon la concurrence", "Utilisateurs simultanés", "conc.png", "skyblue")
    generate_plot(df_fanout, "Impact du Fan-out sur la latence (50 users)", "Nombre de Followees", "fanout.png", "coral")

    # 3. Génération du README
    report_content = f"""# 📊 Rapport d'Analyse de Performance - TinyInsta

**Généré le :** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. Expérience A : Concurrence (Scale Up)
*Données : 1000 users, 50 posts/user, 20 abonnements.*

| Paramètre | Temps Moyen | Run | Échec | Instances |
|---|---|---|---|---|
{df_to_markdown_table(df_conc)}

![Graphique Concurrence](out/conc.png)

## 2. Expérience B : Fan-out (Data Size)
*Données : 1000 users, 100 posts/user, 50 users simultanés.*

| Paramètre | Temps Moyen | Run | Échec | Instances |
|---|---|---|---|---|
{df_to_markdown_table(df_fanout)}

![Graphique Fan-out](out/fanout.png)

---

## 3. Analyse & Interprétation

### Est-ce logique ?
L'augmentation de la latence dans l'Expérience A est attendue : plus d'utilisateurs simultanés saturent les ressources I/O vers Datastore. Pour le Fan-out, l'impact est linéaire car l'opérateur `IN` doit traiter plus de clés pour construire la timeline.

### Est-ce que ça "scale" ?
**Infrastructure :** Oui, Google App Engine scale horizontalement (voir colonne Instances).
**Application :** Non, le modèle "Fan-out on Read" montre ses limites. Une latence dépassant 500ms n'est pas acceptable en production.

## 4. Recommandations
1. **Mise en cache :** Utiliser Memorystore (Redis).
2. **Fan-out on Write :** Pré-calculer les timelines lors de l'écriture d'un post.
"""

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"✅ Rapport final écrit dans {README_FILE}")

if __name__ == "__main__":
    main()