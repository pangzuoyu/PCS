from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类（统一命名约定，避免 alembic autogenerate 噪声）。

    业务：所有 ORM 模型继承 Base；NAMING_CONVENTION 锁定 ix/uq/fk/pk 命名
    规则（手工建约束时也能命中约定，autogenerate 不报"diff noise"）。
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
