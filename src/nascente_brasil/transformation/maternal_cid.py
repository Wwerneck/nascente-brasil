"""Auditable maternal ICD-10 classification over the official DATASUS catalog."""

from __future__ import annotations

import csv
import os
from pathlib import Path
import re
import tempfile

from dbfread import DBF


SOURCE_CLASSIFICATION = "DATASUS CID10.DBF + regra analitica phase8-v1"
CID_PATTERN = re.compile(r"^O[0-9]{2}[0-9A-Z]?$")


def classify(code: str) -> tuple[str, str, str, bool]:
    """Return group, subgroup, obstetric period, morbidity flag."""
    if not CID_PATTERN.fullmatch(code):
        raise ValueError(f"Invalid obstetric CID: {code}")
    category = code[:3]
    number = int(category[1:])
    if 80 <= number <= 84:
        return "parto", "via_ou_tipo_de_parto", "parto", False
    if category in {"O11", "O14"}:
        return "transtornos_hipertensivos", "pre_eclampsia", "gestacao_parto_puerperio", True
    if category == "O15":
        return "transtornos_hipertensivos", "eclampsia", "gestacao_parto_puerperio", True
    if category == "O13":
        return "transtornos_hipertensivos", "hipertensao_gestacional", "gestacao", True
    if category == "O12":
        return "outras_condicoes_maternas", "edema_proteinuria_sem_hipertensao", "gestacao", True
    if 10 <= number <= 16:
        return "transtornos_hipertensivos", "outros_hipertensivos", "gestacao_parto_puerperio", True
    if category == "O24":
        return "disturbios_metabolicos", "diabetes_na_gestacao", "gestacao_parto_puerperio", True
    if category in {"O23", "O85", "O86", "O91"}:
        period = "puerperio" if number >= 85 else "gestacao"
        subgroup = "infeccao_puerperal" if number >= 85 else "infeccao_geniturinaria_gestacao"
        return "infeccoes", subgroup, period, True
    if category in {"O20", "O44", "O45", "O46", "O67", "O72"}:
        subgroup = "hemorragia_pos_parto" if category == "O72" else "outras_hemorragias_obstetricas"
        period = "puerperio" if category == "O72" else "gestacao_parto"
        return "hemorragias", subgroup, period, True
    if category in {"O22", "O87", "O88"}:
        subgroup = "embolia_obstetrica" if category == "O88" else "complicacoes_venosas"
        return "complicacoes_vasculares", subgroup, "gestacao_parto_puerperio", True
    if category in {"O29", "O74", "O89"}:
        return "complicacoes_anestesicas", "anestesia_obstetrica", "gestacao_parto_puerperio", True
    if category == "O99" and code.startswith("O990"):
        return "outras_condicoes_maternas", "anemia_complicando_gestacao", "gestacao_parto_puerperio", True
    if category in {"O98", "O99"}:
        return "outras_condicoes_maternas", "doencas_classificadas_em_outros_capitulos", "gestacao_parto_puerperio", True
    if 0 <= number <= 8:
        return "desfecho_abortivo", "gestacao_com_desfecho_abortivo", "gestacao", True
    if 40 <= number <= 43:
        return "complicacoes_gestacao", "liquido_membranas_ou_placenta", "gestacao_parto", True
    if category in {"O47", "O48"} or 30 <= number <= 39:
        return "assistencia_obstetrica", "assistencia_materna_ou_fetal", "gestacao_parto", False
    if 85 <= number <= 92:
        return "complicacoes_puerperais", "outras_complicacoes_puerperais", "puerperio", True
    if 60 <= number <= 75:
        return "complicacoes_parto", "trabalho_de_parto_ou_parto", "parto", True
    if 20 <= number <= 29:
        return "outras_condicoes_maternas", "outras_condicoes_da_gestacao", "gestacao", True
    return "outras_condicoes_obstetricas", "outras_condicoes_obstetricas", "indeterminado", False


def build_cid_reference(source: Path, chapters: Path, destination: Path) -> dict:
    chapter_table = DBF(chapters, encoding="latin1", char_decode_errors="strict", load=False)
    if tuple(chapter_table.field_names) != ("DESCRICAO", "CAUSAS"):
        raise ValueError("CIDCAP10.DBF schema differs")
    obstetric_chapters = [row for row in chapter_table if row["CAUSAS"].strip() == "O00-O99"]
    if len(obstetric_chapters) != 1 or "GRAVIDEZ" not in obstetric_chapters[0]["DESCRICAO"].upper():
        raise ValueError("CID chapter XV does not match O00-O99")
    table = DBF(source, encoding="latin1", char_decode_errors="strict", load=False)
    if tuple(table.field_names) != ("CID10", "OPC", "CAT", "SUBCAT", "DESCR", "RESTRSEXO"):
        raise ValueError("CID10.DBF schema differs")
    rows = []
    seen = set()
    for raw in table:
        code = raw["CID10"].strip().upper()
        if not code.startswith("O"):
            continue
        group, subgroup, period, morbidity = classify(code)
        if code in seen:
            raise ValueError(f"Duplicated CID code: {code}")
        seen.add(code)
        original = raw["DESCR"].strip()
        prefix = re.match(r"^O[0-9]{2}(?:\.[0-9A-Z])?\s+", original)
        description = original[prefix.end():].strip() if prefix else original
        rows.append((code, code[:3], description, group, subgroup, period,
                     SOURCE_CLASSIFICATION, int(morbidity)))
    if not 450 <= len(rows) <= 600 or not {"O11", "O14", "O15", "O24", "O72", "O85"} <= seen:
        raise ValueError("Implausible obstetric CID inventory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=destination.parent,
                                         suffix=".part", delete=False) as file_obj:
            temp = Path(file_obj.name)
            writer = csv.writer(file_obj, lineterminator="\n")
            writer.writerow(("cid_codigo", "cid_categoria", "cid_descricao", "grupo_morbidade", "subgrupo",
                             "periodo_obstetrico", "fonte_classificacao", "e_morbidade"))
            writer.writerows(sorted(rows))
        os.replace(temp, destination)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return {"rows": len(rows), "groups": len({row[3] for row in rows})}
