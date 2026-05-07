from flask import Flask, request, redirect, url_for, render_template, session, jsonify
from google.cloud import datastore
from datetime import datetime, timedelta
import os
import random

app = Flask(__name__)
app.secret_key = 'dev-key'  # À changer en prod
# On spécifie le projet et 'default' car la base a été créée avec ce nom explicite
client = datastore.Client(project='tiny-494020', database='default')

def get_timeline(user: str, limit: int = 20):
    """Retourne la liste des posts (entités) pour la timeline d'un utilisateur."""
    if not user:
        return []
    follow_key = client.key('User', user)
    user_entity = client.get(follow_key)
    follows = []
    if user_entity:
        follows = user_entity.get('follows', [])
    follows = list({*follows, user})

    all_posts = []
    # Datastore limite l'opérateur IN à 30 valeurs maximum.
    # On découpe 'follows' en morceaux de 30 pour éviter les erreurs.
    for i in range(0, len(follows), 30):
        chunk = follows[i:i + 30]
        try:
            query = client.query(kind='Post')
            query.add_filter('author', 'IN', chunk)
            query.order = ['-created']
            all_posts.extend(list(query.fetch(limit=limit)))
        except Exception:
            # Fallback manuel si l'index IN n'est pas prêt
            for author in chunk:
                q = client.query(kind='Post')
                q.add_filter('author', '=', author)
                q.order = ['-created']
                all_posts.extend(list(q.fetch(limit=limit)))

    # On trie les résultats combinés et on applique la limite
    all_posts.sort(key=lambda x: x.get('created', datetime.min), reverse=True)
    return all_posts[:limit]


def seed_data(users: int = 5, posts: int = 30, follows_min: int = 1, follows_max: int = 3, prefix: str = 'user', clear: bool = False):
    """Crée des utilisateurs, leurs relations de suivi et des posts.
    Retourne un dict avec les compteurs. Fait des écritures directes dans Datastore.
    """
    # Nettoyage si demandé
    if clear:
        # Suppression des posts (c'est ce qui s'accumule le plus)
        query = client.query(kind='Post')
        query.keys_only()
        batch = []
        for entity in query.fetch(batch_size=500):
            batch.append(entity.key)
            if len(batch) >= 500:
                client.delete_multi(batch)
                batch = []
        if batch:
            client.delete_multi(batch)

    user_names = [f"{prefix}{i}" for i in range(1, users + 1)]
    
    # 1. Gestion des utilisateurs en masse (Batch)
    keys = [client.key('User', name) for name in user_names]
    existing_entities = {e.key.name: e for e in client.get_multi(keys)}
    
    users_to_put = []
    created_count = 0
    for name in user_names:
        if name not in existing_entities:
            entity = datastore.Entity(key=client.key('User', name))
            entity['follows'] = []
            created_count += 1
        else:
            entity = existing_entities[name]
        
        # Assignation des follows
        others = [u for u in user_names if u != name]
        if others:
            target = random.randint(min(follows_min, len(others)), min(follows_max, len(others))) if follows_max > 0 else 0
            selection = random.sample(others, target) if target > 0 else []
            # Si clear=True, on remplace la liste, sinon on fusionne
            if clear:
                entity['follows'] = sorted(set(selection))
            else:
                entity['follows'] = sorted(set(entity.get('follows', [])).union(selection))
        users_to_put.append(entity)

    # Sauvegarde des utilisateurs par paquets de 500
    for i in range(0, len(users_to_put), 500):
        client.put_multi(users_to_put[i:i+500])

    # 2. Création des posts en masse (Batch)
    base_time = datetime.utcnow()
    posts_to_put = []
    for i in range(posts):
        p = datastore.Entity(client.key('Post'))
        author = random.choice(user_names)
        p.update({
            'author': author,
            'content': f"Seed post {i+1} by {author}",
            'created': base_time - timedelta(seconds=i)
        })
        posts_to_put.append(p)
        if len(posts_to_put) >= 500:
            client.put_multi(posts_to_put)
            posts_to_put = []
            
    if posts_to_put:
        client.put_multi(posts_to_put)

    return {
        'users_total': users,
        'users_created': created_count,
        'posts_created': posts,
        'prefix': prefix
    }


@app.route('/', methods=['GET'])
def index():
    user = session.get('user')
    timeline = get_timeline(user) if user else []
    return render_template('index.html', user=user, timeline=timeline)


@app.route('/api/timeline')
def api_timeline():
    """Endpoint JSON pour tests de charge (utilise paramètre user=)."""
    user = request.args.get('user') or session.get('user')
    if not user:
        return jsonify({"error": "missing user"}), 400
    try:
        limit = int(request.args.get('limit', '20'))
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 100))
    entities = get_timeline(user, limit=limit)
    data = [
        {
            'author': e.get('author'),
            'content': e.get('content'),
            'created': (e.get('created') or datetime.utcnow()).isoformat() + 'Z'
        }
        for e in entities
    ]
    return jsonify({
        'user': user,
        'count': len(data),
        'items': data
    })


@app.route('/admin/seed', methods=['POST'])
def admin_seed():
    """Endpoint pour exécuter un seed serveur-side.
    Sécurité minimale: en-tête X-Seed-Token ou ?token= doit correspondre à SEED_TOKEN.
    Paramètres (query string ou form): users, posts, follows_min, follows_max, prefix.
    """
    expected = os.environ.get('SEED_TOKEN')
    provided = request.headers.get('X-Seed-Token') or request.args.get('token') or request.form.get('token')
    if expected and provided != expected:
        return jsonify({'error': 'forbidden'}), 403
    def _int(name, default):
        try:
            return int(request.values.get(name, default))
        except ValueError:
            return default
    users = _int('users', 5)
    posts = _int('posts', 30)
    follows_min = _int('follows_min', 1)
    follows_max = _int('follows_max', 3)
    prefix = request.values.get('prefix', 'user')
    clear = request.values.get('clear', '0') == '1'
    if users <= 0 or posts < 0:
        return jsonify({'error': 'invalid parameters'}), 400
    result = seed_data(users=users, posts=posts, follows_min=follows_min, follows_max=follows_max, prefix=prefix, clear=clear)
    return jsonify({'status': 'ok', **result})

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    key = client.key('User', username)
    if not client.get(key):
        entity = datastore.Entity(key)
        entity.update({'follows': []})
        client.put(entity)
    session['user'] = username
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/post', methods=['POST'])
def post():
    user = session.get('user')
    if not user:
        return redirect(url_for('index'))
    content = request.form['content']
    entity = datastore.Entity(client.key('Post'))
    entity.update({
        'author': user,
        'content': content,
        'created': datetime.utcnow()
    })
    client.put(entity)
    return redirect(url_for('index'))

@app.route('/follow', methods=['POST'])
def follow():
    user = session.get('user')
    to_follow = request.form['to_follow']
    if not user or user == to_follow:
        return redirect(url_for('index'))
    user_key = client.key('User', user)
    user_entity = client.get(user_key)
    if to_follow not in user_entity['follows']:
        user_entity['follows'].append(to_follow)
        client.put(user_entity)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
