"""Crée la base SQLite de démonstration : data/hotels.db.

À lancer UNE FOIS en local (python scripts/creer_base_sqlite.py), puis versionner data/hotels.db.
L'application ne l'ouvre ensuite qu'en lecture seule.
Les dates sont calculées à partir du jour de génération : relancez le script pour les rafraîchir.
"""
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import sys

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_DEFAUT = RACINE / "data" / "hotels.db"

SCHEMA = """
CREATE TABLE HOTELS (
    NUMHO        INTEGER PRIMARY KEY,
    NOMHO        TEXT    NOT NULL,
    RUEADRHO     TEXT    NOT NULL,
    VILLEHO      TEXT    NOT NULL,
    NBETOILESHO  INTEGER NOT NULL CHECK (NBETOILESHO BETWEEN 1 AND 5)
);
CREATE TABLE TYPESCHAMBRE (
    NUMTY   INTEGER PRIMARY KEY,
    NOMTY   TEXT    NOT NULL,
    PRIXTY  REAL    NOT NULL CHECK (PRIXTY > 0)
);
CREATE TABLE CHAMBRES (
    NUMCH  INTEGER NOT NULL,
    NUMHO  INTEGER NOT NULL REFERENCES HOTELS (NUMHO),
    NUMTY  INTEGER NOT NULL REFERENCES TYPESCHAMBRE (NUMTY),
    PRIMARY KEY (NUMCH, NUMHO)
);
CREATE TABLE CLIENTS (
    NUMCL     INTEGER PRIMARY KEY,
    NOMCL     TEXT NOT NULL,
    PRENOMCL  TEXT NOT NULL,
    RUEADRCL  TEXT NOT NULL,
    VILLECL   TEXT NOT NULL
);
CREATE TABLE RESERVATIONS (
    NUMCL       INTEGER NOT NULL REFERENCES CLIENTS (NUMCL),
    NUMHO       INTEGER NOT NULL REFERENCES HOTELS (NUMHO),
    NUMTY       INTEGER NOT NULL REFERENCES TYPESCHAMBRE (NUMTY),
    DATEA       TEXT    NOT NULL,                       -- 'YYYY-MM-DD'
    NBJOURS     INTEGER NOT NULL CHECK (NBJOURS > 0),   -- nombre de nuits
    NBCHAMBRES  INTEGER NOT NULL CHECK (NBCHAMBRES > 0),
    PRIMARY KEY (NUMCL, NUMHO, NUMTY, DATEA)
);
CREATE TABLE OCCUPATIONS (
    NUMCL  INTEGER NOT NULL REFERENCES CLIENTS (NUMCL),
    NUMHO  INTEGER NOT NULL,
    NUMCH  INTEGER NOT NULL,
    DATEA  TEXT    NOT NULL,
    DATED  TEXT    NOT NULL,
    PRIMARY KEY (NUMHO, NUMCH, DATEA),
    FOREIGN KEY (NUMCH, NUMHO) REFERENCES CHAMBRES (NUMCH, NUMHO),
    CHECK (DATED > DATEA)
);
"""

HOTELS = [
    (1, "Hôtel Plaza Athénée", "25 Avenue Montaigne", "Paris", 5),
    (2, "Le Negresco", "37 Promenade des Anglais", "Nice", 5),
    (3, "InterContinental Lyon", "66 Quai Charles de Gaulle", "Lyon", 5),
    (4, "Hôtel de Crillon", "10 Place de la Concorde", "Paris", 5),
    (5, "Grand Hôtel de Bordeaux", "2-5 Place de la Comédie", "Bordeaux", 4),
    (6, "Hôtel Mercure Centre", "15 Rue Dr Charles Cazalis", "Marseille", 3),
    (7, "Hôtel de la Cité", "Place Auguste Pierre Pont", "Carcassonne", 4),
    (8, "Hôtel Régina", "2 Place des Pyramides", "Paris", 4),
    (9, "Hôtel Cour des Loges", "6 Rue du Boeuf", "Lyon", 4),
    (10, "Hôtel Martinez", "73 Boulevard de la Croisette", "Cannes", 5),
]

TYPES_CHAMBRE = [
    (1, "Chambre Simple Standard", 89.00),
    (2, "Chambre Double Classique", 129.00),
    (3, "Chambre Double Supérieure", 169.00),
    (4, "Suite Junior", 249.00),
    (5, "Suite Exécutive", 349.00),
    (6, "Suite Présidentielle", 599.00),
    (7, "Chambre Familiale 4 personnes", 199.00),
    (8, "Chambre Confort Vue Mer", 229.00),
    (9, "Chambre Luxe avec Balcon", 279.00),
    (10, "Suite Honeymoon", 459.00),
]

