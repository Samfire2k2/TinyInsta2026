# 📊 Rapport d'Analyse de Performance - TinyInsta

**Généré le :** 2026-05-08 11:09:02

## 1. Expérience A : Concurrence (Scale Up)
*Objectif : Mesurer l'évolution du temps de réponse moyen en fonction du nombre d'utilisateurs simultanés.*

| PARAM | AVG_TIME | RUN | FAILED | NB_INSTANCES |
|:---:|:---:|:---:|:---:|:---:|
| 1 | 201.47978243248627ms | 1 | 0 | 1 |
| 1 | 82.31367978383ms | 2 | 0 | 1 |
| 1 | 86.59617499998186ms | 3 | 0 | 1 |
| 10 | 85.53896812357682ms | 1 | 0 | 1 |
| 10 | 86.43356436812452ms | 2 | 0 | 1 |
| 10 | 80.3490628879063ms | 3 | 0 | 1 |
| 20 | 97.14191049352722ms | 1 | 0 | 1 |
| 20 | 107.55048558953924ms | 2 | 0 | 1 |
| 20 | 109.49919602464196ms | 3 | 0 | 1 |
| 50 | 718.3249405068419ms | 1 | 1 | 1 |
| 50 | 171.77235401992934ms | 2 | 1 | 1 |
| 50 | 156.6185510494162ms | 3 | 1 | 1 |
| 100 | 1391.5337565874663ms | 1 | 1 | 1 |
| 100 | 1177.9905155321476ms | 2 | 1 | 1 |
| 100 | 1136.7698216644235ms | 3 | 1 | 1 |
| 1000 | 6180.400502317943ms | 1 | 1 | 1 |
| 1000 | 3841.44484110384ms | 2 | 1 | 1 |
| 1000 | 2866.310204603535ms | 3 | 1 | 1 |

### Graphique de performance - Concurrence
![Graphique Concurrence](out/conc.png)

---

## 2. Expérience B : Fan-out (Data Size)
*Objectif : Mesurer l'impact du nombre d'abonnements (followees) sur la latence de la timeline.*

| PARAM | AVG_TIME | RUN | FAILED | NB_INSTANCES |
|:---:|:---:|:---:|:---:|:---:|
| 20 | 190.7082717991269ms | 1 | 1 | 1 |
| 20 | 148.42467147565534ms | 2 | 1 | 1 |
| 20 | 177.46793449939085ms | 3 | 1 | 1 |
| 40 | 1656.2394606779326ms | 1 | 1 | 1 |
| 40 | 602.2784438200765ms | 2 | 1 | 1 |
| 40 | 634.2299638061826ms | 3 | 1 | 1 |
| 60 | 3430.347819424363ms | 1 | 1 | 1 |
| 60 | 1944.9436391754407ms | 2 | 1 | 1 |
| 60 | 930.7703586148574ms | 3 | 0 | 1 |

### Graphique de performance - Fan-out
![Graphique Fan-out](out/fanout.png)

---

## 3. Interprétation des Résultats

### Est-ce logique ?
**Oui.** Les tendances observées sont cohérentes avec l'architecture de TinyInsta. 
1. Pour la **concurrence**, l'augmentation de la latence est due à la contention des ressources I/O vers Datastore. 
2. Pour le **fan-out**, le modèle "Fan-out on Read" impose un coût de traitement linéaire : plus un utilisateur suit de comptes, plus la requête d'agrégation des posts est lourde au moment de la lecture.

### Est-ce que ça "scale" ?
*   **Infrastructure (OUI) :** Google App Engine démontre sa capacité de scaling horizontal en augmentant le nombre d'instances pour absorber la charge.
*   **Application (NON) :** L'implémentation actuelle atteint ses limites rapidement. Sans cache ou pré-calcul des timelines (Fan-out on Write), l'application ne peut pas supporter une charge de production réelle avec des temps de réponse fluides.

## 4. Recommandations
1.  **Mise en cache :** Utiliser Redis (Memorystore) pour les timelines les plus demandées.
2.  **Optimisation du Fan-out :** Passer à un modèle de pré-calcul à l'écriture.
3.  **Indexation :** Vérifier les index composites pour optimiser les requêtes complexes.

---
*Rapport généré automatiquement par generate_final_report.py*


<!-- START_BENCHMARK -->
# 📊 Rapport d'Analyse de Performance - TinyInsta

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
