from uuid import uuid4

from fastapi.testclient import TestClient


def create_project(
    client: TestClient,
    *,
    name: str = "E-Commerce Testing",
    base_url: str = "https://example.com",
    authorization_confirmed: bool = True,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "base_url": base_url,
            "description": "Automated testing project",
            "authorization_confirmed": authorization_confirmed,
        },
    )
    return response.json()


def test_create_project_successfully(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "E-Commerce Testing",
            "base_url": "https://example.com",
            "description": "Automated testing project",
            "authorization_confirmed": True,
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["name"] == "E-Commerce Testing"
    assert result["base_url"] == "https://example.com/"
    assert result["is_active"] is True
    assert result["id"]
    assert result["created_at"]
    assert result["updated_at"]


def test_reject_empty_project_name(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": " ",
            "base_url": "https://example.com",
            "authorization_confirmed": True,
        },
    )

    assert response.status_code == 422


def test_reject_invalid_project_url(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Example",
            "base_url": "ftp://example.com",
            "authorization_confirmed": True,
        },
    )

    assert response.status_code == 422


def test_reject_missing_authorization_confirmation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Example", "base_url": "https://example.com"},
    )

    assert response.status_code == 422


def test_list_projects_and_filter_by_active(client: TestClient) -> None:
    create_project(client, name="Active Shop")
    archived = create_project(client, name="Archived Shop")
    client.delete(f"/api/v1/projects/{archived['id']}")

    response = client.get("/api/v1/projects?is_active=true")

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["items"][0]["name"] == "Active Shop"


def test_search_projects_by_name(client: TestClient) -> None:
    create_project(client, name="E-Commerce Testing")
    create_project(client, name="Marketing Site")

    response = client.get("/api/v1/projects?search=commerce")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "E-Commerce Testing"


def test_blank_search_is_ignored(client: TestClient) -> None:
    create_project(client, name="E-Commerce Testing")
    create_project(client, name="Marketing Site")

    response = client.get("/api/v1/projects?search=%20%20")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_blank_description_is_normalized_to_none(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Example",
            "base_url": "https://example.com",
            "description": "   ",
            "authorization_confirmed": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["description"] is None


def test_paginate_projects(client: TestClient) -> None:
    for name in ("Shop One", "Shop Two", "Shop Three"):
        create_project(client, name=name)

    response = client.get("/api/v1/projects?page=2&page_size=2")

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 3
    assert result["page"] == 2
    assert len(result["items"]) == 1


def test_get_project_by_id(client: TestClient) -> None:
    created = create_project(client)

    response = client.get(f"/api/v1/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_unknown_project_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/projects/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


def test_update_project_partially(client: TestClient) -> None:
    created = create_project(client)

    response = client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"name": "Updated Project"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Project"
    assert response.json()["base_url"] == created["base_url"]


def test_reject_empty_project_update(client: TestClient) -> None:
    created = create_project(client)

    response = client.patch(f"/api/v1/projects/{created['id']}", json={})

    assert response.status_code == 422


def test_archive_is_soft_hidden_from_default_list_and_not_retrievable(
    client: TestClient,
) -> None:
    created = create_project(client)

    response = client.delete(f"/api/v1/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert client.get(f"/api/v1/projects/{created['id']}").status_code == 404
    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    archived = client.get("/api/v1/projects?is_active=false")
    assert archived.status_code == 200
    assert archived.json()["total"] == 1


def test_archive_already_archived_project_returns_404(
    client: TestClient,
) -> None:
    created = create_project(client)
    assert client.delete(f"/api/v1/projects/{created['id']}").status_code == 200

    response = client.delete(f"/api/v1/projects/{created['id']}")

    assert response.status_code == 404


def test_update_archived_project_returns_404(client: TestClient) -> None:
    created = create_project(client)
    client.delete(f"/api/v1/projects/{created['id']}")

    response = client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"name": "Cannot update"},
    )

    assert response.status_code == 404


def test_skip_limit_project_pagination(client: TestClient) -> None:
    for name in ("Shop One", "Shop Two", "Shop Three"):
        create_project(client, name=name)

    response = client.get("/api/v1/projects?skip=1&limit=1")

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 3
    assert result["skip"] == 1
    assert result["limit"] == 1
    assert len(result["items"]) == 1


def test_invalid_project_pagination_returns_422(client: TestClient) -> None:
    assert client.get("/api/v1/projects?skip=-1").status_code == 422
    assert client.get("/api/v1/projects?limit=101").status_code == 422
