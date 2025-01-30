# Minesweeper game API using DBOS!

## Running Locally

To run this app locally, you need a Postgres database.
If you have Docker, you can start one with:

Setup dependencies
```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start Postgres
```shell
export PGPASSWORD=dbos
python3 start_postgres_docker.py
```

Start the app
```shell
dbos migrate
dbos start
```

Visit [`http://localhost:8000/docs`](http://localhost:8000/docs) to see the API!

## Migrations

Auto-generate migrations with Alembic
```shell
export PGPASSWORD=dbos
alembic revision --autogenerate -m "add table"
```
