from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from minesweeper_dbos.api import app
from dbos import DBOS
import minesweeper_dbos.api.models as models
import datetime
from pydantic import BaseModel
from pathlib import Path
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(Path(BASE_DIR, "static"))), name="static")
templates = Jinja2Templates(directory=str(Path(BASE_DIR, 'templates')))

GAME_TIMEOUT_SECS: int = 60 * 20  # 20 minutes

@app.get("/hello", response_class=HTMLResponse)
def index(request: Request):
    """Generates a page with the request."""
    return templates.TemplateResponse(name="index.html",
                                      context={"request": request, "message": "Hello, World!"})


@app.get('/api/v1/games/{gameid}/state/')
@DBOS.transaction()
def api_state(gameid: int):
    """
    **Returns** the game object. (GET method)
    The current `state` can be:

    - **new** : for a new game.
    - **started** : if the game is running.
    - **paused** : if the game is paused.
    - **timeout** : if the game finished by timeout.
    - **won** : if the player won the game.
    - **lost** : if the player lost the game.

    The `board_view` is a matrix where each cell can be:

    - an empty character if the user hasn't set a mark or revealed the cell.
    - **?** : if the user set a question mark
    - **!** : if the user set a red flag mark
    - **x** : to indicate the cell has a mine.
    - an integer (0-8) to indicate the number of adjacent mines to the cell.
    """
    game = DBOS.sql_session.query(models.Game).get(gameid)
    return JSONResponse(jsonable_encoder(game.serialize()))


class NewRequest(BaseModel):
    rows: int
    columns: int
    mines: int


@app.post('/api/v1/games/new/')
@DBOS.workflow()
def api_new(request: NewRequest):
    """
    Creates a new game. (POST method)
    **Returns** the game state.
    Arguments:
        - rows (number of rows)
        - columns (number of columns)
        - mines (number of mines, should be less than the board size)
    """
    game = insert_new(request)
    DBOS.start_workflow(check_timeout, gameid=int(game['id']))
    return JSONResponse(jsonable_encoder(game))


@DBOS.workflow()
def check_timeout(gameid: int):
    DBOS.sleep(GAME_TIMEOUT_SECS)
    game_timeout(gameid)


@DBOS.transaction()
def game_timeout(gameid: int):
    game = DBOS.sql_session.query(models.Game).get(gameid)
    game.timeout()


@DBOS.transaction()
def insert_new(request: NewRequest):
    rows = request.rows
    columns = request.columns
    mines = request.mines
    board, player_board = models.Game.new_boards(rows, columns, mines)

    user = DBOS.sql_session.query(models.User).limit(1).all()  # Hack to use a single user for now.
    if not user:
        user = models.User("test", "test", "test@test.com")
        user.id = 1
        DBOS.sql_session.add(user)
        user = [user]
    game = models.Game()
    game.title = 'Game for user %s' % (user[0].first_name)
    game.board = board
    game.player_board = player_board
    game.state = models.Game.STATE_NEW
    game.player_id = user[0].id
    game.resumed_timestamp = datetime.datetime.utcnow()
    DBOS.sql_session.add(game)
    DBOS.sql_session.flush() # To get the game defaults and PK.
    return game.serialize()


class CellRequest(BaseModel):
    x: int
    y: int


@app.post('/api/v1/games/{gameid}>/pause/')
@DBOS.transaction()
def api_pause(gameid: int):
    """
    Pauses a given game (stops time tracking). (POST method)
    **Returns** the game state.
    """
    game = DBOS.sql_session.query(models.Game).get(gameid)
    return JSONResponse(jsonable_encoder(game.serialize()))


@app.post('/api/v1/games/{gameid}/resume/')
@DBOS.transaction()
def api_resume(gameid: int):
    """
    Resumes a given game (starts time tracking). (POST method)
    **Returns** the game state.
    """
    game = DBOS.sql_session.query(models.Game).get(gameid)
    return JSONResponse(jsonable_encoder(game.serialize()))


@app.post('/api/v1/games/{gameid}/mark_as_flag/')
@DBOS.transaction()
def api_mark_as_flag(gameid: int, request: CellRequest):
    """
    Set a flag mark in a given cell. (POST method)
    **Returns** the game state.
    Arguments:
        - x (cell index)
        - y (cell index)
    """
    x = request.x
    y = request.y

    game = DBOS.sql_session.query(models.Game).get(gameid)
    game.mark_flag_at(x, y)
    return JSONResponse(jsonable_encoder(game.serialize()))


@app.post('/api/v1/games/{gameid}/mark_as_question/')
@DBOS.transaction()
def api_mark_as_question(gameid: int, request: CellRequest):
    """
    Set a question mark in a given cell. (POST method)
    **Returns** the game state.
    Arguments:
        - x (cell index)
        - y (cell index)
    """
    x = request.x
    y = request.y

    game = DBOS.sql_session.query(models.Game).get(gameid)
    game.mark_question_at(x, y)
    return JSONResponse(jsonable_encoder(game.serialize()))


@app.post('/api/v1/games/{gameid}/reveal/')
@DBOS.transaction()
def api_reveal(gameid: int, request: CellRequest):
    """
    Reveals a given cell. (POST method)
    **Returns** the game state.
    Arguments:
        - x (cell index)
        - y (cell index)
    """
    x = request.x
    y = request.y

    game = DBOS.sql_session.query(models.Game).get(gameid)
    game.reveal_at(x, y)
    if game.is_mine_at(x, y):
        game.state = models.Game.STATE_LOST
    elif game.is_all_revealed():
        game.state = models.Game.STATE_WON
    return JSONResponse(jsonable_encoder(game.serialize()))
