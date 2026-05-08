#!/usr/bin/env python3
"""Script de peuplement (seed) pour Tiny Instagram.

Usage basique:
  python seed.py --users 5 --posts 40 --follows-min 1 --follows-max 3

Paramètres:
  --users        Nombre d'utilisateurs à créer (user1 .. userN)
  --posts        Nombre total de posts à répartir
  --follows-min  Nombre minimum de follows par utilisateur
  --follows-max  Nombre maximum de follows par utilisateur
  --prefix       Préfixe des noms d'utilisateurs (default: user)
  --dry-run      N'écrit rien, affiche seulement le plan

Le script est idempotent sur les utilisateurs (il ne recrée pas si existants) et ajoute simplement des posts supplémentaires.

ATTENTION: Ce script écrit directement dans Datastore du projet courant (gcloud config get-value project).
"""
from __future__ import annotations
import argparse
import random
import time
from datetime import datetime, timedelta
from google.cloud import datastore


def parse_args():
    p = argparse.ArgumentParser(description="Seed Datastore for Tiny Instagram")
    p.add_argument('--users', type=int, default=5)
    p.add_argument('--posts', type=int, default=30)
    p.add_argument('--follows-min', type=int, default=1)
    p.add_argument('--follows-max', type=int, default=3)
    p.add_argument('--prefix', type=str, default='user')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--clear', action='store_true', help="Supprime les posts et users existants avant de seeder")
    return p.parse_args()

def clear_all_data(client: datastore.Client):
    """Supprime proprement les entités Post et User par batchs."""
    print("[Seed] Nettoyage du Datastore...")

    # Sur les bases "Enterprise" ou nommées 'default', la requête sur __kind__ 
    # est interdite via l'API Datastore. On nettoie donc les types connus en dur.
    kinds = ['Post', 'User']
    print(f"[Seed] Suppression des entités pour les types: {kinds}")

    for kind in kinds:
        deleted_count = 0
        while True:
            try:
                query = client.query(kind=kind)
                query.keys_only()
                # Utilisation d'un timeout de 180s pour éviter les erreurs 504
                entities = list(query.fetch(limit=500, timeout=180))
                if not entities:
                    break
                
                keys = [e.key for e in entities]
                client.delete_multi(keys)
                deleted_count += len(keys)
                print(f"  [Seed] Nettoyage {kind}: {deleted_count} supprimés...", end="\r", flush=True)
            except Exception as e:
                print(f"\n[Seed] Pause de 5s suite à une erreur (timeout ?): {e}")
                time.sleep(5)
                continue
        print(f"\n[Seed] Kind {kind} nettoyé.")

def ensure_users(client: datastore.Client, names: list[str], dry: bool):
    """Crée les utilisateurs en utilisant put_multi pour la performance."""
    users_to_create = []
    for name in names:
        key = client.key('User', name)
        entity = client.get(key)
        if entity is None:
            entity = datastore.Entity(key)
            entity['follows'] = []
            users_to_create.append(entity)
    
    if not dry and users_to_create:
        # On réduit à 200 pour éviter les DeadlineExceeded
        for i in range(0, len(users_to_create), 200):
            client.put_multi(users_to_create[i:i+200])
            time.sleep(0.1) # Petit délai pour la stabilité

    return len(users_to_create)


def assign_follows(client: datastore.Client, names: list[str], fmin: int, fmax: int, dry: bool):
    """Ajuste les relations de suivi en masse."""
    updated_users = []
    for name in names:
        key = client.key('User', name)
        entity = client.get(key)
        if entity is None:
            continue  # devrait exister
        # Générer un set de follows (exclure soi-même)
        others = [u for u in names if u != name]
        if not others:
            continue
        target_count = random.randint(min(fmin, len(others)), min(fmax, len(others)))
        selection = random.sample(others, target_count)
        # Fusion avec existants
        existing = set(entity.get('follows', []))
        new_set = sorted(existing.union(selection))
        entity['follows'] = new_set
        updated_users.append(entity)

    if not dry and updated_users:
        for i in range(0, len(updated_users), 200):
            client.put_multi(updated_users[i:i+200])
            time.sleep(0.1)


def create_posts(client: datastore.Client, names: list[str], total_posts: int, dry: bool):
    """Crée les posts par batchs de 500 pour optimiser l'injection."""
    if not names or total_posts <= 0:
        return 0
    
    posts_batch = []
    base_time = datetime.utcnow()
    
    for i in range(total_posts):
        author = random.choice(names)
        key = client.key('Post')
        post = datastore.Entity(key)
        # Décaler artificiellement le timestamp pour obtenir un tri naturel
        post['author'] = author
        post['content'] = f"Seed post {i+1} by {author}"
        post['created'] = base_time - timedelta(seconds=i)
        
        posts_batch.append(post)
        
        # Envoi par paquets de 200 pour plus de stabilité (seeding progressif)
        if not dry and len(posts_batch) >= 200:
            client.put_multi(posts_batch)
            posts_batch = []
            print(f"  [Seed] {i+1}/{total_posts} posts créés...", end="\r", flush=True)
            time.sleep(0.2) # On laisse Datastore indexer

    if not dry and posts_batch:
        client.put_multi(posts_batch)
        
    return total_posts


def main():
    args = parse_args()
    # Spécifier explicitement la base 'default' pour éviter l'erreur 404 sur '(default)'
    client = datastore.Client(project='tiny-494020', database='default')

    user_names = [f"{args.prefix}{i}" for i in range(1, args.users + 1)]

    print(f"[Seed] Utilisateurs ciblés: {user_names}")
    if args.dry_run:
        print("[Dry-Run] Aucune écriture ne sera effectuée.")

    # Nettoyage si demandé
    if args.clear and not args.dry_run:
        clear_all_data(client)

    # 1. Users
    new_users = ensure_users(client, user_names, args.dry_run)
    print(f"[Seed] Nouveaux utilisateurs créés: {new_users}")

    # 2. Follows
    assign_follows(client, user_names, args.follows_min, args.follows_max, args.dry_run)
    print("[Seed] Relations de suivi ajustées.")

    # 3. Posts
    created_posts = create_posts(client, user_names, args.posts, args.dry_run)
    print(f"[Seed] Posts créés: {created_posts}")

    print("[Seed] Terminé.")


if __name__ == '__main__':
    main()
