# HotelBot: Interroger une base hôtelière en langage naturel

https://github.com/user-attachments/assets/ecc1e6a9-cea7-4414-af01-be19f231442f

Prototype académique de **text-to-SQL avec un LLM** : l'utilisateur pose une question en français (« Je cherche une chambre pour moins de 100 € par nuit à Marseille »), l'API Claude (Anthropic) la traduit en requête SQL, la requête est **validée** puis exécutée **en lecture seule**, et les résultats sont reformulés en langage naturel dans une interface **Streamlit**.

**🔗 Démo en ligne : https://hotelbot-kandji.streamlit.app **
_La démo utilise une base SQLite en lecture seule. La version complète tourne sur Oracle 21c avec Docker Compose (voir [Installation](#installation))._

**Statut :** prototype de démonstration. Les protections de sécurité sont testées automatiquement ; la qualité des requêtes générées n'a pas encore été évaluée sur un jeu de questions. Voir [Limites](#limites).

_Projet réalisé seul

---

## Fonctionnement

```
Question en français
        │
        ▼
1. Claude génère UNE requête SQL (schéma fourni dans le prompt système)
   ou répond NON_SUPPORTE si la question est hors périmètre
        │
        ▼
2. Validation dans le code : une seule instruction SELECT, aucun mot-clé de modification
        │  (refus → message à l'utilisateur, rien n'est exécuté)
        ▼
3. Exécution sur une connexion EN LECTURE SEULE (limite de durée et de lignes)
        │
        ▼
4. Claude rédige la réponse à partir de la question et des seuls résultats
        │
        ▼
Affichage dans Streamlit, avec la requête SQL et les résultats bruts consultables
```

Deux appels à l'API par question : un modèle plus puissant pour le SQL, un modèle plus léger pour la rédaction (configurables).

### Exemple testé

> **Question :** Je cherche une chambre pour moins de 100 € par nuit à Marseille
>
> **Requête générée :**
> ```sql
> SELECT DISTINCT h.NOMHO, h.RUEADRHO, t.NOMTY, t.PRIXTY
> FROM HOTELS h
> JOIN CHAMBRES c ON h.NUMHO = c.NUMHO
> JOIN TYPESCHAMBRE t ON c.NUMTY = t.NUMTY
> WHERE h.VILLEHO = 'Marseille'
> AND t.PRIXTY < 100
> ORDER BY t.PRIXTY
> ```

## Sécurité

Le SQL produit par le LLM n'est **jamais considéré comme fiable**. Le projet applique une **défense en profondeur** :

| Barrière | Mise en œuvre | Fichier |
| --- | --- | --- |
| 1. Base en lecture seule | SQLite ouvert en `mode=ro` avec `PRAGMA query_only` ; sous Oracle, utilisateur dédié qui n'a que le droit `SELECT` | `backend/database.py`, `scripts/init_oracle.py` |
| 2. Validation de la requête | Une seule instruction ; `SELECT` ou `WITH … SELECT` uniquement ; commentaires refusés ; mots-clés de modification refusés en dehors des textes entre guillemets | `backend/securite.py` |
| 3. Prompt | La question est encadrée par des balises et traitée comme une donnée ; consigne de répondre `NON_SUPPORTE` hors périmètre | `backend/llm.py` |
| 4. Limites d'usage | Durée maximale par requête (5 s), 50 lignes au maximum, 10 questions par session, 300 caractères par question, limite de dépenses sur la clé API | `app.py`, `backend/database.py` |

### Tentatives testées

| Tentative | Résultat |
| --- |  |
| Requête de lecture normale | Exécutée |
| `SELECT * FROM HOTELS; DROP TABLE CLIENTS` (deux instructions) | Ignore le DROP |
| `SELECT * FROM HOTELS -- DROP …` (commentaire) | Ignore le DROP |
| `DELETE`, `UPDATE`, `INSERT`, `DROP`, `CREATE`, `SELECT … INTO` | Bloquées par la validation **et** refusées par la base |
| `PRAGMA`, `ATTACH`, `load_extension`, paquets Oracle `DBMS_*` / `UTL_*` | Bloqués par la validation |
| Nom contenant un mot interdit (`'Drop Inn'`) | Exécutée (pas de faux positif) |
| « Hôtels avec piscine » (hors schéma) | Le modèle doit répondre `NON_SUPPORTE` → refus |

Ces cas sont vérifiés par **40 tests automatiques** (`tests/`), dont des tests qui contournent la validation pour vérifier que **la base elle-même** refuse toute écriture :

```bash
python -m pytest
```

## Fonctionnalités

- **Chat en langage naturel** avec historique de la session, requête SQL et résultats bruts affichés pour vérifier chaque réponse.
- **Page Données** : consultation des tables (lecture seule).
- **Page Sécurité** : explication des protections.
- **Consultation uniquement** : le chatbot ne crée ni ne modifie aucune réservation.

## Base de données

Schéma de 6 tables, avec clés primaires, clés étrangères et contraintes `CHECK` :

| Table | Contenu |
| --- | --- |
| `HOTELS` | Hôtels : nom, adresse, ville, nombre d'étoiles |
| `TYPESCHAMBRE` | Types de chambre et prix par nuit |
| `CHAMBRES` | Chambres de chaque hôtel |
| `CLIENTS` | Clients |
| `RESERVATIONS` | Réservations : client, hôtel, type, date d'arrivée, nombre de nuits, nombre de chambres |
| `OCCUPATIONS` | Occupations effectives des chambres |

**Données de démonstration** : 10 hôtels, 10 types de chambre (de 89 € à 599 €), 100 chambres, 15 clients, 20 réservations et 30 occupations. Les noms et adresses d'hôtels sont réels et servent seulement d'exemples ; les prix, chambres, clients et réservations sont **fictifs**. Les dates sont calculées à partir du jour de génération de la base.

## Stack technique

| Composant | Technologie |
| --- | --- |
| Interface | Streamlit |
| LLM | API Claude (SDK Python `anthropic`) |
| Base de données | SQLite (démo en ligne) ; Oracle Database 21c XE (version Docker) |
| Accès Oracle | `python-oracledb` |
| Conteneurisation | Docker et Docker Compose (base + application, *healthchecks*) |
| Tests | pytest |

## Structure du projet

```
hotelbot/
├── app.py                      # interface Streamlit
├── backend/
│   ├── config.py               # lecture des secrets (st.secrets ou variables d'environnement)
│   ├── securite.py             # validation des requêtes générées
│   ├── database.py             # connexions EN LECTURE SEULE (SQLite, Oracle)
│   ├── llm.py                  # appels à Claude : SQL, puis réponse
│   ├── OracleDatabase.py       # connexion Oracle administrateur (initialisation uniquement)
│   └── CreateTables.py         # création des tables Oracle
├── scripts/
│   ├── creer_base_sqlite.py    # génère data/hotels.db
│   └── init_oracle.py          # tables, données et utilisateur lecture seule sous Oracle
├── data/hotels.db              # base de la démo
├── tests/                      # tests de sécurité et de la base
├── Dockerfile, docker-compose.yml
├── requirements.txt            # démo (SQLite)
└── requirements-oracle.txt     # version Oracle
```

## Installation

### Option 1 : en local avec SQLite (le plus simple)
```bash
git clone https://github.com/Mouhamadoukandji/hotelbot.git
cd hotelbot
python -m venv .venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # puis renseigner CLAUDE_API_KEY
python scripts/creer_base_sqlite.py  # (re)génère data/hotels.db
streamlit run app.py
```

### Option 2 : version complète avec Oracle et Docker
```bash
cp .env.example .env    # renseigner la clé API et les mots de passe Oracle
docker compose up -d --build
# Une fois la base démarrée (quelques minutes au premier lancement) :
docker compose run --rm streamlit-app python scripts/init_oracle.py
```
Puis ouvrir http://localhost:8501.

Le fichier `.env` contient des secrets : il est exclu de Git (`.gitignore`) et de l'image Docker (`.dockerignore`).

## Déploiement (Streamlit Community Cloud)

1. Vérifier que `data/hotels.db` est versionné et que **aucun secret** n'est dans le dépôt.
2. Sur share.streamlit.io : *Create app*, choisir le dépôt, la branche et `app.py`.
3. Dans *Advanced settings* → *Secrets*, coller le contenu de `.streamlit/secrets.toml.example` avec la vraie clé.
4. Dans la console Anthropic, fixer une **limite de dépenses** pour la clé utilisée par la démo.

## Limites

1. **Validation imparfaite.** Le filtre par mots-clés peut, en théorie, être contourné ou refuser une requête légitime. Il ne sert que de deuxième barrière : la protection principale est la connexion en lecture seule.
2. **Pas d'évaluation de la qualité.** La part de questions pour lesquelles le SQL généré est correct n'a pas été mesurée ; le fonctionnement a été vérifié manuellement sur quelques exemples.
3. **Risque d'hallucination à la rédaction.** Le modèle reçoit la consigne de n'utiliser que les résultats, mais rien ne le garantit. Les résultats bruts sont affichés pour permettre la vérification.
4. **Questions hors schéma.** La base ne contient ni équipements ni descriptions : ces questions doivent être refusées, mais le refus dépend du modèle.
5. **Pas de mémoire de conversation.** Chaque question est traduite indépendamment : « Et à Lyon ? » n'est pas compris.
6. **Limite de questions contournable.** Elle est liée à la session du navigateur : recharger la page la remet à zéro. La limite de dépenses de la clé API reste la protection finale contre les abus.
7. **Version Oracle.** Le script `init_oracle.py` crée les tables dans le schéma du compte administrateur ; dans un vrai déploiement, un schéma applicatif dédié serait préférable.

## Pistes d'amélioration

- [x] Connexion en lecture seule et validation des requêtes
- [x] Tests automatiques des protections
- [x] Réduction de 3 à 2 appels au LLM, et réponse fondée sur la question et les résultats
- [ ] Jeu d'évaluation (questions et résultats attendus) et mesure de l'**exactitude à l'exécution**
- [ ] Validation par analyse syntaxique du SQL (par exemple avec `sqlglot`) plutôt que par mots-clés
- [ ] Mémoire de conversation pour les questions de suivi
- [ ] Création de réservations avec confirmation de l'utilisateur et transaction contrôlée

## Auteur
**Mouhamadou Falilou KANDJI**, Master Science et Ingénierie des Données, Aix-Marseille Université.
