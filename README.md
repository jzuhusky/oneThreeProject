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
# If you already have another PG instance running on 5432 locally,  
# update the `-p` flags arguments using the rule `-p host_port:5432`
docker run -p 5432:5432 -e POSTGRES_PASSWORD=password --name local-postgres -d postgres:alpine
```

Create the database using Raw SQL or via the command line (ensure you have psql installed locally, I'm using a mac):  
See also https://www.postgresql.org/docs/9.3/app-psql.html
```bash
psql -h localhost -U postgres -c 'CREATE DATABASE onethreedb;'
```

Now, setup a local python virtualenv. I've used Pipenv, but there is a requirements.txt file as well. Either should be fine for setting up an virtualenv. 

Using Pipenv
```bash
# Init the environment and install deps (project must be pulled first, and you must be in the dir with the Pipfile)
pipenv install
# activate your environment
pipenv shell
```
If using venv
```bash
virtualenv -p python3.7 {your envs name here}
source {your envs name here}/bin/activate
python -m pip install -r requirements.txt  # or simply pip install -r requirements.txt
```
NOTE: If using Pipenv, the Pipfile has python 3.7 specified as the necessary version. This might precelude a successful install of the 
necessary packages if you're using another python version. If that's the case for you, go ahead and remove the lines from the Pipfile:
```
[requires]
python_version = "3.7"
```
### Run the commands
From your virtual environment, you'll need to run 2 commands to run the data-import:
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
