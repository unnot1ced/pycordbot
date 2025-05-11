import discord
from discord import option
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
import traceback

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

PORT = int(os.getenv('PORT', 8080))

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Bot(intents=intents)

secret_role = "Cutie"

XP_FILE = "user_xp.json"

level_roles = {
    5: "Level 5",
    10: "level 10",
    20: "level 20",
    50: "level 50"
}

user_xp = {}

swear_words = [
    "shit", "fuck", "damn", "bitch", "asshole", "bastard", 
    "cunt", "dick", "piss", "cock", "pussy", 
    "ass", "hell", "whore", "hoe", "slut", "bullshit", 
    "motherfucker", "fucker", "dickhead", "fuk", "fck", "f*ck",
    "s*it", "b*tch", "a$$", "a$$hole", "sh*t", "b!tch", "d!ck",
    "f**k", "sh!t", "a**", "a**hole", "p*ssy", "c*nt"
]

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

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    message_lower = message.content.lower()
    for word in swear_words:
        if word in message_lower.split(): 
            await message.delete()
            await message.channel.send(f"{message.author.mention} don't swear please:(")
            break

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

@bot.slash_command(name="level", description="Check your level or another user's level")
@option("member", discord.Member, description="Member to check level for", required=False)
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    
    if user_id not in user_xp:
        return await ctx.respond(f"{member.name} hasn't earned any XP yet :(")
    
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
    
    await ctx.respond(embed=embed)

@bot.slash_command(name="ranks", description="See available level ranks")
async def ranks(ctx):
    embed = discord.Embed(
        title="Level Ranks :trophy:",
        description="Here are the special roles you can earn by leveling up!",
        color=discord.Color.gold()
    )
    
    for level, role_name in sorted(level_roles.items()):
        embed.add_field(name=f"Level {level}", value=role_name, inline=False)
        
    await ctx.respond(embed=embed)

@bot.slash_command(name="hug", description="Give someone a big hug!")
@option("member", discord.Member, description="Member to hug", required=True)
async def hug(ctx, member: discord.Member):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.waifu.pics/sfw/hug') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(
                    title=f"{ctx.author.name} gives {member.name} a big hug! :D",
                    color=discord.Color.purple()
                )
                embed.set_image(url=data['url'])
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"HUGGIES TO {member.mention} from {ctx.author.mention}!!!")

@bot.slash_command(name="slap", description="Slap someone!")
@option("member", discord.Member, description="Member to slap", required=True)
async def slap(ctx, member: discord.Member):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.waifu.pics/sfw/slap') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(
                    title=f"{ctx.author.name} slaps {member.name}!! ",
                    color=discord.Color.red()
                )
                embed.set_image(url=data['url'])
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"{ctx.author.mention} slaps {member.mention}!")

@bot.slash_command(name="hello", description="Get a friendly hello from the bot")
async def hello(ctx):
    await ctx.respond(f"HIII {ctx.author.mention}!!! :D")

