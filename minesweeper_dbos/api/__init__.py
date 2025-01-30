from dbos import DBOS
from fastapi import FastAPI

app = FastAPI()
DBOS(fastapi=app)

from .views import *
