from __future__ import with_statement
import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine

from alembic import context

# ensure repo root on path
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config.settings import get_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Provide the SQLAlchemy URL dynamically from our app settings
def get_url():
    settings = get_settings()
    uri = settings.DATABASE_URI
    if uri == "sqlite:///:memory:":
        uri = "sqlite:///pipeline.db"
    return uri


def run_migrations_offline():
    url = get_url()
    context.configure(url=url, target_metadata=None, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(get_url())

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
