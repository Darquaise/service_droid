"""Galatron: the voice (register) the current reign is told in, rerolled on every win.

The column default rolls a register per row, so existing guilds and every guild the
bot joins later start with a random one instead of all sharing the same voice.
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0005_galatron_register"
down_revision: Union[str, None] = "0004_galatron_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RANDOM_REGISTER = "((ARRAY['survey', 'shroud', 'court'])[floor(random() * 3)::int + 1])"


def upgrade() -> None:
    op.add_column(
        "guild",
        sa.Column("galatron_register", sa.Text(), nullable=False, server_default=sa.text(RANDOM_REGISTER)),
    )


def downgrade() -> None:
    op.drop_column("guild", "galatron_register")
