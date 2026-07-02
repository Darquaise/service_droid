"""Add FK trivia_channel(guild_id, list_name) -> trivia_list.

Deferred (checked at commit) so replace_guild/replace_list — delete + reinsert
within one transaction — still pass, while an external writer can no longer
delete a list that channels still reference.
"""

from typing import Sequence, Union
from alembic import op

revision: str = "0002_trivia_channel_list_fk"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT = "trivia_channel_list_fkey"


def upgrade() -> None:
    op.create_foreign_key(
        CONSTRAINT,
        "trivia_channel",
        "trivia_list",
        ["guild_id", "list_name"],
        ["guild_id", "name"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "trivia_channel", type_="foreignkey")
