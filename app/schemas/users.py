from pydantic import BaseModel, ConfigDict


class UserPublic(BaseModel):
    """允许返回给客户端的公开用户信息"""

    id: int
    username: str
    display_name: str
    roles: list[str]

    model_config = ConfigDict(
        from_attributes=True,
    )
