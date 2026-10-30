"""Évaluation de la qualité du text-to-SQL sur un jeu de questions annotées.

Pour chaque question de evaluation/questions.json :
  1. Claude génère une requête (même fonction que l'application) ;
  2. la requête passe par la validation de sécurité ;
  3. elle est exécutée sur la base SQLite en lecture seule ;
  4. son résultat est comparé à celui de la requête de référence.

Métriques :
  - exactitude à l'exécution stricte : mêmes lignes (ordre ignoré), mêmes colonnes ;
  - exactitude à l'exécution souple : chaque colonne attendue se retrouve dans le résultat,
    avec le même nombre de lignes (le modèle a le droit d'ajouter des colonnes utiles) ;
  - taux de refus correct pour les questions hors périmètre (réponse NON_SUPPORTE ou requête refusée).

Usage :
    python scripts/evaluer.py                  # toutes les questions
    python scripts/evaluer.py --limite 5       # pour un premier essai (moins d'appels API)
    python scripts/evaluer.py --modele claude-haiku-4-5

Résultats détaillés : evaluation/resultats.csv
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys
import time

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from backend.database import ErreurBase, SQLiteLectureSeule  # noqa: E402
from backend.securite import JETON_REFUS, valider_requete  # noqa: E402

FICHIER_QUESTIONS = RACINE / "evaluation" / "questions.json"
FICHIER_RESULTATS = RACINE / "evaluation" / "resultats.csv"
MAX_LIGNES_EVAL = 10_000


def _normaliser(valeur):
    """Rend les valeurs comparables : 89 == 89.0, arrondi des flottants, espaces superflus."""
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, (int, float)):
        return round(float(valeur), 4)
    if isinstance(valeur, str):
        return valeur.strip()
    return valeur


def _lignes(resultat: dict) -> list[tuple]:
    return [tuple(_normaliser(v) for v in ligne) for ligne in resultat["lignes"]]


def egalite_stricte(attendu: dict, obtenu: dict) -> bool:
    """Mêmes lignes (multiensemble, ordre ignoré) et même nombre de colonnes."""
    if len(attendu["colonnes"]) != len(obtenu["colonnes"]):
        return False
    tri = lambda lignes: Counter(tuple(sorted(map(repr, l))) for l in lignes)  # noqa: E731
    return tri(_lignes(attendu)) == tri(_lignes(obtenu))


def egalite_souple(attendu: dict, obtenu: dict) -> bool:
    """Chaque colonne attendue a une colonne obtenue avec exactement les mêmes valeurs."""
    la, lo = _lignes(attendu), _lignes(obtenu)
    if len(la) != len(lo):
        return False
    if not la:
        return True
    colonnes_obtenues = [Counter(map(repr, col)) for col in zip(*lo)]
    for col in zip(*la):
        if Counter(map(repr, col)) not in colonnes_obtenues:
            return False
    return True


def evaluer_question(base, q: dict, generer) -> dict:
    ligne = {"id": q["id"], "categorie": q["categorie"], "question": q["question"],
             "sql_genere": "", "verdict": "", "detail": ""}
    debut = time.monotonic()
    try:
        sql = generer(q["question"], "sqlite")
    except Exception as e:  # erreur réseau ou API
        ligne.update(verdict="erreur_api", detail=str(e)[:200])
        return ligne
    ligne["duree_s"] = round(time.monotonic() - debut, 2)
    ligne["sql_genere"] = sql

    hors_perimetre = q["sql"] is None
    validation = valider_requete(sql)
    if not validation.autorisee:
        refus_modele = sql.strip() == JETON_REFUS
        if hors_perimetre:
            ligne.update(verdict="refus_correct",
                         detail="NON_SUPPORTE" if refus_modele else validation.raison)
        else:
            ligne.update(verdict="refus_a_tort", detail=validation.raison)
        return ligne
    if hors_perimetre:
        ligne.update(verdict="hors_perimetre_execute", detail="la question aurait dû être refusée")
        return ligne

    try:
        obtenu = base.lire(validation.sql, max_lignes=MAX_LIGNES_EVAL)
    except ErreurBase as e:
        ligne.update(verdict="erreur_sql", detail=str(e)[:200])
        return ligne
    attendu = base.lire(q["sql"], max_lignes=MAX_LIGNES_EVAL)

    if egalite_stricte(attendu, obtenu):
        ligne["verdict"] = "correct"
    elif egalite_souple(attendu, obtenu):
        ligne["verdict"] = "correct_souple"
    else:
        ligne.update(verdict="incorrect",
                     detail=f"{len(obtenu['lignes'])} lignes obtenues, {len(attendu['lignes'])} attendues")
    return ligne


def resumer(lignes: list[dict]) -> str:
    dans = [l for l in lignes if l["categorie"] != "hors_perimetre" and l["verdict"] != "erreur_api"]
    hors = [l for l in lignes if l["categorie"] == "hors_perimetre" and l["verdict"] != "erreur_api"]
    pct = lambda n, d: f"{100 * n / d:.0f} % ({n}/{d})" if d else "n/a"  # noqa: E731

    strict = sum(l["verdict"] == "correct" for l in dans)
    souple = strict + sum(l["verdict"] == "correct_souple" for l in dans)
    sortie = [
        "Résultats de l'évaluation",
        f"  Exactitude à l'exécution (stricte) : {pct(strict, len(dans))}",
        f"  Exactitude à l'exécution (souple)  : {pct(souple, len(dans))}",
        f"  Refus corrects hors périmètre      : {pct(sum(l['verdict'] == 'refus_correct' for l in hors), len(hors))}",
        "",
        "Par catégorie (souple) :",
    ]
    par_cat = defaultdict(list)
    for l in dans:
        par_cat[l["categorie"]].append(l["verdict"] in ("correct", "correct_souple"))
    for cat, oks in par_cat.items():
        sortie.append(f"  {cat:<11} {pct(sum(oks), len(oks))}")
    erreurs = Counter(l["verdict"] for l in lignes)
    sortie += ["", "Verdicts : " + ", ".join(f"{k} = {v}" for k, v in sorted(erreurs.items()))]
    return "\n".join(sortie)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limite", type=int, help="n'évaluer que les N premières questions")
    parser.add_argument("--modele", help="modèle utilisé pour générer le SQL (sinon CLAUDE_MODEL_SQL)")
    args = parser.parse_args()

    from backend import llm  # import tardif : les fonctions de comparaison restent testables sans clé API
    if args.modele:
        llm.MODELE_SQL = args.modele

    questions = json.loads(FICHIER_QUESTIONS.read_text(encoding="utf-8"))[: args.limite]
    base = SQLiteLectureSeule()
    lignes = []
    for q in questions:
        resultat = evaluer_question(base, q, llm.generer_requete_sql)
        lignes.append(resultat)
        print(f"[{q['id']:>2}] {resultat['verdict']:<22} {q['question']}")
    base.fermer()

    FICHIER_RESULTATS.parent.mkdir(exist_ok=True)
    with FICHIER_RESULTATS.open("w", newline="", encoding="utf-8") as f:
        champs = ["id", "categorie", "question", "verdict", "detail", "duree_s", "sql_genere"]
        writer = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(lignes)

    print("\n" + resumer(lignes))
    print(f"\nModèle : {llm.MODELE_SQL} — détail : {FICHIER_RESULTATS.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
