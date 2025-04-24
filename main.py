import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import random
import aiohttp
import json
import datetime
import asyncio
from aiohttp import web 

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

PORT = int(os.getenv('PORT', 8080))

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

secret_role = "Cutie"

app = web.Application()

async def handle_index(request):
    return web.Response(text=f"{bot.user.name} is up and running!")

app.router.add_get('/', handle_index)

async def start_webserver():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

@bot.event
async def on_ready():
    print(f"YAYYY!! We are up and running:) {bot.user.name}")
    await start_webserver()


@bot.event
async def on_member_join(member):
    await member.send(f"HIIIII!! :D, {member.name}!")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "shit" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} don't swear please:(")

    await bot.process_commands(message)


@bot.command()
async def hello(ctx):
    await ctx.send(f"HIII {ctx.author.mention}!!! :D")


@bot.command()
async def assign(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} YAY U got the role: {secret_role}!! :D")
    else:
        await ctx.send("Nooo something went wrong adding the role :(")


@bot.command()
async def remove(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.remove_roles(role)
        await ctx.send(f"{ctx.author.mention} Aw the role {secret_role} has vanished:(")
    else:
        await ctx.send("Nooo something went wrong removing the role:(")


@bot.command()
async def dm(ctx, *, msg):
    await ctx.author.send(f"LOOOKKKK u said: {msg} :D")


@bot.command()
async def cat(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.thecatapi.com/v1/images/search') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(title="Meowww! :cat:", color=discord.Color.purple())
                embed.set_image(url=data[0]['url'])
                await ctx.send(embed=embed)
            else:
                await ctx.send("Oopsie! Couldn't find a kitty right now :(")


@bot.command()
async def dog(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://dog.ceo/api/breeds/image/random') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(title="Woof Woof! :dog:", color=discord.Color.green())
                embed.set_image(url=data['message'])
                await ctx.send(embed=embed)
            else:
                await ctx.send("Oopsie! Couldn't find a doggo right now :(")


@bot.command()
async def joke(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://official-joke-api.appspot.com/random_joke') as response:
            if response.status == 200:
                data = await response.json()
                await ctx.send(f"**{data['setup']}**\n\n||{data['punchline']}|| :sob:")
            else:
                await ctx.send("Oopsie! My joke book is empty right now :(")


@bot.command(aliases=['8ball'])
async def magic8ball(ctx, *, question):
    responses = [
        "Yesss definitely!!", "For sure!!", "Without a doubt!",
        "Hmmmm I think yes!", "You can count on it!",
        "Maybe? ask again later", "Better not tell you now :3",
        "Cannot predict now", "Don't count on it :(",
        "My sources say noooo", "Very doubtful", "NOPE!"
    ]
    await ctx.send(f"🎱 **Question:** {question}\n**Answer:** {random.choice(responses)}")


@bot.command()
async def rps(ctx, choice=None):
    choices = ['rock', 'paper', 'scissors']

    if choice is None:
        instruction_msg = await ctx.send(
            "Let's play Rock Paper Scissors! Type 'rock', 'paper', or 'scissors' now! You have 15 seconds to choose :3")

        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in choices

        try:
            user_response = await bot.wait_for('message', check=check, timeout=15.0)
            user_choice = user_response.content.lower()

            bot_choice = random.choice(choices)

            if user_choice == bot_choice:
                result = "It's a tie!! :o"
            elif (user_choice == 'rock' and bot_choice == 'scissors') or \
                    (user_choice == 'paper' and bot_choice == 'rock') or \
                    (user_choice == 'scissors' and bot_choice == 'paper'):
                result = "You win!! :D"
            else:
                result = "I win!! hehe :3"

            await ctx.send(f"You chose **{user_choice}**, I chose **{bot_choice}**. {result}")

        except asyncio.TimeoutError:
            await ctx.send("Aww you took too long to choose :( Game cancelled!")
            return

    elif choice.lower() in choices:
        user_choice = choice.lower()
        bot_choice = random.choice(choices)

        if user_choice == bot_choice:
            result = "It's a tie!! :o"
        elif (user_choice == 'rock' and bot_choice == 'scissors') or \
                (user_choice == 'paper' and bot_choice == 'rock') or \
                (user_choice == 'scissors' and bot_choice == 'paper'):
            result = "You win!! :D"
        else:
            result = "I win!! hehe :3"

        await ctx.send(f"You chose **{user_choice}**, I chose **{bot_choice}**. {result}")

    else:
        await ctx.send(
            "Please choose rock, paper, or scissors! You can do `!rps rock` or just `!rps` and then type your choice!")


@rps.error
async def rps_error(ctx, error):
    await ctx.send(
        "To play Rock Paper Scissors, you can either:\n1. Type `!rps rock` (or paper/scissors)\n2. OR type `!rps` and then respond with your choice :D my favourite game")


@bot.command()
async def fact(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://uselessfacts.jsph.pl/api/v2/facts/random') as response:
            if response.status == 200:
                data = await response.json()
                await ctx.send(f"**Random Fact:** {data['text']} :D")
            else:
                await ctx.send("Oopsie! My fact book is empty right now :(")


@bot.command()
@commands.has_role(secret_role)
async def secretfact(ctx):
    secret_facts = [
        "When you shuffle a deck of cards, it's likely that your exact arrangement has never been seen before in human history!",
        "The inventor of the frisbee was turned into a frisbee after he died! His ashes were molded into a frisbee!",
        "Dolphins have names for each other and will respond when called!",
        "The original purpose of bubble wrap was to be used as wallpaper!",
        "Nintendo was founded in 1889, before the invention of cars or planes!",
        "Did u know that u are a cutie:)"
    ]
    await ctx.send(f"**🔮 SUPER SECRET FACT I like this one:D :** {random.choice(secret_facts)} :D")


@secretfact.error
async def secretfact_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("Uh oh, you need the special role to see these super secret facts :eyes:")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Hmmmm I don't know that command :( Try using !help to see what I can do!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"Oopsie! You forgot something important for this command :( Try `!help {ctx.command}` to see how to use it!")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Uh oh, I didn't understand what you meant :( Please check your input!")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Woah slow down! Try again in {error.retry_after:.2f} seconds :)")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Sorry, you don't have permission to do this :'(")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("I don't have permission to do that :(")
    elif isinstance(error, commands.MissingRole):
        await ctx.send("You need a special role for that command :(")
    elif isinstance(error, commands.NSFWChannelRequired):
        await ctx.send("This command can only be used in NSFW channels!")
    else:
        logging.error(f"Unexpected error: {error}")
        await ctx.send("Oops! Something went wrong :( Please try again later!")


@bot.command()
async def guess(ctx):
    number = random.randint(1, 100)
    attempts = 0
    max_attempts = 10

    await ctx.send(f"I'm thinking of a number between 1 and 100! You have {max_attempts} tries to guess it! :3")

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel and message.content.isdigit()

    while attempts < max_attempts:
        try:
            guess_msg = await bot.wait_for('message', check=check, timeout=30.0)
            guess = int(guess_msg.content)
            attempts += 1

            if guess == number:
                await ctx.send(
                    f"YAYYYY!!! :partying_face: You got it right in {attempts} attempts! The number was indeed {number}!")
                return
            elif guess < number:
                await ctx.send(f"Too low! Try a higher number! :point_up: ({attempts}/{max_attempts} attempts)")
            else:
                await ctx.send(f"Too high! Try a lower number! :point_down: ({attempts}/{max_attempts} attempts)")

        except asyncio.TimeoutError:
            await ctx.send(f"Oops! You took too long to respond :( The number was {number}.")
            return

    await ctx.send(f"Awww you ran out of attempts :( The number was {number}. Better luck next time!")


@bot.command()
async def poll(ctx, *, question):
    embed = discord.Embed(title="Question:D", description=question)
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("👎")


@poll.error
async def poll_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You need to provide a question for the poll! Try `!poll Should we play a game today?`")


@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.purple())
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)


@avatar.error
async def avatar_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("I couldn't find that user :( Please make sure you spelled their name correctly!")


@bot.command()
async def flip(ctx):
    result = random.choice(["Heads", "Tails"])

    heads_url = "https://i.imgur.com/HavOS71.png"
    tails_url = "https://i.imgur.com/u1pmQMV.png"

    embed = discord.Embed(
        title="Coin Flip!",
        description=f"The coin landed on... **{result}**!",
        color=discord.Color.gold()
    )

    embed.set_image(url=heads_url if result == "Heads" else tails_url)

    await ctx.send(embed=embed)


bot.run(token, log_handler=handler, log_level=logging.DEBUG)