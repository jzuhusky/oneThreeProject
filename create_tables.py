import logging

from tqdm import tqdm

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def create_tables(db_engine):
    """RUN SQL STATEMENTS TO CREATE TABLES"""

    with db_engine.connect() as conn:
        create_table_stmts = []

        create_drugs_table = """
        DROP TABLE IF EXISTS drugs CASCADE; 
        CREATE TABLE drugs (
            drugbank_id char(7) PRIMARY KEY,
            name varchar NOT NULL,  -- Something “Human Readable”,
            smiles varchar
        );
        """

        create_table_stmts.append(create_drugs_table)

        create_drug_id_types_table = """
        DROP TABLE IF EXISTS drug_identifier_types CASCADE; 
        CREATE TABLE drug_identifier_types (
            identifier_type_id SERIAL UNIQUE, 
            identifier_type_name varchar UNIQUE
        );    
        """
        create_table_stmts.append(create_drug_id_types_table)

        create_drug_identifiers_table = """
        DROP TABLE IF EXISTS drug_identifiers CASCADE;
        CREATE TABLE drug_identifiers (
            drugbank_id char(7) references drugs(drugbank_id),
            alt_identifier_value varchar NOT NULL,
            alt_identifier_type_id int references drug_identifier_types(identifier_type_id) NOT NULL,
            alt_identifier_url varchar
        );
        """
        create_table_stmts.append(create_drug_identifiers_table)

        create_drug_action_types = """
        DROP TABLE IF EXISTS drug_action_types CASCADE;
        CREATE TABLE drug_action_types (
            action_type_id SERIAL UNIQUE, 
            action_type varchar UNIQUE
        )
        """
        create_table_stmts.append(create_drug_action_types)

        create_drug_targets_table = """
        DROP TABLE IF EXISTS drug_targets CASCADE;
        CREATE TABLE drug_targets (
            drugbank_id char(7) references drugs(drugbank_id),
            gene_name varchar NOT NULL,  
            action_type_id int references drug_action_types(action_type_id),
            UNIQUE(drugbank_id, gene_name, action_type_id)
        );
        """
        create_table_stmts.append(create_drug_targets_table)

        logger.info("Creating %d tables", len(create_table_stmts))
        for stmt in tqdm(create_table_stmts):
            conn.execute(stmt)
