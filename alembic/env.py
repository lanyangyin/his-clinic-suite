from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 数据库地址以应用配置为准（config.ini / HIS_DATABASE_URL），alembic.ini 仅作回退
try:
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
except Exception:  # pragma: no cover - 配置异常时保持 alembic.ini 默认值
    pass

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
import app.database
import app.modules.patient.models  # noqa: F401
import app.modules.staff.models  # noqa: F401
import app.modules.registration.models  # noqa: F401
import app.modules.encounter.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
import app.modules.pharmacy.models  # noqa: F401
import app.modules.drug.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.inpatient.models  # noqa: F401
import app.modules.triage.models  # noqa: F401
import app.modules.lis.models  # noqa: F401
import app.modules.pacs.models  # noqa: F401
import app.modules.warehouse.models  # noqa: F401
import app.modules.materials.models  # noqa: F401
import app.modules.supplier.models  # noqa: F401
import app.modules.pathway.models  # noqa: F401
import app.modules.finance.models  # noqa: F401
import app.modules.hr.models  # noqa: F401
import app.modules.integration.models  # noqa: F401
import app.modules.dict.models  # noqa: F401
import app.modules.publichealth.models  # noqa: F401
import app.modules.ca.models  # noqa: F401
import app.modules.idempotency.models  # noqa: F401
import app.modules.charges.models  # noqa: F401
import app.modules.treatment.models  # noqa: F401
import app.modules.appointment.models  # noqa: F401
import app.modules.facility.models  # noqa: F401
import app.modules.sms.models  # noqa: F401
import app.modules.receiving.models  # noqa: F401
import app.modules.insurance_catalog.models  # noqa: F401
import app.modules.stock_ledger.models  # noqa: F401
import app.modules.traceability.models  # noqa: F401
import app.modules.insurance_inventory.models  # noqa: F401
import app.modules.insurance_inventory.interface_models  # noqa: F401

target_metadata = app.database.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
