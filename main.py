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
import threading
from flask import Flask
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import time
import sys

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

PORT = int(os.getenv('PORT', 8080))

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

secret_role = "Cutie"

XP_FILE = "user_xp.json"

level_roles = {
    5: "Level 5",
    10: "level 10",
    20: "level 20",
    50: "level 50"
}

user_xp = {}

try:
    if os.path.exists('firebase-key.json'):
        print("Initializing Firebase with local key file...")
        cred = credentials.Certificate('firebase-key.json')
        firebase_admin.initialize_app(cred, {
            'databaseURL': os.getenv('FIREBASE_DB_URL')
        })
        print(f"Firebase initialized with database URL: {os.getenv('FIREBASE_DB_URL')}")
    else:
        import base64
        firebase_key_json = os.getenv('FIREBASE_KEY_JSON')
        if firebase_key_json:
            print("Initializing Firebase with environment key...")
            firebase_key_data = json.loads(base64.b64decode(firebase_key_json).decode('utf-8'))
            cred = credentials.Certificate(firebase_key_data)
            firebase_admin.initialize_app(cred, {
                'databaseURL': os.getenv('FIREBASE_DB_URL')
            })
            print(f"Firebase initialized with database URL: {os.getenv('FIREBASE_DB_URL')}")
        else:
            print("No Firebase credentials found - XP data will not persist between restarts!")
except Exception as e:
    print(f"Error initializing Firebase: {e}")

def load_xp_data():
    global user_xp
    try:
        if firebase_admin._apps:  
            print("Loading XP data from Firebase...")
            xp_ref = db.reference('/xp_data')
            
            firebase_data = xp_ref.get()
            if firebase_data:
                user_xp = firebase_data
                print(f"Successfully loaded XP data for {len(user_xp)} users from Firebase")
                for user_id, xp in user_xp.items():
                    print(f"User {user_id}: {xp} XP, Level {calculate_level(xp)}")
            else:
                print("No XP data found in Firebase, starting fresh")
                user_xp = {}
        else:
            print("Firebase not initialized, trying to load from local file...")
            if os.path.exists(XP_FILE):
                with open(XP_FILE, 'r') as f:
                    content = f.read().strip()
                    if content: 
                        user_xp = json.loads(content)
                        print(f"Loaded XP data for {len(user_xp)} users from local file")
                    else:
                        print("XP file exists but is empty, starting fresh")
                        user_xp = {}
            else:
                print(f"XP file not found at {XP_FILE}, starting fresh")
                user_xp = {}
    except Exception as e:
        print(f"Error loading XP data: {e}")
        traceback.print_exc()  
        user_xp = {}

def save_xp_data():
    try:
        if firebase_admin._apps: 
            xp_ref = db.reference('/xp_data')
            
            print(f"About to save XP data: {len(user_xp)} users with data: {json.dumps(user_xp)[:100]}...")
            
            def transaction_update(current_data):
                if current_data is None:
                    return user_xp
                for user_id, xp in user_xp.items():
                    current_data[user_id] = xp
                return current_data
            
            try:
                xp_ref.transaction(transaction_update)
                print(f"Successfully used transaction to save XP data for {len(user_xp)} users to Firebase")
            except Exception as e:
                print(f"Transaction failed: {e}, falling back to direct set")
                xp_ref.set(user_xp)
                
            time.sleep(1)  
            verification = xp_ref.get()
            if verification:
                all_verified = True
                for user_id, xp in user_xp.items():
                    if user_id not in verification or verification[user_id] != xp:
                        all_verified = False
                        print(f"Verification failed for user {user_id}: expected {xp}, got {verification.get(user_id, 'missing')}")
                
                if all_verified:
                    print("Firebase save verified successfully!")
                else:
                    print("Firebase save verification partially failed!")
            else:
                print("Firebase save verification completely failed - no data returned!")
        
        with open(XP_FILE, 'w') as f:
            json.dump(user_xp, f, indent=2)
            print(f"Saved XP data backup to local file")
            
        print(f"Current user_xp content (first 3 entries):")
        entries = 0
        for user_id, xp in user_xp.items():
            if entries < 3:  
                print(f"  User {user_id}: {xp} XP")
                entries += 1
            
    except Exception as e:
        print(f"Error saving XP data: {e}", file=sys.stderr)
        traceback.print_exc() 
        try:
            with open(XP_FILE, 'w') as f:
                json.dump(user_xp, f)
                print(f"Saved XP data to local file after Firebase failure")
        except Exception as e2:
            print(f"Failed to save XP data anywhere: {e2}", file=sys.stderr)
            traceback.print_exc()

