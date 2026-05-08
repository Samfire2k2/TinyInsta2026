import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_csv(filename, title, xlabel, output_name):
    if not os.path.exists(filename):
        return
    
    df = pd.read_csv(filename)
    # Si l'en-tête est manquant (KeyError prévenu), on recharge avec les noms explicites
    if 'PARAM' not in df.columns:
        df = pd.read_csv(filename, header=None, names=["PARAM", "AVG_TIME", "RUN", "FAILED", "NB_INSTANCES"])

    # Nettoyage du "ms" pour calculs
    df['AVG_TIME'] = df['AVG_TIME'].astype(str).str.replace('ms', '').astype(float)
    
    # Groupement par paramètre pour moyenne et écart-type
    grouped = df.groupby('PARAM')['AVG_TIME'].agg(['mean', 'std']).fillna(0)
    
    plt.figure(figsize=(10, 6))
    grouped['mean'].plot(kind='bar', yerr=grouped['std'], capsize=5, color='skyblue', edgecolor='black')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel('Temps moyen (ms)')
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(output_name)
    print(f"Graphique {output_name} généré.")

if __name__ == "__main__":
    plot_csv('out/conc.csv', 'Passage à l\'échelle : Concurrence', 'Nombre d\'utilisateurs simultanés', 'out/conc.png')
    plot_csv('out/fanout.csv', 'Passage à l\'échelle : Fan-out', 'Nombre de Followees par utilisateur', 'out/fanout.png')