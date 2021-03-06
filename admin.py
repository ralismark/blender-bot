#!/usr/bin/env python3

"""
Commands related to the management of the bot (but not core to functionality)
"""

import ast
import asyncio
import logging
import random
import traceback

import discord
from discord.ext import commands

from base import fragment, sql, resolver

setup = fragment.Fragment()
_L = logging.getLogger(__name__)

@setup.command("!sql", hidden=True)
@commands.is_owner()
async def sql_query(ctx, *, query):
    """
    Run a SQL query
    """
    buffered = ""
    try:
        for row in sql.query(query):
            line = "\t".join(map(repr, row)) + "\n"
            if len(buffered) + len(line) >= 2000 - 50: # Some extra leeway
                # flush
                await ctx.send(f"```\n{buffered}```")
                buffered = ""
            buffered += line

        await ctx.send(f"```\n{buffered}```")
    except Exception as error:
        await ctx.send(f"err: {error}")

@setup.command("!exec", hidden=True)
@commands.is_owner()
async def execute(ctx, *, code):
    """
    Run python code in this context
    """
    _L.warning("exec: %s", code)

    async def async_exec(stmts, env=None):
        parsed_stmts = ast.parse(stmts)

        fn_name = "_async_exec_f"

        fn = f"async def {fn_name}(): pass"
        parsed_fn = ast.parse(fn)

        for node in parsed_stmts.body:
            ast.increment_lineno(node)

        parsed_fn.body[0].body = parsed_stmts.body
        exec(compile(parsed_fn, filename="<ast>", mode="exec"), env)

        return await eval(f"{fn_name}()", env)

    try:
        # pylint: disable=exec-used
        await async_exec(code, {"ctx": ctx})
        # pylint: enable=exec-used
    except Exception as error:
        exc_traceback = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await ctx.send(f"```{exc_traceback}```")
    else:
        await ctx.message.add_reaction("✅")

@setup.command("!delete", hidden=True)
@commands.is_owner()
async def delete(ctx, *messages: int):
    """
    Deletes a message
    """
    for msg in messages:
        message = await ctx.channel.fetch_message(msg)
        await message.delete()
    await ctx.message.add_reaction("✅")

@setup.command("!chatlog", hidden=True)
@commands.bot_has_permissions(read_message_history=True)
@commands.is_owner()
async def chatlog(ctx, *, channel: commands.TextChannelConverter = None):
    """
    Get chat log
    """
    import io
    import zlib

    if channel is None:
        channel = ctx.channel

    compress = zlib.compressobj(level=9, wbits=zlib.MAX_WBITS + 16)
    log = bytearray()

    msgcount = 0
    charcount = 0
    logcount = 0

    pending = await ctx.send("pending...")
    async with ctx.channel.typing():
        async for msg in channel.history(limit=None, oldest_first=True):
            created = msg.created_at.strftime("%y-%m-%d %H:%M:%S")
            line = f"[{created}] {msg.author}: {msg.clean_content}"
            if msg.attachments:
                filelist = ", ".join(f"{f.filename}:{f.url}" for f in msg.attachments)
                line += f" [attached: {filelist}]"
            if msg.embeds:
                plural = "s" if len(msg.embeds) > 1 else ""
                line += f" [{len(msg.embeds)} embed{plural}]"

            encoded = (line + "\n").encode()
            log += compress.compress(encoded)

            msgcount += 1
            charcount += len(msg.content)
            logcount += len(encoded)

            if msgcount % 500 == 0:
                await pending.edit(content=f"{msgcount} processed, up to {created}", suppress=False)

        log += compress.flush()

    await pending.delete()
    msg = await ctx.send(
        f"{ctx.author.mention} {charcount} characters across {msgcount} messages. "
        f"Log {logcount//1000} kb long, compressed to {len(log)//1000} kb",
        file=discord.File(io.BytesIO(log), filename=f"{channel.guild.name}--{channel.name}.gz"))

    await ctx.author.send(f"chatlog done -> {msg.jump_url}")

@setup.command("whois")
async def whois(ctx, *, userid: int):
    """
    Find someone's username from just their userid
    """
    user = await resolver.fetch_user_maybe(userid)
    await ctx.send(f"{userid} = {user}", delete_after=10)

@setup.command("hello")
async def hellothere(ctx):
    await ctx.message.add_reaction("✅")

@setup.task
async def activity_randomiser():
    """
    Randomly set an activity
    """
    activities = [
        discord.Activity(type=discord.ActivityType.watching, name="you"),
        discord.Activity(type=discord.ActivityType.watching, name="🔺 to upvote!"),
        discord.Activity(type=discord.ActivityType.playing, name="as a human"),
        discord.Activity(type=discord.ActivityType.playing, name="'a nice game of chess'"),
        ]
    while True:
        setup.bot.activity = random.choice(activities)
        _L.info("Randomising activity")
        await asyncio.sleep(60*60)