def calculate_level(xp):
    return int((xp / 100) ** 0.5)

def xp_for_level(level):
    return int(level ** 2 * 100)

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
    
    load_xp_data()
    
    await start_webserver()
    
    bot.loop.create_task(periodic_save())
    print("Periodic save task started")

async def periodic_save():
    """Periodically save XP data"""
    while True:
        try:
            await asyncio.sleep(60)  
            if user_xp:
                print(f"Performing periodic XP data save at {datetime.datetime.now()}")
                save_xp_data()
                print(f"Periodic save completed at {datetime.datetime.now()}")
        except Exception as e:
            print(f"Error in periodic save: {e}")
            traceback.print_exc()

@bot.command()
@commands.is_owner()
async def forcesave(ctx):
    """Force save XP data (bot owner only)"""
    try:
        save_xp_data()
        await ctx.send("XP data forcibly saved!")
    except Exception as e:
        await ctx.send(f"Error saving XP data: {e}")
        traceback.print_exc()

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

    if not message.author.bot and message.guild is not None:
        user_id = str(message.author.id)
        
        if user_id in user_xp:
            print(f"Before update: User {user_id} has {user_xp[user_id]} XP")
        else:
            print(f"Before update: User {user_id} is new, starting with 0 XP")
            user_xp[user_id] = 0
            
        old_level = calculate_level(user_xp[user_id])
        old_xp = user_xp[user_id]
        
        xp_gain = random.randint(5, 15)
        user_xp[user_id] += xp_gain
        
        print(f"XP UPDATE: User {user_id} gained {xp_gain} XP: {old_xp} -> {user_xp[user_id]}")
        
        print(f"Saving XP data after update for user {user_id}")
        save_xp_data()
        print(f"Save complete. User {user_id} now has {user_xp[user_id]} XP")
        
        new_level = calculate_level(user_xp[user_id])
        
        if new_level > old_level:
            level_up_embed = discord.Embed(
                title="🌟 LEVEL UP! 🌟",
                description=f"WOOHOOOOOO {message.author.mention} just reached level **{new_level}** YIPEEE!!!",
                color=discord.Color.gold()
            )
            level_up_embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
            await message.channel.send(embed=level_up_embed)
            
            if new_level in level_roles:
                role_name = level_roles[new_level]
                role = discord.utils.get(message.guild.roles, name=role_name)
                
                if role:
                    await message.author.add_roles(role)
                    await message.channel.send(f"✨YAYYYY {message.author.mention} has earned the **{role_name}** role! :D ✨")
                else:

                    print(f"Oh no, role {role_name} was not found in server {message.guild.name}")

    await bot.process_commands(message)

@bot.command()
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    
    if user_id not in user_xp:
        return await ctx.send(f"{member.name} hasn't earned any XP yet :(")
    
    xp = user_xp[user_id]
    level = calculate_level(xp)
    next_level = level + 1
    next_level_xp = xp_for_level(next_level)
    current_level_xp = xp_for_level(level)
    
    progress = (xp - current_level_xp) / (next_level_xp - current_level_xp) * 100 if next_level_xp > current_level_xp else 100
    
    embed = discord.Embed(
        title=f"{member.name}'s Level Stats :sparkles:",
        color=discord.Color.blue()
    )
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp}/{next_level_xp}", inline=True)
    embed.add_field(name="Progress to Level {}".format(next_level), value=f"{progress:.1f}%", inline=True)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command()
async def ranks(ctx):
    embed = discord.Embed(
        title="Level Ranks :trophy:",
        description="Here are the special roles you can earn by leveling up!",
        color=discord.Color.gold()
    )
    
    for level, role_name in sorted(level_roles.items()):
        embed.add_field(name=f"Level {level}", value=role_name, inline=False)
        
    await ctx.send(embed=embed)

@bot.command()
async def hug(ctx, member: discord.Member = None):
    if member is None:
        return await ctx.send("Who do you want to hug? Try `!hug @username :3`")
    
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.waifu.pics/sfw/hug') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(
                    title=f"{ctx.author.name} gives {member.name} a big hug! :D",
                    color=discord.Color.purple()
                )
                embed.set_image(url=data['url'])
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"HUGGIES TO {member.mention} from {ctx.author.mention}!!!")

