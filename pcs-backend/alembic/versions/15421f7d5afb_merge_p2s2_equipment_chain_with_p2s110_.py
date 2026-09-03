"""merge p2s2 equipment chain with p2s110 template chain

Revision ID: 15421f7d5afb
Revises: 2026_09_03_1000_add_htri_template_schemas, p2_sprint2_equipment_engineering
Create Date: 2026-09-03 20:51:19.227516

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '15421f7d5afb'
down_revision: str | Sequence[str] | None = (
    '2026_09_03_1000_add_htri_template_schemas',
    'p2_sprint2_equipment_engineering',
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