CLIENTS = [
    (1, "Martin", "Sophie", "15 Rue de la République", "Lyon"),
    (2, "Dubois", "Pierre", "22 Avenue Victor Hugo", "Paris"),
    (3, "Bernard", "Marie", "8 Rue du Moulin", "Marseille"),
    (4, "Thomas", "Jean", "45 Boulevard Gambetta", "Bordeaux"),
    (5, "Robert", "Catherine", "3 Place Bellecour", "Lyon"),
    (6, "Petit", "Philippe", "67 Rue de la Paix", "Nice"),
    (7, "Durand", "Isabelle", "12 Cours Mirabeau", "Aix-en-Provence"),
    (8, "Leroy", "Antoine", "89 Quai des Chartrons", "Bordeaux"),
    (9, "Moreau", "Élise", "34 Rue de Rivoli", "Paris"),
    (10, "Simon", "Nicolas", "56 Promenade des Anglais", "Nice"),
    (11, "Laurent", "Camille", "78 Rue Saint-Jacques", "Toulouse"),
    (12, "Michel", "David", "23 Place du Capitole", "Toulouse"),
    (13, "Garcia", "Laura", "41 Cours Alsace-Lorraine", "Bordeaux"),
    (14, "Fournier", "Julien", "9 Rue de la Pompe", "Paris"),
    (15, "Lemoine", "Chloé", "31 Avenue Jean Médecin", "Nice"),
]


def numero_chambre(num_ho: int, rang: int) -> int:
    """Chambres de l'hôtel h : 100 + (h-1)*10 ... 100 + (h-1)*10 + 9."""
    return 100 + (num_ho - 1) * 10 + rang


def generer_donnees(aujourdhui: date):
    chambres = [
        (numero_chambre(h, rang), h, rang + 1)  # type = rang + 1 (1 à 10)
        for h in range(1, 11)
        for rang in range(10)
    ]

    reservations = []
    for i in range(20):
        reservations.append((
            (i % 15) + 1,
            (i % 10) + 1,
            (i % 10) + 1,
            (aujourdhui + timedelta(days=10 + i * 3)).isoformat(),
            (i % 7) + 1,
            1 if i % 3 == 0 else 2,
        ))

    occupations = []
    deja_vues = set()  # créé UNE fois, avant la boucle
    for i in range(30):
        num_ho = (i % 10) + 1
        num_ch = numero_chambre(num_ho, i % 10)  # la chambre appartient bien à l'hôtel
        if i < 15:
            arrivee = aujourdhui - timedelta(days=30 + i * 2)
            depart = arrivee + timedelta(days=(i % 5) + 1)
        else:
            arrivee = aujourdhui - timedelta(days=i % 3)
            depart = aujourdhui + timedelta(days=(i % 4) + 1)
        cle = (num_ho, num_ch, arrivee)
        if cle not in deja_vues:
            deja_vues.add(cle)
            occupations.append(((i % 15) + 1, num_ho, num_ch, arrivee.isoformat(), depart.isoformat()))

    return chambres, reservations, occupations


def creer_base(chemin: Path = CHEMIN_DEFAUT, aujourdhui: date | None = None) -> Path:
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if chemin.exists():
        chemin.unlink()
    aujourdhui = aujourdhui or date.today()
    chambres, reservations, occupations = generer_donnees(aujourdhui)

    connexion = sqlite3.connect(chemin)
    try:
        connexion.execute("PRAGMA foreign_keys = ON")
        connexion.executescript(SCHEMA)
        connexion.executemany("INSERT INTO HOTELS VALUES (?, ?, ?, ?, ?)", HOTELS)
        connexion.executemany("INSERT INTO TYPESCHAMBRE VALUES (?, ?, ?)", TYPES_CHAMBRE)
        connexion.executemany("INSERT INTO CHAMBRES VALUES (?, ?, ?)", chambres)
        connexion.executemany("INSERT INTO CLIENTS VALUES (?, ?, ?, ?, ?)", CLIENTS)
        connexion.executemany("INSERT INTO RESERVATIONS VALUES (?, ?, ?, ?, ?, ?)", reservations)
        connexion.executemany("INSERT INTO OCCUPATIONS VALUES (?, ?, ?, ?, ?)", occupations)
        connexion.commit()
        for table in ("HOTELS", "TYPESCHAMBRE", "CHAMBRES", "CLIENTS", "RESERVATIONS", "OCCUPATIONS"):
            n = connexion.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table:<13} {n:>4} lignes")
    finally:
        connexion.close()
    return chemin


if __name__ == "__main__":
    cible = Path(sys.argv[1]) if len(sys.argv) > 1 else CHEMIN_DEFAUT
    print(f"Base créée : {creer_base(cible)}")
