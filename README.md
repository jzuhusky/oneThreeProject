# oneThreeProject

This project contains simple scripts to create a Postgres DB locally, and run some scripts to 
pull metadata about Drugs from drugbank.com. The scripts act as a basic ETL to get the data off the site
and into the database. 

Fair warning, this was developed locally on a Mac. Linux systems should be OK, not sure about Windows. 

## Getting Started

You'll need a Postgres Database. If using Docker, use the commands below, otherwise setup a postgres DB instance however you like.
If using Docker as shown below, the default credentials in `config.json` should work for the Docker setup. Otherwise, 
plug in your own credentials into this file. Which variables to set should be self-evident. 

```bash
# alpine images are generally lightweight
docker pull postgres:alpine

# Run the PG instance locally, setting password to "password", default user is "postgres"
docker run -p 5432:5432 -e POSTGRES_PASSWORD=password --name local-postgres -d postgres:alpine
```

Create the database using Raw SQL or via the command line (ensure you have psql installed locally, I'm using a mac):  
See also https://www.postgresql.org/docs/9.3/app-psql.html
```bash
psql -h localhost -U postgres -c 'CREATE DATABASE onethreedb;'
```

Now, setup a local python virtualenv. I've used Pipenv, but there is a requirements.txt file as well. Either should be fine for setting up an virtualenv. 
```bash
# 1st, install Pipenv / virtualenv, use one or the other. 

# Using pipenv
pipenv shell
# Requirements.txt for virtualenv etc. 
pip install -r requirements.txt
```

You'll need to run 2 commands to run the data-import:
1. From the app's directory, Create Database tables
```bash
python main.py setup-db
```
This command is idempotent. If run, any existing tables will be deleted and re-created. You may run it any number of times. 

2. Run the Data Import
```bash
python main.py run-import
```

## TODO:
Write some tests. 
