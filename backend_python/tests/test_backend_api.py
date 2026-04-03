from fastapi.testclient import TestClient
import io
import json


def register_and_login(client: TestClient, username: str = "tester", password: str = "test123") -> str:
    register_response = client.post(
        "/register",
        json={"username": username, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/login",
        data={"username": username, "password": password},
    )
    assert login_response.status_code == 200

    token = login_response.json().get("access_token")
    assert token
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def valid_card_payload(name: str = "Asan", birth_year: int = 1899) -> dict:
    return {
        "name": name,
        "birth_year": birth_year,
        "death_year": 1937,
        "region": "Chui",
        "category": "Teacher",
        "charge": "Article 58-10",
        "description": "Short biography",
        "source": "Archive fund 10",
        "lat": None,
        "lon": None,
    }


def test_register_and_login_returns_token(client: TestClient):
    token = register_and_login(client)
    assert isinstance(token, str)
    assert len(token) > 10


def test_create_card_and_get_card(client: TestClient):
    token = register_and_login(client)

    create_response = client.post(
        "/cards",
        headers=auth_headers(token),
        json=valid_card_payload(name="Baitemirov", birth_year=1899),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Baitemirov"
    assert created["region"] == "Chui"

    card_id = created["id"]
    get_response = client.get(f"/cards/{card_id}", headers=auth_headers(token))
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == card_id
    assert fetched["charge"] == "Article 58-10"


def test_duplicate_card_rejected(client: TestClient):
    token = register_and_login(client)
    payload = valid_card_payload(name="Sydykova", birth_year=1905)

    first = client.post("/cards", headers=auth_headers(token), json=payload)
    assert first.status_code == 201

    second = client.post("/cards", headers=auth_headers(token), json=payload)
    assert second.status_code == 409
    assert "Duplicate card" in second.json()["detail"]


def test_cards_filter_by_region_and_birth_year(client: TestClient):
    token = register_and_login(client)

    card_a = valid_card_payload(name="A", birth_year=1890)
    card_b = valid_card_payload(name="B", birth_year=1900)
    card_b["region"] = "Osh"

    assert client.post("/cards", headers=auth_headers(token), json=card_a).status_code == 201
    assert client.post("/cards", headers=auth_headers(token), json=card_b).status_code == 201

    response = client.get(
        "/cards",
        headers=auth_headers(token),
        params={"region": "osh", "birth_year": 1900},
    )
    assert response.status_code == 200
    cards = response.json()
    assert len(cards) == 1
    assert cards[0]["name"] == "B"


def test_upload_document_rejects_unsupported_extension(client: TestClient):
    token = register_and_login(client)

    response = client.post(
        "/upload_document",
        headers=auth_headers(token),
        data={"person_id": "1"},
        files={"file": ("archive.pdf", b"fake-pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .txt and .md files are supported"


def test_seed_import_skips_duplicates(client: TestClient):
    token = register_and_login(client)

    payload = [
        {
            "full_name": "Baitemirov Asan",
            "birth_year": 1899,
            "death_year": 1937,
            "region": "Chui",
            "occupation": "Teacher",
            "charge": "58-10",
            "biography": "Bio 1",
            "source": "Archive 1",
        },
        {
            "full_name": "Baitemirov Asan",
            "birth_year": 1899,
            "death_year": 1937,
            "region": "Chui",
            "occupation": "Teacher",
            "charge": "58-10",
            "biography": "Bio duplicate",
            "source": "Archive 2",
        },
    ]

    response = client.post("/cards/import/seed", headers=auth_headers(token), json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["skipped_duplicates"] == 1
    assert body["total"] == 2


def test_create_card_accepts_minimal_payload_for_frontend_compat(client: TestClient):
    token = register_and_login(client, username="frontend-user")

    response = client.post(
        "/cards",
        headers=auth_headers(token),
        json={
            "name": "Frontend Compatible Card",
            "category": "Teacher",
            "description": "Created with minimal payload",
            "lat": None,
            "lon": None,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Frontend Compatible Card"
    assert body["birth_year"] == 1900
    assert body["region"] == "Unknown"
    assert body["charge"] == "Unknown"


def test_import_persons_file_endpoint_supports_seed_json_shape(client: TestClient):
    token = register_and_login(client, username="import-user")

    payload = [
        {
            "id": 1,
            "full_name": "Asan Seed",
            "birth_year": 1899,
            "death_year": 1937,
            "region": "Chui",
            "occupation": "Teacher",
            "charge": "58-10",
            "biography": "Bio 1",
            "source": "Archive A",
        },
        {
            "id": 2,
            "full_name": "Asan Seed",
            "birth_year": 1899,
            "death_year": 1938,
            "region": "Chui",
            "occupation": "Teacher",
            "charge": "58-10",
            "biography": "Bio duplicate",
            "source": "Archive B",
        },
    ]

    files = {
        "file": ("seed.json", io.BytesIO(json.dumps(payload).encode("utf-8")), "application/json")
    }
    response = client.post(
        "/api/persons/import",
        headers=auth_headers(token),
        files=files,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped_duplicates"] == 1
    assert body["total"] == 2


def test_persons_alphabetical_returns_frontend_shape(client: TestClient):
    token = register_and_login(client, username="alphabet-user")

    payload = [
        {
            "full_name": "Askar T",
            "birth_year": 1901,
            "region": "Osh",
            "occupation": "Journalist",
            "charge": "58-10",
            "biography": "Bio",
        },
        {
            "full_name": "Bakyt K",
            "birth_year": 1902,
            "region": "Chui",
            "occupation": "Teacher",
            "charge": "58-10",
            "biography": "Bio",
        },
    ]

    response_import = client.post(
        "/cards/import/seed",
        headers=auth_headers(token),
        json=payload,
    )
    assert response_import.status_code == 200

    response = client.get("/api/persons/alphabetical", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()

    assert "A" in body
    assert "B" in body
    assert body["A"][0]["full_name"] == "Askar T"
    assert body["B"][0]["full_name"] == "Bakyt K"


def test_public_person_endpoint_returns_static_front_shape(client: TestClient):
    token = register_and_login(client, username="public-person-user")

    create_response = client.post(
        "/cards",
        headers=auth_headers(token),
        json=valid_card_payload(name="Public Person", birth_year=1904),
    )
    assert create_response.status_code == 201
    card_id = create_response.json()["id"]

    response = client.get(f"/api/person/{card_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == card_id
    assert body["full_name"] == "Public Person"
    assert "biography" in body
    assert "documents" in body


def test_public_persons_search_endpoint_is_unauthenticated(client: TestClient):
    token = register_and_login(client, username="public-search-user")

    response_create = client.post(
        "/cards",
        headers=auth_headers(token),
        json=valid_card_payload(name="Searchable Person", birth_year=1910),
    )
    assert response_create.status_code == 201

    response = client.get("/api/persons/search", params={"q": "searchable", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert body[0]["full_name"] == "Searchable Person"
