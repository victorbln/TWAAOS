from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Gestiune inventar", version="1.0.0")


class Produs(BaseModel):
    id: int
    nume: str
    pret: float
    stoc: int = 0


inventar: list[Produs] = []


@app.get("/produse")
def obtine_toate_produsele(stoc_minim: int | None = None):
    if stoc_minim is not None:
        return [p for p in inventar if p.stoc < stoc_minim]
    return inventar


@app.get("/produse/{produs_id}")
def obtine_produs(produs_id: int):
    for produs in inventar:
        if produs.id == produs_id:
            return produs
    raise HTTPException(status_code=404, detail=f"Produsul cu ID-ul {produs_id} nu a fost gasit.")


@app.post("/produse", status_code=201)
def adauga_produs(produs: Produs):
    for p in inventar:
        if p.id == produs.id:
            raise HTTPException(status_code=400, detail=f"Produsul cu ID-ul {produs.id} exista deja.")
    inventar.append(produs)
    return produs


@app.put("/produse/{produs_id}")
def actualizeaza_produs(produs_id: int, produs: Produs):
    for i, p in enumerate(inventar):
        if p.id == produs_id:
            inventar[i] = produs
            return inventar[i]
    raise HTTPException(status_code=404, detail=f"Produsul cu ID-ul {produs_id} nu a fost gasit.")


@app.delete("/produse/{produs_id}")
def sterge_produs(produs_id: int):
    for i, produs in enumerate(inventar):
        if produs.id == produs_id:
            produs_sters = inventar.pop(i)
            return produs_sters
    raise HTTPException(status_code=404, detail=f"Produsul cu ID-ul {produs_id} nu a fost gasit.")
