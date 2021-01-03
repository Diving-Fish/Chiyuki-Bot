import aiosqlite
import sqlite3
import asyncio


async def init_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect("src/static/chiyuki.db")
    cursor = await db.cursor()
    try:
        await cursor.executescript(
            "create table group_poke_table (group_id bigint primary key not null, last_trigger_time int, triggered int, disabled bit, strategy text);"
            "create table user_poke_table (user_id bigint, group_id bigint, triggered int);")

    except sqlite3.OperationalError:
        pass
    return db


db = asyncio.new_event_loop().run_until_complete(init_db())


async def cursor() -> aiosqlite.Cursor:
    return await db.cursor()


async def commit():
    await db.commit()