@bot.command()
async def slap(ctx, member: discord.Member = None):
    if member is None:
        return await ctx.send("Who do you want to slap? Try `!slap @username`")
    
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.waifu.pics/sfw/slap') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(
                    title=f"{ctx.author.name} slaps {member.name}!! ",
                    color=discord.Color.red()
                )
                embed.set_image(url=data['url'])
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"{ctx.author.mention} slaps {member.mention}!")

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
            "Please choose rock, paper, or scissors! You can do `!rps rock` (or paper/scissors) or just `!rps` and then type your choice!")


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
        await ctx.send("You need to provide a question for the poll! Try `!poll Should we play a game today?` :3")

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

    heads_url = "https://i.imgur.com/jTGm7MF.png"
    tails_url = "https://i.imgur.com/u1pmQMV.png"

    embed = discord.Embed(
        title="Coin Flip!",
        description=f"The coin landed on... **{result}**! :o",
        color=discord.Color.gold()
    )

    embed.set_image(url=heads_url if result == "Heads" else tails_url)

    await ctx.send(embed=embed)

@bot.command()
async def wyr(ctx):
    """Would You Rather - Presents two crazy choices"""
    # static list of questions for now since the api for this doesnt work in my case ill be researching this later.
    wyr_questions = [
        ["Eat a pizza with pineapple", "Eat a burger with chocolate sauce"],
        ["Have the ability to talk to animals", "Have the ability to speak all human languages"],
        ["Be able to teleport anywhere", "Be able to read minds"],
        ["Live in the future", "Live in the past"],
        ["Always have to say everything on your mind", "Never speak again"],
        ["Be famous for your talent", "Be incredibly rich but unknown"],
        ["Never use social media again", "Never watch movies or TV shows again"],
        ["Have unlimited food", "Have unlimited money"],
        ["Be able to fly", "Be invisible whenever you want"],
        ["Live underwater", "Live in space"],
        ["Always be slightly too hot", "Always be slightly too cold"],
        ["Have hands for feet", "Have feet for hands"],
        ["Know how you will die", "Know when you will die"],
        ["Be covered in fur", "Be covered in scales"],
        ["Never sleep again", "Sleep for 12 hours every day and never feel tired"],
        ["Be a famous actor", "Be a famous musician"],
        ["Travel to the past", "Travel to the future"],
        ["Lose the ability to read", "Lose the ability to speak"],
        ["Give up your smartphone forever", "Give up dessert forever"],
        ["Be 10 years older", "Be 10 years younger"],
        ["Have super strength", "Have super speed"],
        ["Always be overdressed", "Always be underdressed"],
        ["Live without the internet", "Live without AC/heating"],
        ["Be able to see 10 minutes into the future", "Be able to see 10 minutes into the past"],
        ["Always have to tell the truth", "Always have to lie"],
        ["Be fluent in all languages", "Be a master of all musical instruments"],
        ["Have one real-life 'get out of jail free' card", "Have one real-life 'undo button'"],
        ["Have all traffic lights turn green for you", "Never have to stand in line again"],
        ["Save 100 strangers", "Save 1 loved one"],
        ["Fight 1 horse-sized duck", "Fight 100 duck-sized horses"],
        ["Have unlimited sushi", "Have unlimited tacos"],
        ["Be a superhero", "Be a wizard"],
        ["Live in a world with zombies", "Live in a world with aliens"],
        ["Never have to clean again", "Never have to do laundry again"],
        ["Be the funniest person alive", "Be the smartest person alive"],
        ["Know when you'll die", "Know how you'll die"],
        ["Win the lottery", "Live twice as long"],
        ["Be famous", "Be anonymous forever"],
        ["Always have bad WiFi", "Always have bad phone signal"],
        ["Be a dragon", "Be a unicorn"]
    ]
    
    options = random.choice(wyr_questions)
    
    embed = discord.Embed(
        title="Would You Rather...? :3",
        description="React to choose! :)",
        color=discord.Color.blue()
    )
    embed.add_field(name="🅰️", value=f"Option A: {options[0]}", inline=False)
    embed.add_field(name="🅱️", value=f"Option B: {options[1]}", inline=False)
    
    message = await ctx.send(embed=embed)
    await message.add_reaction("🅰️")
    await message.add_reaction("🅱️")

