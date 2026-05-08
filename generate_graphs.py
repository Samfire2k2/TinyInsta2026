#!/usr/bin/env python3
"""Generate performance graphs from test results.

Creates bar plots showing execution time vs parameters with error bars.
"""
import pandas as pd
import matplotlib.pyplot as plt
import os

OUTPUT_DIR = 'out'

def plot_concurrency_results():
    """Create bar plot for concurrency test results."""
    csv_file = f'{OUTPUT_DIR}/conc.csv'
    
    if not os.path.exists(csv_file):
        print(f"Warning: {csv_file} not found")
        return
    
    # Read data
    df = pd.read_csv(csv_file)
    
    # Convert AVG_TIME to float (remove 'ms' suffix if present)
    df['AVG_TIME'] = df['AVG_TIME'].astype(str).str.replace('ms', '').astype(float)
    
    # Group by PARAM and compute mean and std
    grouped = df.groupby('PARAM')['AVG_TIME'].agg(['mean', 'std']).reset_index()
    grouped.columns = ['PARAM', 'mean', 'std']
    grouped['std'] = grouped['std'].fillna(0)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Bar plot with error bars
    x_pos = range(len(grouped))
    ax.bar(x_pos, grouped['mean'], yerr=grouped['std'], 
           capsize=5, alpha=0.7, color='steelblue', edgecolor='black')
    
    # Formatting
    ax.set_xlabel('Nombre d\'utilisateurs concurrents', fontsize=12)
    ax.set_ylabel('Temps moyen par requête (ms)', fontsize=12)
    ax.set_title('Temps moyen par requête selon la concurrence', fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(grouped['PARAM'])
    ax.grid(axis='y', alpha=0.3)
    
    # Save
    output_file = f'{OUTPUT_DIR}/conc.png'
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"[Graph] Saved: {output_file}")
    plt.close()


def plot_fanout_results():
    """Create bar plot for fanout test results."""
    csv_file = f'{OUTPUT_DIR}/fanout.csv'
    
    if not os.path.exists(csv_file):
        print(f"Warning: {csv_file} not found")
        return
    
    # Read data
    df = pd.read_csv(csv_file)
    
    # Convert AVG_TIME to float
    df['AVG_TIME'] = df['AVG_TIME'].astype(str).str.replace('ms', '').astype(float)
    
    # Group by PARAM and compute mean and std
    grouped = df.groupby('PARAM')['AVG_TIME'].agg(['mean', 'std']).reset_index()
    grouped.columns = ['PARAM', 'mean', 'std']
    grouped['std'] = grouped['std'].fillna(0)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Bar plot with error bars
    x_pos = range(len(grouped))
    ax.bar(x_pos, grouped['mean'], yerr=grouped['std'],
           capsize=5, alpha=0.7, color='coral', edgecolor='black')
    
    # Formatting
    ax.set_xlabel('Nombre de followers par utilisateur', fontsize=12)
    ax.set_ylabel('Temps moyen par requête (ms)', fontsize=12)
    ax.set_title('Impact du fanout sur les performances (50 utilisateurs simultanés)', fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(grouped['PARAM'])
    ax.grid(axis='y', alpha=0.3)
    
    # Save
    output_file = f'{OUTPUT_DIR}/fanout.png'
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"[Graph] Saved: {output_file}")
    plt.close()


if __name__ == '__main__':
    print("[Graph] Generating performance plots...")
    plot_concurrency_results()
    plot_fanout_results()
    print("[Graph] Done!")
