"""Add interview stage missed columns

Revision ID: e3fd7129ab5e
Revises: d4ec588369c4
Create Date: 2026-02-20 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3fd7129ab5e'
down_revision = 'd4ec588369c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('job_applications', sa.Column('phone_screen_missed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('job_applications', sa.Column('assessment_missed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('job_applications', sa.Column('technical_missed', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('job_applications', 'technical_missed')
    op.drop_column('job_applications', 'assessment_missed')
    op.drop_column('job_applications', 'phone_screen_missed')
