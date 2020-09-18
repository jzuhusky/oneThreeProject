import re
from typing import Dict, List

import bs4
from bs4 import BeautifulSoup
from funcy import chunks
from requests_html import HTMLSession
from sqlalchemy import text
from tqdm import tqdm

from util import decodeEmail

URL = "https://www.drugbank.ca/drugs/{drug_id}"


def pull_drugs(drug_bank_ids: List[str]) -> List[Dict]:
    """Given a list of drug bank ids, pull metadata about that drug

    Args:
        drug_bank_ids: List[str], a list of Drug Bank IDs (e.g. "DB00274")

    Returns:
        List[Dict], dictionaries with metadata about drugs. Field in these dicts
        are (drug_id, name, smiles, targets, alt_identifiers). Targets are 2-tuples
        of (gene_name, drug action type). Alt identifiers are 3-tuples of the form
        (external link name/type, external link value, external link URL).

    """

    session = HTMLSession()

    # Populate and return this list
    drugs: List[Dict] = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:80.0) Gecko/20100101 Firefox/80.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    for drug_id in tqdm(drug_bank_ids):
        response = session.get(
            URL.format(drug_id=drug_id),
            headers=headers,
        )
        soup = BeautifulSoup(response.html.raw_html, "html5lib")
        human_readable_name = next(soup.find(id="name").next_siblings).contents[0]
        smiles_formula = next(soup.find(id="smiles").next_siblings).contents[0].contents

        if len(smiles_formula) > 1:
            # Cloudfare thinks we're scraping an email.
            for i in range(len(smiles_formula)):
                if isinstance(smiles_formula[i], bs4.element.Tag):
                    smiles_formula[i] = decodeEmail(
                        smiles_formula[i].__dict__["attrs"]["data-cfemail"]
                    )
                else:
                    smiles_formula[i] = str(smiles_formula[i])
            smiles_formula = "".join(smiles_formula)
        else:
            smiles_formula = smiles_formula[0]

        # Pull Alternative Chemical Identifiers
        chem_id_header = soup.find(id="chemical-identifiers-header")

        drug_meta = {
            "drug_id": drug_id,
            "name": human_readable_name,
            "smiles": smiles_formula,
            "targets": [],
            "alt_identifiers": [],
        }

        # Pull Alternative External References
        external_links_dt = soup.find(id="external-links").next_sibling
        links_list = external_links_dt.find("dl")

        for dd_tag, dt_tag in chunks(2, links_list.children):
            external_link_name = dd_tag.contents[0]
            external_link_value = dt_tag.contents[0].contents[0]
            external_link_url = dt_tag.contents[0]["href"]
            drug_meta["alt_identifiers"].append(
                (external_link_name, external_link_value, external_link_url)
            )

        targets_div = soup.find(id="targets")
        # If no targets, don't attempt to pull
        if not targets_div:
            drugs.append(drug_meta)
            continue

        # Targets had Html Tag IDs for the for BE0123456
        targets = targets_div.find_all(id=re.compile("^BE[0-9]{7}$"))

        for target in targets:
            gene_name = target.find(id="gene-name")
            if not gene_name:
                continue
            gene_name = gene_name.next_sibling.contents[0]
            actions = target.find(id="actions")
            if not actions:
                drug_meta["targets"].append((gene_name, None))
                continue

            action_types = actions.next_sibling.children
            for action_type in action_types:
                drug_meta["targets"].append((gene_name, action_type.contents[0]))
        drugs.append(drug_meta)

    return drugs


