"""create master_catalog table

Revision ID: 0001_create_master_catalog
Revises: 
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_create_master_catalog'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'master_catalog',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('mpn', sa.String(), nullable=True),
        sa.Column('upc', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('specs', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table('master_catalog')
