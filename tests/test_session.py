from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.session import SESSION_HEADER, SessionContext, get_session_context
from repositories import session_repository

app = FastAPI()


@app.get("/whoami")
async def whoami(session: SessionContext = Depends(get_session_context)):
    return {"session_id": session.session_id, "ip": session.ip}


client = TestClient(app)


async def test_mints_new_session_id_when_absent(mongo_db):
    res = client.get("/whoami")
    assert res.status_code == 200
    minted = res.headers[SESSION_HEADER]
    assert minted == res.json()["session_id"]

    stored = await session_repository.get_session(minted)
    assert stored is not None


def test_echoes_supplied_session_id(mongo_db):
    res = client.get("/whoami", headers={SESSION_HEADER: "my-existing-session"})
    assert res.headers[SESSION_HEADER] == "my-existing-session"
    assert res.json()["session_id"] == "my-existing-session"


def test_extracts_ip_from_x_forwarded_for(mongo_db):
    res = client.get("/whoami", headers={"X-Forwarded-For": "5.6.7.8, 9.9.9.9"})
    assert res.json()["ip"] == "5.6.7.8"


def test_falls_back_to_client_host_without_forwarded_header(mongo_db):
    res = client.get("/whoami")
    assert res.json()["ip"]  # TestClient sets some client host; just must not be empty
