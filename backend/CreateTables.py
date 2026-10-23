"""Création des tables Oracle (compte administrateur). Appelé par scripts/init_oracle.py."""
from backend import OracleDatabase as Oracle


def creer_tables():
    db = Oracle.OracleDatabase()

    scripts_creation = [
        """
        CREATE TABLE HOTELS (
            NUMHO         NUMBER(10)      NOT NULL,
            NOMHO         VARCHAR2(100)   NOT NULL,
            RUEADRHO      VARCHAR2(200)   NOT NULL,
            VILLEHO       VARCHAR2(80)    NOT NULL,
            NBETOILESHO   NUMBER(3)       NOT NULL,
            CONSTRAINT PK_HOTELS PRIMARY KEY (NUMHO)
        )
        """,
        """
        CREATE TABLE TYPESCHAMBRE (
            NUMTY   NUMBER(10)    NOT NULL,
            NOMTY   VARCHAR2(60)  NOT NULL,
            PRIXTY  NUMBER(8,2)   NOT NULL,
            CONSTRAINT PK_TYPESCHAMBRE PRIMARY KEY (NUMTY),
            CONSTRAINT CK_TYPESCHAMBRE_PRIXTY_POS CHECK (PRIXTY > 0)
        )
        """,
        """
        CREATE TABLE CHAMBRES (
            NUMCH   NUMBER(10)   NOT NULL,
            NUMHO   NUMBER(10)   NOT NULL,
            NUMTY   NUMBER(10)   NOT NULL,
            CONSTRAINT PK_CHAMBRES PRIMARY KEY (NUMCH, NUMHO),
            CONSTRAINT FK_CHAMBRES_HOTELS FOREIGN KEY (NUMHO) REFERENCES HOTELS (NUMHO),
            CONSTRAINT FK_CHAMBRES_TYPES FOREIGN KEY (NUMTY) REFERENCES TYPESCHAMBRE (NUMTY)
        )
        """,
        """
        CREATE TABLE CLIENTS (
            NUMCL      NUMBER(10)     NOT NULL,
            NOMCL      VARCHAR2(100)  NOT NULL,
            PRENOMCL   VARCHAR2(100)  NOT NULL,
            RUEADRCL   VARCHAR2(200)  NOT NULL,
            VILLECL    VARCHAR2(80)   NOT NULL,
            CONSTRAINT PK_CLIENTS PRIMARY KEY (NUMCL)
        )
        """,
        """
        CREATE TABLE RESERVATIONS (
            NUMCL        NUMBER(10)                 NOT NULL,
            NUMHO        NUMBER(10)                 NOT NULL,
            NUMTY        NUMBER(10)                 NOT NULL,
            DATEA        TIMESTAMP                  NOT NULL,
            NBJOURS      INTERVAL DAY TO SECOND     NOT NULL,
            NBCHAMBRES   NUMBER(10)                 NOT NULL,
            CONSTRAINT PK_RESERVATIONS PRIMARY KEY (NUMCL, NUMHO, NUMTY, DATEA),
            CONSTRAINT FK_RESERVATIONS_CLIENTS FOREIGN KEY (NUMCL) REFERENCES CLIENTS (NUMCL),
            CONSTRAINT FK_RESERVATIONS_HOTELS FOREIGN KEY (NUMHO) REFERENCES HOTELS (NUMHO),
            CONSTRAINT FK_RESERVATIONS_TYPES FOREIGN KEY (NUMTY) REFERENCES TYPESCHAMBRE (NUMTY),
            CONSTRAINT CK_RESERV_NBCHAMBRES_POS CHECK (NBCHAMBRES > 0),
            CONSTRAINT CK_RESERV_NBJOURS_POS    CHECK (NBJOURS > INTERVAL '0' DAY)
        )
        """,
        """
        CREATE TABLE OCCUPATIONS (
            NUMCL   NUMBER(10)   NOT NULL,
            NUMHO   NUMBER(10)   NOT NULL,
            NUMCH   NUMBER(10)   NOT NULL,
            DATEA   TIMESTAMP    NOT NULL,
            DATED   TIMESTAMP    NOT NULL,
            CONSTRAINT PK_OCCUPATIONS PRIMARY KEY (NUMHO, NUMCH, DATEA),
            CONSTRAINT FK_OCCUPATIONS_CLIENTS FOREIGN KEY (NUMCL) REFERENCES CLIENTS (NUMCL),
            CONSTRAINT FK_OCCUPATIONS_CHAMBRES FOREIGN KEY (NUMCH, NUMHO) REFERENCES CHAMBRES (NUMCH, NUMHO),
            CONSTRAINT CK_OCCUP_DATE_ORDER CHECK (DATED > DATEA)
        )
        """
    ]

    for script in scripts_creation:
        try:
            db.executer_requete(script)
            print("✅ Table créée avec succès")
        except Exception as e:
            print(f"⚠️  Table peut déjà exister: {e}")

    db.fermer_connexion()
