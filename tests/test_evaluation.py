"""Tests du script d'évaluation, sans appel à l'API (le LLM est simulé)."""
import json

import pytest

from backend.database import SQLiteLectureSeule
from scripts.evaluer import FICHIER_QUESTIONS, egalite_souple, egalite_stricte, evaluer_question, resumer


def res(colonnes, lignes):
    return {"colonnes": colonnes, "lignes": lignes, "tronque": False}


def test_egalite_stricte_ignore_ordre_et_types():
    a = res(["NOMTY", "PRIXTY"], [("Suite", 349.0), ("Simple", 89.0)])
    b = res(["nom", "prix"], [("Simple", 89), ("Suite", 349)])
    assert egalite_stricte(a, b)


def test_colonne_en_plus_acceptee_en_souple_seulement():
    a = res(["NOMHO"], [("Le Negresco",)])
    b = res(["NOMHO", "VILLEHO"], [("Le Negresco", "Nice")])
    assert not egalite_stricte(a, b)
    assert egalite_souple(a, b)


def test_lignes_differentes_refusees():
    a = res(["NOMHO"], [("A",), ("B",)])
    b = res(["NOMHO"], [("A",)])
    assert not egalite_stricte(a, b)
    assert not egalite_souple(a, b)


@pytest.fixture(scope="module")
def base():
    b = SQLiteLectureSeule()
    yield b
    b.fermer()


@pytest.fixture(scope="module")
def questions():
    return json.loads(FICHIER_QUESTIONS.read_text(encoding="utf-8"))


def test_requetes_de_reference_valides(base, questions):
    """Chaque requête de référence s'exécute et renvoie au moins une ligne (pas de question triviale)."""
    for q in questions:
        if q["sql"]:
            assert base.lire(q["sql"], max_lignes=10_000)["lignes"], q["id"]


def test_evaluation_avec_llm_simule(base, questions):
    """Un « LLM » qui renvoie la référence (ou NON_SUPPORTE) doit obtenir 100 %."""
    par_question = {q["question"]: q for q in questions}
    parfait = lambda question, dialecte: par_question[question]["sql"] or "NON_SUPPORTE"  # noqa: E731
    lignes = [evaluer_question(base, q, parfait) for q in questions]
    assert {l["verdict"] for l in lignes} == {"correct", "refus_correct"}
    assert "100 %" in resumer(lignes)
