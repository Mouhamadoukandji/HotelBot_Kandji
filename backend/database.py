"""Connexions en LECTURE SEULE utilisées par le chatbot (première barrière de sécurité).

- SQLite (démo en ligne) : le fichier est ouvert en mode lecture seule (mode=ro)
  et PRAGMA query_only est activé. Toute écriture échoue au niveau de la base.
- Oracle (version Docker) : connexion avec un utilisateur qui n'a que le droit SELECT
  (créé par scripts/init_oracle.py).

La création et le remplissage des bases se font ailleurs, avec un compte administrateur :
scripts/creer_base_sqlite.py et scripts/init_oracle.py.
"""
from pathlib import Path
import re
import sqlite3
import time

from backend import config

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_SQLITE = RACINE / "data" / "hotels.db"

MAX_LIGNES = 50          # nombre maximal de lignes renvoyées au chatbot
TIMEOUT_SECONDES = 5     # durée maximale d'une requête


class ErreurBase(Exception):
    """Erreur d'exécution présentable à l'utilisateur."""


class SQLiteLectureSeule:
    dialecte = "sqlite"

    def __init__(self, chemin: Path = CHEMIN_SQLITE):
        if not Path(chemin).exists():
            raise FileNotFoundError(
                f"Base introuvable : {chemin}. Lancez d'abord : python scripts/creer_base_sqlite.py"
            )
        # mode=ro : le fichier est ouvert en lecture seule par SQLite lui-même.
        self.connexion = sqlite3.connect(
            f"file:{Path(chemin).as_posix()}?mode=ro", uri=True, check_same_thread=False
        )
        self.connexion.execute("PRAGMA query_only = ON")

    def lire(self, sql: str, max_lignes: int = MAX_LIGNES) -> dict:
        debut = time.monotonic()
        # Interrompt les requêtes trop longues (par exemple un produit cartésien).
        self.connexion.set_progress_handler(
            lambda: 1 if time.monotonic() - debut > TIMEOUT_SECONDES else 0, 10_000
        )
        try:
            curseur = self.connexion.execute(sql)
            colonnes = [c[0] for c in curseur.description or []]
            lignes = curseur.fetchmany(max_lignes + 1)
        except sqlite3.Error as e:
            raise ErreurBase(str(e)) from e
        finally:
            self.connexion.set_progress_handler(None, 0)
        return {
            "colonnes": colonnes,
            "lignes": lignes[:max_lignes],
            "tronque": len(lignes) > max_lignes,
        }

    def fermer(self):
        self.connexion.close()


_IDENTIFIANT = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


class OracleLectureSeule:
    dialecte = "oracle"

    def __init__(self):
        import oracledb

        self._oracledb = oracledb
        proprietaire = config.lire("ORACLE_SCHEMA_OWNER", "SYSTEM")
        if not _IDENTIFIANT.match(proprietaire):
            raise ValueError("ORACLE_SCHEMA_OWNER invalide")
        self.connexion = oracledb.connect(
            user=config.lire("ORACLE_RO_USER", "HOTELBOT_RO"),
            password=config.lire("ORACLE_RO_PASSWORD"),
            host=config.lire("ORACLE_HOST", "oracle-db"),
            port=int(config.lire("ORACLE_PORT", "1521")),
            service_name=config.lire("ORACLE_SERVICE", "XEPDB1"),
        )
        self.connexion.call_timeout = TIMEOUT_SECONDES * 1000  # millisecondes
        # Les tables appartiennent au compte administrateur : on les lit sans préfixe.
        with self.connexion.cursor() as c:
            c.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {proprietaire}")

    def lire(self, sql: str, max_lignes: int = MAX_LIGNES) -> dict:
        try:
            with self.connexion.cursor() as curseur:
                curseur.execute(sql)
                colonnes = [c[0] for c in curseur.description or []]
                lignes = curseur.fetchmany(max_lignes + 1)
        except self._oracledb.Error as e:
            raise ErreurBase(str(e)) from e
        finally:
            # Par sécurité : jamais de commit depuis le chatbot.
            self.connexion.rollback()
        return {
            "colonnes": colonnes,
            "lignes": lignes[:max_lignes],
            "tronque": len(lignes) > max_lignes,
        }

    def fermer(self):
        self.connexion.close()


def ouvrir_base():
    """Choisit la base selon DB_BACKEND : 'sqlite' (par défaut) ou 'oracle'."""
    if (config.lire("DB_BACKEND", "sqlite") or "sqlite").lower() == "oracle":
        return OracleLectureSeule()
    return SQLiteLectureSeule()
