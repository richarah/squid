"""
Test fixtures for SQUID tests.

Provides sample schemas and DMRS parses for testing without ACE/ERG.
"""

import pytest

from squid.schema import Column, ForeignKey, Schema, Table


@pytest.fixture
def concert_singer_schema():
    """
    The concert_singer schema from Spider.

    A simple schema with 3 tables and foreign key relationships.
    """
    return Schema(
        db_id="concert_singer",
        tables=[
            Table(
                name="singer",
                columns=[
                    Column("singer_id", "number", primary_key=True),
                    Column("name", "text"),
                    Column("country", "text"),
                    Column("song_name", "text"),
                    Column("song_release_year", "text"),
                    Column("age", "number"),
                    Column("is_male", "text"),
                ],
                primary_keys=["singer_id"]
            ),
            Table(
                name="concert",
                columns=[
                    Column("concert_id", "number", primary_key=True),
                    Column("concert_name", "text"),
                    Column("theme", "text"),
                    Column("stadium_id", "text"),
                    Column("year", "text"),
                ],
                primary_keys=["concert_id"]
            ),
            Table(
                name="singer_in_concert",
                columns=[
                    Column("concert_id", "number", primary_key=True),
                    Column("singer_id", "text", primary_key=True),
                ],
                primary_keys=["concert_id", "singer_id"]
            ),
        ],
        foreign_keys=[
            ForeignKey("singer_in_concert", "singer_id", "singer", "singer_id"),
            ForeignKey("singer_in_concert", "concert_id", "concert", "concert_id"),
        ]
    )


@pytest.fixture
def simple_schema():
    """
    A minimal schema with one table for basic testing.
    """
    return Schema(
        db_id="simple",
        tables=[
            Table(
                name="students",
                columns=[
                    Column("id", "integer", primary_key=True),
                    Column("name", "text"),
                    Column("age", "integer"),
                    Column("major", "text"),
                ],
                primary_keys=["id"]
            ),
        ],
        foreign_keys=[]
    )


@pytest.fixture
def multi_table_schema():
    """
    A schema with multiple related tables for JOIN testing.
    """
    return Schema(
        db_id="multi_table",
        tables=[
            Table(
                name="customers",
                columns=[
                    Column("customer_id", "integer", primary_key=True),
                    Column("name", "text"),
                    Column("email", "text"),
                ],
                primary_keys=["customer_id"]
            ),
            Table(
                name="orders",
                columns=[
                    Column("order_id", "integer", primary_key=True),
                    Column("customer_id", "integer"),
                    Column("order_date", "date"),
                    Column("total", "real"),
                ],
                primary_keys=["order_id"]
            ),
            Table(
                name="order_items",
                columns=[
                    Column("item_id", "integer", primary_key=True),
                    Column("order_id", "integer"),
                    Column("product_name", "text"),
                    Column("quantity", "integer"),
                    Column("price", "real"),
                ],
                primary_keys=["item_id"]
            ),
        ],
        foreign_keys=[
            ForeignKey("orders", "customer_id", "customers", "customer_id"),
            ForeignKey("order_items", "order_id", "orders", "order_id"),
        ]
    )


# TODO: Add fixtures for sample DMRS objects
# These would be programmatically constructed using PyDelphin
# to test the compiler without requiring ACE/ERG

# Example:
# @pytest.fixture
# def dmrs_how_many_singers():
#     """DMRS for 'How many singers are there?'"""
#     from delphin import dmrs
#     # Construct a DMRS programmatically
#     ...
