"""Tests for squid.schema module."""

import pytest

from squid.schema import Column, ForeignKey, Schema, Table


def test_table_creation():
    """Test Table dataclass creation."""
    table = Table(
        name="students",
        columns=[
            Column("id", "integer", primary_key=True),
            Column("name", "text"),
        ],
        primary_keys=["id"]
    )

    assert table.name == "students"
    assert len(table.columns) == 2
    assert table.column_names() == ["id", "name"]


def test_schema_creation():
    """Test Schema dataclass creation."""
    schema = Schema(
        db_id="test",
        tables=[
            Table(
                name="students",
                columns=[Column("id", "integer", primary_key=True)],
                primary_keys=["id"]
            )
        ],
        foreign_keys=[]
    )

    assert schema.db_id == "test"
    assert len(schema.tables) == 1
    assert schema.table_names() == ["students"]


def test_schema_has_table(simple_schema):
    """Test schema.has_table()."""
    assert simple_schema.has_table("students")
    assert not simple_schema.has_table("nonexistent")


def test_schema_get_table(simple_schema):
    """Test schema.get_table()."""
    table = simple_schema.get_table("students")
    assert table is not None
    assert table.name == "students"

    assert simple_schema.get_table("nonexistent") is None


def test_schema_column_names(simple_schema):
    """Test schema.column_names()."""
    columns = simple_schema.column_names("students")
    assert "id" in columns
    assert "name" in columns
    assert "age" in columns
    assert "major" in columns


def test_schema_column_type(simple_schema):
    """Test schema.column_type()."""
    assert simple_schema.column_type("students", "id") == "integer"
    assert simple_schema.column_type("students", "name") == "text"
    assert simple_schema.column_type("students", "age") == "integer"


def test_fk_graph(concert_singer_schema):
    """Test foreign key graph construction."""
    graph = concert_singer_schema.fk_graph()

    assert graph.number_of_nodes() == 3
    assert graph.has_edge("singer_in_concert", "singer")
    assert graph.has_edge("singer_in_concert", "concert")


def test_find_join_path(concert_singer_schema):
    """Test finding join paths between tables."""
    path = concert_singer_schema.find_join_path("singer", "concert")

    assert path is not None
    assert "singer" in path
    assert "singer_in_concert" in path
    assert "concert" in path


def test_case_insensitive_lookups(simple_schema):
    """Test that schema lookups are case-insensitive."""
    assert simple_schema.has_table("students")
    assert simple_schema.has_table("STUDENTS")
    assert simple_schema.has_table("Students")

    table = simple_schema.get_table("STUDENTS")
    assert table is not None
    assert table.name == "students"
