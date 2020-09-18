import json
import logging
from typing import Dict

import click
from sqlalchemy import create_engine

from create_tables import create_tables
from etl import pull_drugs, equalize_type_ids, transform_to_db_rows, write_rows_to_db

logging.basicConfig(
    **{
        "format": "[%(asctime)s] %(filename)s:%(lineno)s %(levelname)-8s %(message)s",
        "level": "INFO",
    }
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


def get_db_engine():
    """Create a db engine and return it"""
    with open("config.json") as fp:
        db_config = json.loads(fp.read())
        db_engine = create_engine(
            "postgresql+psycopg2://{PG_USERNAME}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}".format(
                **db_config
            )
        )
        # Yes, we can return within a "with" block. Python will handle cleanup of the db engine accordingly
        return db_engine


@cli.command()
def run_import():
    """Importing the drug data

    This function will call a few other functions to run a simple
    ETL process to load some metadata about drugs from DrugBank.

    In a perfect world, each step of this process, and likely more complex processes,
    these steps would be broken up into DAG ETL Nodes, think "Airflow".

    For a simple script like this however, it's easier / cleaner / simpler
    to not use a large "hammer" like Airflow.

    This design also leads nicely into parallelization if necessary, since the entire
    input to the etl is a list of drug ids. So the natural way to split up the work,
    would be to split the input data into N chunks and distribute across N processes.
    The DB hits will run concurrently.
    """
    db_engine = get_db_engine()

    with open("DRUGIDS") as fp:
        drug_ids = [line.strip() for line in fp]

    # Scrape the site, and pull the data we need
    logger.info("Scraping the Drugbank Site")
    drug_metadata = pull_drugs(drug_ids)

    # Check the Database against the "action" and "alt_identifier" types
    # we observe from the site, and the one's we already have in the database.
    # Insert / Update accordingly
    logger.info("Equalizing Type IDs")
    equalize_type_ids(db_engine, drug_metadata)

    # Transform the Metadata dicts into lists of tuples, 1 list per relation
    # so we can bulk insert accordingly
    logger.info("Transforming data to tuples for insertion")
    db_rows_to_insert: Dict = transform_to_db_rows(db_engine, drug_metadata)

    # Insert the rows.
    logger.info("Inserting Data")
    write_rows_to_db(db_engine, db_rows_to_insert)


@cli.command()
def setup_db():
    """Run the create tables command"""
    logger.info("Creating Database Tables")
    create_tables(get_db_engine())


if __name__ == "__main__":
    cli()
