import os
import sqlite3
import jwt
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator

load_dotenv()

# ---------------------------------------------------------------------------
# Configurare
# ---------------------------------------------------------------------------

DATABASE_PATH = os.environ.get("DATABASE_PATH", "sarcini.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "cheie-implicita-doar-pentru-dev")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
EXPIRARE_TOKEN_MINUTE = int(os.environ.get("EXPIRARE_TOKEN_MINUTE", "30"))

context_parola = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_schema = OAuth2PasswordBearer(tokenUrl="autentificare")


# ---------------------------------------------------------------------------
# Baza de date
# ---------------------------------------------------------------------------

def initializeaza_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS utilizatori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            parola_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sarcini (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titlu TEXT NOT NULL,
            descriere TEXT,
            finalizata INTEGER DEFAULT 0,
            utilizator_id INTEGER NOT NULL,
            FOREIGN KEY (utilizator_id) REFERENCES utilizatori(id)
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def durata_de_viata(app: FastAPI):
    initializeaza_db()
    yield


# ---------------------------------------------------------------------------
# Aplicatia
# ---------------------------------------------------------------------------

app = FastAPI(title="Gestionar de sarcini", version="2.0.0", lifespan=durata_de_viata)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Modele Pydantic
# ---------------------------------------------------------------------------

class UtilizatorInregistrare(BaseModel):
    email: str = Field(min_length=5, max_length=100)
    parola: str = Field(min_length=8, max_length=100)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Adresa de email nu este valida.")
        return v.lower()


class SarcinaCreare(BaseModel):
    titlu: str = Field(min_length=1, max_length=200)
    descriere: Optional[str] = Field(default=None, max_length=1000)


class SarcinaActualizare(BaseModel):
    titlu: Optional[str] = Field(default=None, min_length=1, max_length=200)
    descriere: Optional[str] = Field(default=None, max_length=1000)
    finalizata: Optional[bool] = None


# ---------------------------------------------------------------------------
# Functii utilitare
# ---------------------------------------------------------------------------

def hasheaza_parola(parola: str) -> str:
    return context_parola.hash(parola)


def verifica_parola(parola: str, hash_parola: str) -> bool:
    return context_parola.verify(parola, hash_parola)


def creeaza_token(date: dict) -> str:
    date_copie = date.copy()
    date_copie["exp"] = datetime.now(timezone.utc) + timedelta(minutes=EXPIRARE_TOKEN_MINUTE)
    return jwt.encode(date_copie, SECRET_KEY, algorithm=ALGORITHM)


def get_utilizator_curent(
    token: str = Depends(oauth2_schema),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token invalid.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirat. Autentificati-va din nou.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalid.")

    utilizator = db.execute(
        "SELECT * FROM utilizatori WHERE email = ?", (email,)
    ).fetchone()
    if not utilizator:
        raise HTTPException(status_code=401, detail="Utilizatorul nu exista.")
    return utilizator


# ---------------------------------------------------------------------------
# Endpoint-uri: health check
# ---------------------------------------------------------------------------

@app.get("/healthz")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Endpoint-uri: autentificare
# ---------------------------------------------------------------------------

@app.post("/inregistrare", status_code=201)
def inregistrare(utilizator: UtilizatorInregistrare, db: sqlite3.Connection = Depends(get_db)):
    existent = db.execute(
        "SELECT id FROM utilizatori WHERE email = ?", (utilizator.email,)
    ).fetchone()
    if existent:
        raise HTTPException(status_code=400, detail="Adresa de email este deja inregistrata.")

    db.execute(
        "INSERT INTO utilizatori (email, parola_hash) VALUES (?, ?)",
        (utilizator.email, hasheaza_parola(utilizator.parola)),
    )
    db.commit()
    return {"mesaj": f"Utilizatorul {utilizator.email} a fost inregistrat cu succes."}


@app.post("/autentificare")
def autentificare(
    formular: OAuth2PasswordRequestForm = Depends(),
    db: sqlite3.Connection = Depends(get_db),
):
    utilizator = db.execute(
        "SELECT * FROM utilizatori WHERE email = ?", (formular.username,)
    ).fetchone()
    if not utilizator or not verifica_parola(formular.password, utilizator["parola_hash"]):
        raise HTTPException(status_code=401, detail="Email sau parola incorecta.")

    token = creeaza_token({"sub": utilizator["email"]})
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Endpoint-uri: sarcini (protejate cu JWT)
# ---------------------------------------------------------------------------

@app.get("/sarcini")
def obtine_sarcini(
    doar_nefinalizate: bool = False,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    if doar_nefinalizate:
        sarcini = db.execute(
            "SELECT * FROM sarcini WHERE utilizator_id = ? AND finalizata = 0",
            (utilizator_curent["id"],)
        ).fetchall()
    else:
        sarcini = db.execute(
            "SELECT * FROM sarcini WHERE utilizator_id = ?", (utilizator_curent["id"],)
        ).fetchall()
    return [dict(s) for s in sarcini]


@app.get("/sarcini/{sarcina_id}")
def obtine_sarcina(
    sarcina_id: int,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    sarcina = db.execute(
        "SELECT * FROM sarcini WHERE id = ? AND utilizator_id = ?",
        (sarcina_id, utilizator_curent["id"]),
    ).fetchone()
    if not sarcina:
        raise HTTPException(status_code=404, detail="Sarcina nu a fost gasita.")
    return dict(sarcina)


@app.post("/sarcini", status_code=201)
def creeaza_sarcina(
    sarcina: SarcinaCreare,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    cursor = db.execute(
        "INSERT INTO sarcini (titlu, descriere, utilizator_id) VALUES (?, ?, ?)",
        (sarcina.titlu, sarcina.descriere, utilizator_curent["id"]),
    )
    db.commit()
    sarcina_noua = db.execute(
        "SELECT * FROM sarcini WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return dict(sarcina_noua)


@app.put("/sarcini/{sarcina_id}")
def actualizeaza_sarcina(
    sarcina_id: int,
    date: SarcinaActualizare,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    sarcina = db.execute(
        "SELECT * FROM sarcini WHERE id = ? AND utilizator_id = ?",
        (sarcina_id, utilizator_curent["id"]),
    ).fetchone()
    if not sarcina:
        raise HTTPException(status_code=404, detail="Sarcina nu a fost gasita.")

    sarcina_dict = dict(sarcina)
    titlu_nou = date.titlu if date.titlu is not None else sarcina_dict["titlu"]
    descriere_noua = date.descriere if date.descriere is not None else sarcina_dict["descriere"]
    finalizata_noua = int(date.finalizata) if date.finalizata is not None else sarcina_dict["finalizata"]

    db.execute(
        "UPDATE sarcini SET titlu = ?, descriere = ?, finalizata = ? WHERE id = ?",
        (titlu_nou, descriere_noua, finalizata_noua, sarcina_id),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM sarcini WHERE id = ?", (sarcina_id,)).fetchone())


@app.patch("/sarcini/{sarcina_id}/finalizeaza")
def finalizeaza_sarcina(
    sarcina_id: int,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    sarcina = db.execute(
        "SELECT * FROM sarcini WHERE id = ? AND utilizator_id = ?",
        (sarcina_id, utilizator_curent["id"]),
    ).fetchone()
    if not sarcina:
        raise HTTPException(status_code=404, detail="Sarcina nu a fost gasita.")

    db.execute("UPDATE sarcini SET finalizata = 1 WHERE id = ?", (sarcina_id,))
    db.commit()
    return dict(db.execute("SELECT * FROM sarcini WHERE id = ?", (sarcina_id,)).fetchone())


@app.delete("/sarcini/{sarcina_id}")
def sterge_sarcina(
    sarcina_id: int,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    sarcina = db.execute(
        "SELECT * FROM sarcini WHERE id = ? AND utilizator_id = ?",
        (sarcina_id, utilizator_curent["id"]),
    ).fetchone()
    if not sarcina:
        raise HTTPException(status_code=404, detail="Sarcina nu a fost gasita.")

    db.execute("DELETE FROM sarcini WHERE id = ?", (sarcina_id,))
    db.commit()
    return {"mesaj": f"Sarcina cu ID-ul {sarcina_id} a fost stearsa."}


# Trebuie sa fie ULTIMUL apel - prinde toate rutele nerezolvate de endpoint-uri
app.mount("/", StaticFiles(directory="static", html=True), name="static")
