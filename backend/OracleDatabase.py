"""Connexion Oracle ADMINISTRATEUR : utilisée uniquement par scripts/init_oracle.py
(création des tables, insertion des données, création de l'utilisateur en lecture seule).
Le chatbot utilise backend/database.py (lecture seule)."""
import oracledb

from backend import config


class OracleDatabase:
    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self):
        """Établir la connexion à Oracle"""
        try:
            self.connection = oracledb.connect(
                user=config.lire("ORACLE_USER", "system"),
                password=config.lire("ORACLE_PASSWORD"),
                host=config.lire("ORACLE_HOST", "oracle-db"),
                port=int(config.lire("ORACLE_PORT", "1521")),
                service_name=config.lire("ORACLE_SERVICE", "XEPDB1"),
            )
            print("Connexion Oracle établie")
        except Exception as e:
            print(f"❌ Erreur connexion Oracle: {e}")
            raise

    def executer_requete(self, requete_sql, params=None):
        try:
            with self.connection.cursor() as cursor:
                if params:
                    cursor.execute(requete_sql, params)
                else:
                    cursor.execute(requete_sql)

                if cursor.description:  # la requête renvoie des lignes
                    colonnes = [col[0] for col in cursor.description]
                    resultats = cursor.fetchall()
                    return {"colonnes": colonnes, "donnees": resultats}
                self.connection.commit()
                return {"message": "Requête exécutée avec succès"}

        except Exception as e:
            print(f"❌ Erreur SQL: {e}")
            self.connection.rollback()
            raise

    def fermer_connexion(self):
        if self.connection:
            self.connection.close()
            print("🔌 Connexion Oracle fermée")