@bot.slash_command(name="assign", description="Assign yourself the secret role")
async def assign(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.add_roles(role)
        await ctx.respond(f"{ctx.author.mention} YAY U got the role: {secret_role}!! :D")
    else:
        await ctx.respond("Nooo something went wrong adding the role :(")

@bot.slash_command(name="remove", description="Remove the secret role from yourself")
async def remove(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.remove_roles(role)
        await ctx.respond(f"{ctx.author.mention} Aw the role {secret_role} has vanished:(")
    else:
        await ctx.respond("Nooo something went wrong removing the role:(")

@bot.slash_command(name="dm", description="Have the bot DM you a message")
@option("msg", str, description="The message to send", required=True)
async def dm(ctx, msg: str):
    await ctx.author.send(f"LOOOKKKK u said: {msg} :D")
    await ctx.respond("Check your DMs! :envelope_with_arrow:", ephemeral=True)

@bot.slash_command(name="cat", description="Get a random cat picture")
async def cat(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.thecatapi.com/v1/images/search') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(title="Meowww! :cat:", color=discord.Color.purple())
                embed.set_image(url=data[0]['url'])
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("Oopsie! Couldn't find a kitty right now :(")

@bot.slash_command(name="dog", description="Get a random dog picture")
async def dog(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://dog.ceo/api/breeds/image/random') as response:
            if response.status == 200:
                data = await response.json()
                embed = discord.Embed(title="Woof Woof! :dog:", color=discord.Color.green())
                embed.set_image(url=data['message'])
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("Oopsie! Couldn't find a doggo right now :(")

@bot.slash_command(name="joke", description="Get a random joke")
async def joke(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://official-joke-api.appspot.com/random_joke') as response:
            if response.status == 200:
                data = await response.json()
                await ctx.respond(f"**{data['setup']}**\n\n||{data['punchline']}|| :sob:")
            else:
                await ctx.respond("Oopsie! My joke book is empty right now :(")

@bot.slash_command(name="magic8ball", description="Ask the magic 8-ball a question")
@option("question", str, description="Your yes/no question", required=True)
async def magic8ball(ctx, question: str):
    responses = [
        "Yesss definitely!!", "For sure!!", "Without a doubt!",
        "Hmmmm I think yes!", "You can count on it!",
        "Maybe? ask again later", "Better not tell you now :3",
        "Cannot predict now", "Don't count on it :(",
        "My sources say noooo", "Very doubtful", "NOPE!"
    ]
    await ctx.respond(f"🎱 **Question:** {question}\n**Answer:** {random.choice(responses)}")

@bot.slash_command(name="rps", description="Play Rock Paper Scissors with the bot")
@option("choice", str, description="Your choice (rock, paper, or scissors)", choices=["rock", "paper", "scissors"], required=True)
async def rps(ctx, choice: str):
    choices = ['rock', 'paper', 'scissors']
    bot_choice = random.choice(choices)
    
    if choice == bot_choice:
        result = "It's a tie!! :o"
    elif (choice == 'rock' and bot_choice == 'scissors') or \
            (choice == 'paper' and bot_choice == 'rock') or \
            (choice == 'scissors' and bot_choice == 'paper'):
        result = "You win!! :D"
    else:
        result = "I win!! hehe :3"
    
    await ctx.respond(f"You chose **{choice}**, I chose **{bot_choice}**. {result}")

@bot.slash_command(name="fact", description="Get a random useless fact")
async def fact(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://uselessfacts.jsph.pl/api/v2/facts/random') as response:
            if response.status == 200:
                data = await response.json()
                await ctx.respond(f"**Random Fact:** {data['text']} :D")
            else:
                await ctx.respond("Oopsie! My fact book is empty right now :(")

@bot.slash_command(name="secretfact", description="Get a super secret fact")
async def secretfact(ctx):
    if not discord.utils.get(ctx.author.roles, name=secret_role):
        return await ctx.respond("Uh oh, you need the special role to see these super secret facts :eyes:", ephemeral=True)
        
    secret_facts = [
        "When you shuffle a deck of cards, it's likely that your exact arrangement has never been seen before in human history!",
        "The inventor of the frisbee was turned into a frisbee after he died! His ashes were molded into a frisbee!",
        "Dolphins have names for each other and will respond when called!",
        "The original purpose of bubble wrap was to be used as wallpaper!",
        "Nintendo was founded in 1889, before the invention of cars or planes!",
        "Did u know that u are a cutie:)"
    ]
    await ctx.respond(f"**🔮 SUPER SECRET FACT I like this one:D :** {random.choice(secret_facts)} :D")

@bot.slash_command(name="guess", description="Play a number guessing game")
async def guess(ctx):
    number = random.randint(1, 100)
    await ctx.respond(f"I'm thinking of a number between 1 and 100! Use the buttons below to guess!")
    
  
    view = GuessView(ctx.author, number)
    await ctx.respond("Guess a number between 1 and 100!", view=view)


@bot.slash_command(name="simpleguessgame", description="Play a simplified number guessing game")
async def simpleguessgame(ctx):
    await ctx.respond("I've picked a number between 1 and 100. Use /guess_number to make guesses!")
    if not hasattr(bot, 'guess_games'):
        bot.guess_games = {}
    bot.guess_games[ctx.author.id] = {'number': random.randint(1, 100), 'attempts': 0, 'max_attempts': 10}

@bot.slash_command(name="guess_number", description="Make a guess for the number game")
@option("number", int, description="Your guess (1-100)", min_value=1, max_value=100, required=True)
async def guess_number(ctx, number: int):
    if not hasattr(bot, 'guess_games') or ctx.author.id not in bot.guess_games:
        return await ctx.respond("You don't have an active guessing game! Start one with /simpleguessgame")
    
    game = bot.guess_games[ctx.author.id]
    game['attempts'] += 1
    
    if number == game['number']:
        await ctx.respond(f"YAYYYY!!! :partying_face: You got it right in {game['attempts']} attempts! The number was indeed {game['number']}!")
        del bot.guess_games[ctx.author.id]
    elif game['attempts'] >= game['max_attempts']:
        await ctx.respond(f"Awww you ran out of attempts :( The number was {game['number']}. Better luck next time!")
        del bot.guess_games[ctx.author.id]
    elif number < game['number']:
        await ctx.respond(f"Too low! Try a higher number! :point_up: ({game['attempts']}/{game['max_attempts']} attempts)")
    else:
        await ctx.respond(f"Too high! Try a lower number! :point_down: ({game['attempts']}/{game['max_attempts']} attempts)")

@bot.slash_command(name="poll", description="Create a simple yes/no poll")
@option("question", str, description="The poll question", required=True)
async def poll(ctx, question: str):
    embed = discord.Embed(title="Question:D", description=question)
    message = await ctx.respond(embed=embed)
    
    message = await ctx.fetch_message(message.id)
    await message.add_reaction("👍")
    await message.add_reaction("👎")

@bot.slash_command(name="avatar", description="Show a user's avatar")
@option("member", discord.Member, description="Member whose avatar to show", required=False)
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.purple())
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.respond(embed=embed)

@bot.slash_command(name="flip", description="Flip a coin")
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

    await ctx.respond(embed=embed)

@bot.slash_command(name="wyr", description="Would You Rather game")
async def wyr(ctx):
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
    
    message = await ctx.respond(embed=embed)
    message = await ctx.fetch_message(message.id)
    await message.add_reaction("🅰️")
    await message.add_reaction("🅱️")

@bot.slash_command(name="remind", description="Set a reminder")
@option("time_value", int, description="Time amount", required=True)
@option("time_unit", str, description="Time unit", choices=["seconds", "minutes", "hours", "days"], required=True)
@option("reminder", str, description="What to remind you about", required=True)
async def remind(ctx, time_value: int, time_unit: str, reminder: str):
    user = ctx.author
    
    time_convert = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}
    seconds = time_value * time_convert[time_unit]
    
    embed = discord.Embed(
        title="Reminder Set! :3",
        description=f"I'll remind you about: **{reminder} :D**",
        color=discord.Color.blue()
    )
    
    time_text = f"{time_value} {time_unit}"
    
    embed.add_field(name="⏱️ Time", value=time_text)
    await ctx.respond(embed=embed)
    
    await asyncio.sleep(seconds)
    
    reminder_embed = discord.Embed(
        title="REMINDER!! ",
        description=f"{reminder}",
        color=discord.Color.red()
    )
    
   
    try:
        await user.send(f"Heyy {user.mention}, here's your reminder!! :3", embed=reminder_embed)
    except discord.errors.Forbidden:
        
        try:
            await ctx.channel.send(f"Heyy {user.mention}, here's your reminder!! :3", embed=reminder_embed)
        except:
            pass 

@bot.slash_command(name="ship", description="Ship two users together")
@option("user1", discord.Member, description="First person", required=True)
@option("user2", discord.Member, description="Second person (optional)", required=False)
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
    
    await ctx.respond(embed=embed)

# for debugging purposes this is only to forcesave if the xp save fails. DO NOT USE RANDOMLY AS THIS CAN CAUSE DESYNC ISSUES
@bot.slash_command(name="forcesave", description="Force save XP data (bot owner only)")
async def forcesave(ctx):

    if ctx.author.id != bot.owner_id:
        return await ctx.respond("Sorry, only the bot owner can use this command.", ephemeral=True)
    
    try:
        save_xp_data()
        await ctx.respond("XP data forcibly saved!")
    except Exception as e:
        await ctx.respond(f"Error saving XP data: {e}")
        traceback.print_exc()

@bot.slash_command(name="rawxp", description="View raw XP data (bot owner only)")
async def rawxp(ctx):

    if ctx.author.id != bot.owner_id:
        return await ctx.respond("Sorry, only the bot owner can use this command.", ephemeral=True)
    
    if len(user_xp) == 0:
        await ctx.respond("No XP data found!")
        return
        
    data_str = json.dumps(user_xp, indent=2)
    if len(data_str) > 1900: 
        await ctx.respond(f"XP data (truncated, {len(user_xp)} users):\n```json\n{data_str[:1900]}...\n```")
    else:
        await ctx.respond(f"XP data ({len(user_xp)} users):\n```json\n{data_str}\n```")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)