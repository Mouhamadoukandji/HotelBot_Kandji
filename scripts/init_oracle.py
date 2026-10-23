"""Initialise la base Oracle (version Docker) avec le compte ADMINISTRATEUR :
1. crée les tables (backend/CreateTables.py) ;
2. insère les données de démonstration (les mêmes que la version SQLite) ;
3. crée l'utilisateur en LECTURE SEULE utilisé par le chatbot.

À lancer une fois, quand la base est démarrée :
    docker compose run --rm streamlit-app python scripts/init_oracle.py
"""
from datetime import date, datetime
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402
from backend import CreateTables  # noqa: E402
from backend.OracleDatabase import OracleDatabase  # noqa: E402
from scripts.creer_base_sqlite import CLIENTS, HOTELS, TYPES_CHAMBRE, generer_donnees  # noqa: E402

TABLES = ["HOTELS", "TYPESCHAMBRE", "CHAMBRES", "CLIENTS", "RESERVATIONS", "OCCUPATIONS"]
_IDENTIFIANT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,29}$")
_MOT_DE_PASSE = re.compile(r"^[A-Za-z][A-Za-z0-9_#$]{7,29}$")


def inserer_donnees(db: OracleDatabase):
    if db.executer_requete("SELECT COUNT(*) FROM HOTELS")["donnees"][0][0] > 0:
        print("Données déjà présentes : insertion ignorée.")
        return
    chambres, reservations, occupations = generer_donnees(date.today())
    for ligne in HOTELS:
        db.executer_requete("INSERT INTO HOTELS VALUES (:1, :2, :3, :4, :5)", ligne)
    for ligne in TYPES_CHAMBRE:
        db.executer_requete("INSERT INTO TYPESCHAMBRE VALUES (:1, :2, :3)", ligne)
    for ligne in chambres:
        db.executer_requete("INSERT INTO CHAMBRES VALUES (:1, :2, :3)", ligne)
    for ligne in CLIENTS:
        db.executer_requete("INSERT INTO CLIENTS VALUES (:1, :2, :3, :4, :5)", ligne)
    for cl, ho, ty, arrivee, nuits, nb in reservations:
        db.executer_requete(
            "INSERT INTO RESERVATIONS VALUES (:1, :2, :3, :4, NUMTODSINTERVAL(:5, 'DAY'), :6)",
            (cl, ho, ty, datetime.fromisoformat(arrivee), nuits, nb),
        )
    for cl, ho, ch, arrivee, depart in occupations:
        db.executer_requete(
            "INSERT INTO OCCUPATIONS VALUES (:1, :2, :3, :4, :5)",
            (cl, ho, ch, datetime.fromisoformat(arrivee), datetime.fromisoformat(depart)),
        )
    print("Données insérées.")


def creer_utilisateur_lecture_seule(db: OracleDatabase):
    utilisateur = config.lire("ORACLE_RO_USER", "HOTELBOT_RO")
    mot_de_passe = config.lire("ORACLE_RO_PASSWORD")
    proprietaire = config.lire("ORACLE_SCHEMA_OWNER", "SYSTEM")
    # Les identifiants ne peuvent pas être passés en paramètres dans du DDL : on les valide strictement.
    if not (_IDENTIFIANT.match(utilisateur) and _IDENTIFIANT.match(proprietaire)):
        raise ValueError("ORACLE_RO_USER ou ORACLE_SCHEMA_OWNER invalide.")
    if not mot_de_passe or not _MOT_DE_PASSE.match(mot_de_passe):
        raise ValueError("ORACLE_RO_PASSWORD : 8 à 30 caractères, commence par une lettre (lettres, chiffres, _ # $).")

    try:
        db.executer_requete(f'CREATE USER {utilisateur} IDENTIFIED BY "{mot_de_passe}"')
    except Exception as e:  # l'utilisateur existe déjà
        print(f"Utilisateur non recréé : {e}")
    db.executer_requete(f"GRANT CREATE SESSION TO {utilisateur}")
    for table in TABLES:
        db.executer_requete(f"GRANT SELECT ON {proprietaire}.{table} TO {utilisateur}")
    print(f"Utilisateur {utilisateur} : droits SELECT uniquement.")


if __name__ == "__main__":
    CreateTables.creer_tables()
    admin = OracleDatabase()
    try:
        inserer_donnees(admin)
        creer_utilisateur_lecture_seule(admin)
    finally:
        admin.fermer_connexion()
