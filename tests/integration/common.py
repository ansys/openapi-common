import secrets
from typing import Optional, List

from fastapi import HTTPException, status
from fastapi.security import HTTPBasicCredentials
from pydantic import BaseModel

TEST_MODEL_ID = '37630523-deac-44b4-b920-b150ff8a2308'
TEST_PORT = 27768
TEST_URL = f"http://localhost:{TEST_PORT}"
TEST_USER = "api_user"
TEST_PASS = "rosebud"


def validate_user_basic(credentials: HTTPBasicCredentials) -> None:
    correct_username = secrets.compare_digest(credentials.username, TEST_USER)
    correct_password = secrets.compare_digest(credentials.password, TEST_PASS)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )


class ExampleModelPyd(BaseModel):
    String: Optional[str]
    Integer: Optional[int]
    ListOfStrings: Optional[List[str]]
    Boolean: Optional[bool]
