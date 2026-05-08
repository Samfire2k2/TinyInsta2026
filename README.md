<!-- START_BENCHMARK -->
# 📊 Rapport d'Analyse de Performance - TinyInsta - RAVARD Samuel

**Généré le :** 2026-05-08 15:24:28
**URL Application :** [https://tiny-494020.nw.r.appspot.com](https://tiny-494020.nw.r.appspot.com)

## 1. Executive Summary
Ce rapport évalue la capacité de passage à l'échelle (scalability) de TinyInsta sur Google App Engine. Nous analysons deux scénarios critiques : la montée en charge utilisateur (Concurrence) et l'impact de la taille du graphe social (Fan-out).

## 2. Expérience A : Concurrence (Scale Up)
*Objectif : Mesurer l'évolution du temps de réponse avec une charge de 1 à 1000 utilisateurs simultanés.*

| Paramètre | Temps Moyen | Run | Échec | Instances |
|---|---|---|---|---|
| 1 | 122.86812235132292ms | 1 | 0 | 1 |
| 1 | 80.11408573683136ms | 2 | 0 | 1 |
| 1 | 69.40267247368506ms | 3 | 0 | 1 |
| 10 | 66.49328611047811ms | 1 | 0 | 1 |
| 10 | 66.63826468966225ms | 2 | 0 | 1 |
| 10 | 65.39710979250071ms | 3 | 0 | 1 |
| 20 | 75.18728852631402ms | 1 | 0 | 1 |
| 20 | 73.4169235305834ms | 2 | 0 | 1 |
| 20 | 75.28266598285853ms | 3 | 0 | 1 |
| 50 | 489.6607620360731ms | 1 | 1 | 1 |
| 50 | 455.51054649112825ms | 2 | 1 | 1 |
| 50 | 157.91787749581152ms | 3 | 1 | 1 |
| 100 | 820.5657604877963ms | 1 | 1 | 1 |
| 100 | 834.544342655347ms | 2 | 1 | 1 |
| 100 | 971.1956104749096ms | 3 | 1 | 1 |
| 1000 | 5115.128959518996ms | 1 | 1 | 1 |
| 1000 | 3863.456083905278ms | 2 | 1 | 1 |
| 1000 | 2371.140002100503ms | 3 | 1 | 1 |


### Graphiques de Performance
![Graphique Concurrence](out/conc.png)

## 3. Expérience B : Fan-out (Data Size)
*Objectif : Mesurer l'impact du nombre d'abonnements (20, 40, 60) sur la génération de la timeline.*

| Paramètre | Temps Moyen | Run | Échec | Instances |
|---|---|---|---|---|
| 20 | 162.8848421649625ms | 1 | 1 | 1 |
| 20 | 170.93476809486407ms | 2 | 1 | 1 |
| 20 | 162.37344990770922ms | 3 | 1 | 1 |
| 40 | 1932.9630303098195ms | 1 | 1 | 1 |
| 40 | 1891.1513341569084ms | 2 | 1 | 1 |
| 40 | 2078.7273818878857ms | 3 | 1 | 1 |
| 60 | 3120.469322431044ms | 1 | 1 | 1 |
| 60 | 3086.8739100443ms | 2 | 1 | 1 |
| 60 | 3065.970958042461ms | 3 | 1 | 1 |


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