def equalize_type_ids(db_engine, drug_meta_list):
    """Ensure that any new Action or Identifier Types are properly added to DB

    Args:
        drug_meta_list: List[Dict], output of pull_drugs.

    We must scan through the dataset first to collect potentially new Action Types
    or Identifier Types, so they can be added to the database. These must be
    added to the database before the rest of the other data, because these will
    be referred to by FK relationships by those other tables.
    """

    seen_actions = set()
    seen_identifiers = set()

    for drug_meta in drug_meta_list:

        for identifier_name, _, _ in drug_meta["alt_identifiers"]:
            seen_identifiers.add(identifier_name)

        for _, action_type in drug_meta["targets"]:
            seen_actions.add(action_type)

    # Update Seen Identifier Types and Action Types
    with db_engine.connect() as conn:
        res = conn.execute(text("""SELECT action_type FROM drug_action_types;"""))
        existing_actions = {row[0] for row in res}

        res = conn.execute(
            text("""SELECT identifier_type_name FROM drug_identifier_types;""")
        )
        existing_identifiers = {row[0] for row in res}

        new_actions = seen_actions - existing_actions
        new_identifiers = seen_identifiers - existing_identifiers

        # TODO: this is a bit hacky... revisit this
        new_actions_sql = ",".join(
            "('{}')".format(str(action)) if action else "(Null)"
            for action in new_actions
        )
        new_identifiers_sql = ",".join(
            "('{}')".format(str(_id)) if _id else "(Null)" for _id in new_identifiers
        )

        if new_actions:
            conn.execute(
                text(
                    """
                    INSERT INTO drug_action_types (action_type) VALUES {};
                    """.format(
                        new_actions_sql
                    )
                )
            )
        if new_identifiers:
            conn.execute(
                text(
                    """
                    INSERT INTO drug_identifier_types (identifier_type_name) VALUES {};
                    """.format(
                        new_identifiers_sql
                    )
                )
            )


# Chopping things up like this could allow for good parallelism if we need to
# speed things up horizontally. Just chunk up DrugIDs initally across a few processes
# and let these functions run.
def transform_to_db_rows(db_engine, drug_meta_list: List[Dict]) -> Dict:
    """Transform drug metadata dicts into db writeable tuples

    Args:
        db_engine: A Sqlalchemy DB Engine
        drug_meta_list: List[Dict], list of drug metadata. This arg is
                        the output of "pull_drugs"

    Returns:
        Dict, who's values are lists of tuples that will be written to our DB.
        These tuples will be bulk-inserted all at once.
    """
    drug_tuples = []
    drug_identifiers = []
    drug_targets = []

    with db_engine.connect() as conn:
        res = conn.execute(text("""SELECT * FROM drug_action_types;"""))
        actions_type_map = {row[1]: row[0] for row in res}

        res = conn.execute(text("""SELECT * FROM drug_identifier_types;"""))
        identifier_type_map = {row[1]: row[0] for row in res}

    for drug_meta in drug_meta_list:
        drug_tuples.append(
            (drug_meta["drug_id"], drug_meta["name"], drug_meta["smiles"])
        )
        for identifier in drug_meta["alt_identifiers"]:
            _type, value, url = identifier
            integer_identifier_value = identifier_type_map[_type]
            drug_identifiers.append(
                (drug_meta["drug_id"], value, integer_identifier_value, url)
            )

        for target in drug_meta["targets"]:
            gene_name, action_type = target
            action_type_id = actions_type_map[action_type]
            drug_targets.append((drug_meta["drug_id"], gene_name, action_type_id))

    return {
        "drug_tuples": drug_tuples,
        "drug_identifiers": drug_identifiers,
        "drug_targets": drug_targets,
    }


def write_rows_to_db(db_engine, data_tuples: Dict):
    """Take the output of 'transfor_to_db_row' and write to database"""
    with db_engine.connect() as conn:
        if data_tuples["drug_tuples"]:
            insert_str = ",".join(str(t) for t in data_tuples["drug_tuples"])
            conn.execute(
                text(
                    """
                    INSERT INTO drugs (drugbank_id, name, smiles) VALUES {};
                    """.format(
                        insert_str
                    )
                )
            )
        if data_tuples["drug_targets"]:
            insert_str = ",".join(str(t) for t in data_tuples["drug_targets"])
            conn.execute(
                text(
                    """
                    INSERT INTO drug_targets (drugbank_id, gene_name, action_type_id) VALUES {};
                    """.format(
                        insert_str
                    )
                )
            )
        if data_tuples["drug_identifiers"]:
            insert_str = ",".join(str(t) for t in data_tuples["drug_identifiers"])
            conn.execute(
                text(
                    """
                    INSERT INTO drug_identifiers (drugbank_id, alt_identifier_value, alt_identifier_type_id, alt_identifier_url) VALUES {};
                    """.format(
                        insert_str
                    )
                )
            )