@bot.command()
async def remind(ctx, time, *, reminder="Reminder! :D"):

    
    user = ctx.author
    
    time_convert = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    time_unit = time[-1].lower()
    
    if time_unit not in time_convert:
        return await ctx.send("Please use s, m, h, or d for seconds, minutes, hours, or days! Example: `10m` :3")
    
    try:
        amount = int(time[:-1])
    except ValueError:
        return await ctx.send("Please provide a valid number! Example: `10m` :3")
    
    seconds = amount * time_convert[time_unit]
    
    embed = discord.Embed(
        title="Reminder Set! :3",
        description=f"I'll remind you about: **{reminder} :D**",
        color=discord.Color.blue()
    )
    
    if time_unit == "s":
        time_text = f"{amount} second(s)"
    elif time_unit == "m":
        time_text = f"{amount} minute(s)"
    elif time_unit == "h":
        time_text = f"{amount} hour(s)"
    else:
        time_text = f"{amount} day(s)"
    
    embed.add_field(name="⏱️ Time", value=time_text)
    await ctx.send(embed=embed)
    
    await asyncio.sleep(seconds)
    
    reminder_embed = discord.Embed(
        title="REMINDER!! ",
        description=f"{reminder}",
        color=discord.Color.red()
    )
    
    await ctx.send(f"Heyy {user.mention}, here's your reminder!! :3", embed=reminder_embed)

@remind.error
async def remind_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide a time! Example: `!remind 10m Drink water!`")

@bot.command()
async def ship(ctx, user1: discord.Member, user2: discord.Member = None):

    
    if user2 is None:
        user2 = user1
        user1 = ctx.author
    
    if user1.id == user2.id:
        ship_percentage = 100
    else:
        combined_id = str(min(user1.id, user2.id)) + str(max(user1.id, user2.id))
        seed = int(combined_id) % 10000  
        random.seed(seed)
        ship_percentage = random.randint(0, 100)
        random.seed() 
    
    name1 = user1.display_name
    name2 = user2.display_name
    first_half = name1[:len(name1)//2]
    second_half = name2[len(name2)//2:]
    ship_name = first_half + second_half
    
    if ship_percentage < 20:
        color = discord.Color.red()
        message = "Uh oh.. Maybe just be friends :("
        emoji = "💔"
    elif ship_percentage < 40:
        color = discord.Color.orange()
        message = "Hmm, could be better! :3"
        emoji = "🧡"
    elif ship_percentage < 60:
        color = discord.Color.yellow()
        message = "Ooooo ;) You might have something there!"
        emoji = "💫"
    elif ship_percentage < 80:
        color = discord.Color.green()
        message = "WOAHHHHH :o You two would be so cute together!!"
        emoji = "💚"
    elif ship_percentage < 100:
        color = discord.Color.purple()
        message = "WOWIE this is insane! You two are meant to be!!"
        emoji = "💜"
    else:
        color = discord.Color.magenta()
        message = "PERFECT MATCH!! TRUE LOVE!!"
        emoji = "💞"
    
    embed = discord.Embed(
        title=f"{emoji} Relationship Calculator {emoji}",
        description=f"**{user1.display_name}** + **{user2.display_name}** = **{ship_name}**",
        color=color
    )
    
    embed.add_field(name="Compatibility", value=f"**{ship_percentage}%**", inline=True)
    embed.add_field(name="Result", value=message, inline=True)
    
    await ctx.send(embed=embed)

@ship.error
async def ship_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You need to mention at least one user! Example: `!ship @user`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("I couldn't find that user! Make sure you're @mentioning them correctly!")

# pure for debuging purposes
@bot.command()
@commands.is_owner()
async def rawxp(ctx):
    """View raw XP data (bot owner only)"""
    if len(user_xp) == 0:
        await ctx.send("No XP data found!")
        return
        
    data_str = json.dumps(user_xp, indent=2)
    if len(data_str) > 1900: 
        await ctx.send(f"XP data (truncated, {len(user_xp)} users):\n```json\n{data_str[:1900]}...\n```")
    else:
        await ctx.send(f"XP data ({len(user_xp)} users):\n```json\n{data_str}\n```")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)