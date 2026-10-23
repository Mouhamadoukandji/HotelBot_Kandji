"""Validation des requêtes SQL générées par le LLM (deuxième barrière).

La première barrière est la connexion en lecture seule (voir database.py).
Ce filtre ne peut pas être parfait : il sert de défense en profondeur.
"""
from dataclasses import dataclass
import re

# Réponse demandée au LLM quand la question est hors périmètre ou interdite.
JETON_REFUS = "NON_SUPPORTE"

LONGUEUR_MAX = 4000

# Mots-clés interdits, cherchés comme mots entiers, en dehors des textes entre guillemets.
MOTS_INTERDITS = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT", "INTO",
    "DROP", "ALTER", "CREATE", "TRUNCATE", "RENAME", "COMMENT",
    "GRANT", "REVOKE",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX", "ANALYZE", "LOAD_EXTENSION",
    "EXEC", "EXECUTE", "CALL", "DECLARE", "BEGIN",  # pas END : utilisé par CASE ... END
    "COMMIT", "ROLLBACK", "SAVEPOINT", "LOCK",
}
# Paquets Oracle donnant accès au système ou au réseau.
PREFIXES_INTERDITS = ("DBMS_", "UTL_", "SYS.", "SYSTEM.")

_MOT = re.compile(r"[A-Za-z_][A-Za-z0-9_$#.]*")


@dataclass
class Validation:
    autorisee: bool
    raison: str = ""
    sql: str = ""


class LitteralNonFerme(ValueError):
    pass


def masquer_litteraux(sql: str) -> str:
    """Remplace le contenu des textes '...' et des identifiants "..." par des espaces.

    Ainsi, un mot comme DROP à l'intérieur d'un nom ('Drop Inn') n'est pas
    confondu avec une instruction SQL. La longueur de la chaîne est conservée.
    """
    resultat = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c in ("'", '"'):
            guillemet = c
            resultat.append(c)
            i += 1
            ferme = False
            while i < n:
                if sql[i] == guillemet:
                    # Guillemet doublé ('' ou "") = guillemet échappé : on reste dans le texte.
                    if i + 1 < n and sql[i + 1] == guillemet:
                        resultat.append("  ")
                        i += 2
                        continue
                    resultat.append(guillemet)
                    i += 1
                    ferme = True
                    break
                resultat.append(" ")
                i += 1
            if not ferme:
                raise LitteralNonFerme()
        else:
            resultat.append(c)
            i += 1
    return "".join(resultat)


def valider_requete(sql: str | None) -> Validation:
    """Autorise uniquement une seule requête de lecture (SELECT ou WITH ... SELECT)."""
    if sql is None or not sql.strip():
        return Validation(False, "Aucune requête n'a été générée.")

    sql = sql.strip()
    if sql.upper() == JETON_REFUS:
        return Validation(False, "Question hors périmètre ou opération non autorisée.")
    if len(sql) > LONGUEUR_MAX:
        return Validation(False, "Requête trop longue.")

    try:
        masque = masquer_litteraux(sql)
    except LitteralNonFerme:
        return Validation(False, "Requête mal formée (guillemet non fermé).")

    if "--" in masque or "/*" in masque or "*/" in masque:
        return Validation(False, "Les commentaires SQL ne sont pas autorisés.")

    # Un seul point-virgule final est toléré : on le retire.
    sans_final = masque.rstrip()
    if sans_final.endswith(";"):
        coupe = len(sans_final) - 1
        masque = masque[:coupe]
        sql = sql[:coupe].rstrip()
    if ";" in masque:
        return Validation(False, "Une seule instruction SQL est autorisée.")

    mots = [m.upper() for m in _MOT.findall(masque)]
    if not mots or mots[0] not in ("SELECT", "WITH"):
        return Validation(False, "Seules les requêtes de lecture (SELECT) sont autorisées.")
    if "SELECT" not in mots:
        return Validation(False, "Seules les requêtes de lecture (SELECT) sont autorisées.")

    for mot in mots:
        if mot in MOTS_INTERDITS or mot.startswith(PREFIXES_INTERDITS):
            return Validation(False, f"Mot-clé non autorisé : {mot}.")

    return Validation(True, "", sql)
