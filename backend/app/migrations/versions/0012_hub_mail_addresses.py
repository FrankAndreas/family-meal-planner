"""Recipe mails come only from the address each person confirmed in the family hub (security review 2026-11-08, option
B): the addresses typed into the planner are dropped, the hub's is kept with the person and synced like their name."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email", sa.String(200)))
    op.drop_table("user_emails")


def downgrade() -> None:
    # The typed addresses are gone; the hub's are kept as typed ones again
    op.create_table(
        "user_emails",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_emails_user_id_users"),
            nullable=False,
        ),
        sa.Column("address", sa.String(200), nullable=False),
        sa.UniqueConstraint("address", name="uq_user_emails_address"),
    )
    op.execute(
        "INSERT INTO user_emails (user_id, address) SELECT MIN(id), email FROM users WHERE email IS NOT NULL GROUP BY email"
    )
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email")
