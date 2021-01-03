import aiosqlite
import sqlite3
import asyncio


class G:
    db = None


async def init_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect("src/static/chiyuki.db")
    cursor = await db.cursor()
    try:
        await cursor.executescript(
            "create table group_poke_table (group_id bigint primary key not null, last_trigger_time int, triggered int, disabled bit, strategy text);"
            "create table user_poke_table (user_id bigint, group_id bigint, triggered int);")

    except sqlite3.OperationalError:
        pass
    G.db = db


async def cursor() -> aiosqlite.Cursor:
    if G.db is None:
        await init_db()
    return await G.db.cursor()


async def commit():
    if G.db is None:
        await init_db()
    await G.db.commit()
