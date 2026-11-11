import dj_database_url
from dj_database_url import DBConfig


def database_config(url: str) -> DBConfig:
    return dj_database_url.parse(
        url,
        conn_max_age=0,
        conn_health_checks=True,
        ssl_require=True,
    )
