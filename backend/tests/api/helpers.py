def ids(response) -> list[int]:
    """The ids of a list response's rows, in order."""
    return [row["id"] for row in response.json()["data"]]


def error_fields(response) -> set[str]:
    """The fields a 422 names, after asserting it is one."""
    assert response.status_code == 422, response.content
    body = response.json()
    assert isinstance(body["message"], str)
    return set(body["errors"])
