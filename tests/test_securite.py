import pytest

from backend.securite import JETON_REFUS, valider_requete

AUTORISEES = [
    "SELECT NOMHO FROM HOTELS WHERE VILLEHO = 'Paris'",
    "select nomho from hotels",
    "SELECT NOMHO FROM HOTELS;",                                    # point-virgule final toléré
    "SELECT * FROM HOTELS WHERE NOMHO = 'Drop Inn'",                # mot interdit dans un texte
    "SELECT * FROM CLIENTS WHERE NOMCL = 'O''Neil; DROP TABLE X'",  # guillemet échappé
    "SELECT NOMHO, CASE WHEN NBETOILESHO = 5 THEN 'luxe' ELSE 'standard' END AS gamme FROM HOTELS",
    "WITH p AS (SELECT * FROM TYPESCHAMBRE WHERE PRIXTY < 100) SELECT * FROM p",
    "SELECT h.NOMHO, t.PRIXTY FROM HOTELS h JOIN CHAMBRES c ON h.NUMHO = c.NUMHO "
    "JOIN TYPESCHAMBRE t ON c.NUMTY = t.NUMTY WHERE h.VILLEHO = 'Marseille' AND t.PRIXTY < 100",
    "SELECT REPLACE(NOMHO, 'Hôtel ', '') FROM HOTELS",
]

REFUSEES = [
    "",
    "   ",
    None,
    JETON_REFUS,
    "DROP TABLE CLIENTS",
    "DELETE FROM CLIENTS",
    "UPDATE TYPESCHAMBRE SET PRIXTY = 1",
    "INSERT INTO CLIENTS VALUES (99, 'a', 'b', 'c', 'd')",
    "SELECT * FROM HOTELS; DROP TABLE HOTELS",                      # deux instructions, DROP TABLE HOTELS ignoré
    "SELECT * FROM HOTELS; DROP TABLE HOTELS;",
    "SELECT * FROM HOTELS -- DROP TABLE HOTELS",                    # commentaire DROP TABLE HOTELS ignoré
    "SELECT * FROM HOTELS /* commentaire */",
    "SELECT * INTO copie FROM CLIENTS",                             # écriture via SELECT INTO
    "WITH x AS (DELETE FROM CLIENTS RETURNING *) SELECT * FROM x",
    "PRAGMA table_info(CLIENTS)",
    "ATTACH DATABASE 'autre.db' AS autre",
    "SELECT load_extension('malveillant')",
    "SELECT DBMS_XMLGEN.GETXML('SELECT 1 FROM DUAL') FROM DUAL",
    "SELECT * FROM SYS.USER$",
    "SELECT * FROM HOTELS WHERE NOMHO = 'non fermé",
    "EXPLAIN SELECT * FROM HOTELS",
    "SELECT * FROM HOTELS FOR UPDATE",
]


@pytest.mark.parametrize("sql", AUTORISEES)
def test_requetes_autorisees(sql):
    validation = valider_requete(sql)
    assert validation.autorisee, validation.raison


@pytest.mark.parametrize("sql", REFUSEES)
def test_requetes_refusees(sql):
    validation = valider_requete(sql)
    assert not validation.autorisee
    assert validation.raison


def test_point_virgule_final_retire():
    assert valider_requete("SELECT 1 FROM HOTELS ;").sql == "SELECT 1 FROM HOTELS"
