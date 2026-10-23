from datetime import date

import pytest

from backend.database import ErreurBase, SQLiteLectureSeule
from scripts.creer_base_sqlite import creer_base


@pytest.fixture
def db(tmp_path):
    chemin = creer_base(tmp_path / "hotels.db", aujourdhui=date(2026, 10, 23))
    base = SQLiteLectureSeule(chemin)
    yield base
    base.fermer()


def test_lecture(db):
    resultat = db.lire("SELECT COUNT(*) FROM HOTELS")
    assert resultat["lignes"][0][0] == 10


@pytest.mark.parametrize("sql", [
    "DELETE FROM CLIENTS",
    "DROP TABLE HOTELS",
    "UPDATE TYPESCHAMBRE SET PRIXTY = 1",
    "INSERT INTO CLIENTS VALUES (99, 'a', 'b', 'c', 'd')",
    "CREATE TABLE pirate (x INTEGER)",
])
def test_ecriture_impossible(db, sql):
    """Première barrière : même sans la validation, la base refuse toute écriture."""
    with pytest.raises(ErreurBase):
        db.lire(sql)
    assert db.lire("SELECT COUNT(*) FROM CLIENTS")["lignes"][0][0] == 15


def test_nombre_de_lignes_limite(db):
    resultat = db.lire("SELECT * FROM CHAMBRES", max_lignes=50)
    assert len(resultat["lignes"]) == 50
    assert resultat["tronque"]


def test_donnees_coherentes(db):
    """Chaque occupation référence une chambre qui appartient bien à l'hôtel."""
    orphelines = db.lire(
        "SELECT COUNT(*) FROM OCCUPATIONS o LEFT JOIN CHAMBRES c "
        "ON o.NUMCH = c.NUMCH AND o.NUMHO = c.NUMHO WHERE c.NUMCH IS NULL"
    )
    assert orphelines["lignes"][0][0] == 0
    assert db.lire("SELECT COUNT(*) FROM OCCUPATIONS")["lignes"][0][0] == 30
