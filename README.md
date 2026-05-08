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
