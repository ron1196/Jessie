import discord
from discord.ext import commands
import asyncio
import json
import os
import difflib
import sys
import pickle
import dropbox
from urllib.request import urlopen

class NestMap:
    def __init__(self):
        self.locToPoke = {}
        self.pokeToLoc = {}
        
    def addNest(self, location, pokemon):
        lastPokemonReported = self.locToPoke.get(location['name_eng'], None)
        if lastPokemonReported:
            if pokemon == lastPokemonReported:
                return
            self.pokeToLoc[lastPokemonReported].remove(location)
        
        self.locToPoke[ location['name_eng'] ] = pokemon
        
        if not self.pokeToLoc.get(pokemon, None):
            self.pokeToLoc[pokemon] = []
        self.pokeToLoc[pokemon].append(location)
        
    def removeNest(self, location):
        lastPokemonReported = self.locToPoke.get(location['name_eng'], None)
        if lastPokemonReported:
            self.pokeToLoc[lastPokemonReported] = [x for x in self.pokeToLoc[lastPokemonReported] if not x['name_eng'] == location['name_eng']]
        del self.locToPoke[location['name_eng']]

TOKEN = 'NDA5OTc0Mzc5MzE3OTUyNTIz.DYmdug.9s14UBTOWKccf93ISi24d9wrhEE'
Jessie = commands.Bot(command_prefix='!', owner_id=195097871626928128)

DROPBOX_TOKEN = "bUcu0SDbjZQAAAAAAAAIDuGE3CPVOfRfrF3XkcXHzKBtYAfdpgyGdQVqWodaXpQR"

pokemons = []
locations = {}

def load_data():
    global guild_dict
    try:
        with open(os.path.join('data', 'guild_dict'), 'rb') as fd:
            guild_dict = pickle.load(fd)
    except OSError:
        with open(os.path.join('data', 'guild_dict'), 'wb') as fd:
            guild_dict = {}
            pickle.dump(guild_dict, fd, (- 1))
            
    global pokemons
    with open(os.path.join('data', 'pokemons.json'), 'r') as fd:
        pokemons = json.load(fd)['pokemon_list']
    
    global locations
    try:
        with urlopen("https://www.dropbox.com/s/8lkr25odjen8wvr/locations.json?dl=1" ) as response:
            html_response = response.read()
            encoding = response.headers.get_content_charset('utf-8-sig')
            locations_data = html_response.decode(encoding)
            locations = json.loads(locations_data)            
            with open(os.path.join('data', 'locations.json'), 'w+') as f: 
                f.write(locations_data)
    except e:
        with open(os.path.join('data', 'locations.json'), 'r') as fd:
            locations = json.load(fd)
            
    for location in locations['locations']:
        locations[location['name_eng']] = location
    del locations['locations'] 
load_data()

async def save():
    with open(os.path.join('data', 'guild_dict_tmp'), 'wb') as fd:
        pickle.dump(guild_dict, fd, (- 1))
    os.remove(os.path.join('data', 'guild_dict'))
    os.rename(os.path.join('data', 'guild_dict_tmp'), os.path.join('data', 'guild_dict'))

"""
Events
"""

@Jessie.event
async def on_ready():
    async def auto_save(loop=True):
        while (not Jessie.is_closed()):
            try:
                await save()
            except Exception as err:
                pass
            await asyncio.sleep(600)
            continue
    
    try:
        event_loop.create_task(auto_save())
    except KeyboardInterrupt as e:
        pass
event_loop = asyncio.get_event_loop()

@Jessie.event
async def on_guild_join(guild):
    guild_dict[guild.id] = {
        'channel': None,
        'message': None,
        'nests': NestMap()
    }

@Jessie.event
async def on_guild_remove(guild):
    try:
        if guild.id in guild_dict:
            try:
                del guild_dict[guild.id]
            except KeyError:
                pass
    except KeyError:
        pass
        
"""
Helper functions
"""

async def autocorrect(word, word_list, user, channel):
    close_matches = difflib.get_close_matches(word, word_list, n=1, cutoff=0.5)
    if ( len(close_matches) <= 0 ):
        return None
    correct_word = close_matches[0]
    check_correct_word = await ask('Did you mean {} ?'.format(correct_word), user, channel)
    return correct_word if check_correct_word else None
        

async def find_pokemon(entered_pokemon: str, user, channel):
    if not entered_pokemon:
        return None
    if entered_pokemon.isdigit():
        return pokemons[int(entered_pokemon)]
    if entered_pokemon.lower() in pokemons:
        return entered_pokemon.lower()
    
    pokemon = await autocorrect( entered_pokemon, pokemons, user, channel )
    return await find_pokemon(pokemon, user, channel)
    
async def find_nest(entered_nest: str, user, channel):
    if not entered_nest:
        return None
    for location in locations.values():
        if entered_nest.lower() == location['name_eng'].lower() or entered_nest == location['name_heb']:
            return location
        if entered_nest.lower() in [ x.lower() for x in location.get('aka_eng', []) ]:
            return location
        if entered_nest.lower() in [ x.lower() for x in location.get('aka_heb', []) ]: 
            return location
    
    locations_names = []
    for location in locations.values():
        locations_names += [ location['name_eng'] ]
        locations_names += [ location['name_heb'] ]
        locations_names += location.get( 'aka_eng', [] )
        locations_names += location.get( 'aka_heb', [] )
    nest = await autocorrect( entered_nest, locations_names, user, channel )
    return await find_nest(nest, user, channel)

async def ask(message, user, channel):
    react_list = ['👍', '👎']
    rusure = await channel.send(message)
    def check(reaction, user_react):
        return reaction.message.id == rusure.id and user.id == user_react.id and (reaction.emoji in react_list)
    for r in react_list:
        await asyncio.sleep(0.25)
        await rusure.add_reaction(r)
    try:
        reaction, user = await Jessie.wait_for('reaction_add', check=check, timeout=60)
        await rusure.delete()
        return reaction.emoji == '👍'
    except asyncio.TimeoutError:
        await rusure.delete()
        return False
    
def create_nest_embed(pokemon: str, location):
    pokemon_img_url = 'https://raw.githubusercontent.com/FoglyOgly/Meowth/master/images/pkmn/{0}_.png?cache=2'.format(str(pokemons.index(pokemon)).zfill(3))
    embed_title = '__**{}**__ - Click here for directions!'.format('Frequent Spawn Point' if 'frequent_point' in location else 'Nest')
    embed = discord.Embed(title=embed_title, url=location['map_link'])
    embed.add_field(name='**Pokemon:**', value='{}'.format(pokemon.title()), inline=True)
    embed.add_field(name='**Where:**', value='{} - {}'.format(location['name_eng'], location['name_heb']), inline=True)
    embed.add_field(name='**Atlas:**', value='{}'.format(f"[Click here!]({location['atlas_link']})"), inline=True)
    embed.add_field(name='**Google Map:**', value='{}'.format(f"[Click here!]({location['map_link']})"), inline=True)
    embed.set_thumbnail(url=pokemon_img_url)
    return embed
    
"""
Commands
"""

@Jessie.command(aliases=['n'])
async def nest(ctx):
    """Report Pokemon Nests.
    
    Usage: !nest <pokemon> <location>
    """
    if ctx.invoked_subcommand is not None:
        return

    guild = ctx.guild
    message = ctx.message
    channel = message.channel
    author = message.author
    args = message.clean_content.split()[1:]
    
    if len(args) == 0:
        await channel.send('Give me details about the nest!')
        return
    
    entered_pokemon = args[0]
    entered_details = ' '.join(args[1:])
    
    pokemon = await find_pokemon(entered_pokemon, author, channel)
    location = await find_nest(entered_details, author, channel)
    if pokemon is None:
        await channel.send('Give me a valid pokemon name!')
        return
    if location is None:
        await channel.send('Give me a valid location name!')
        return
       
    msg = await channel.send(embed=create_nest_embed(pokemon, location))
    guild_dict[ctx.guild.id]['nests'].addNest(location, pokemon)
    
    """await asyncio.sleep(30)
    await message.delete()
    await msg.delete()
    
    try:
        pin_message = await channel.get_message(guild_dict[guild.id]['message'])
        await pin_message.edit(embed=discord.Embed(description=_list(guild)))
    except:
        pass"""

@Jessie.command(aliases=['f'])
async def find(ctx):
    """Find Pokemon Nest.
    
    Usage: !find <pokemon>
    """
    
    guild = ctx.guild
    message = ctx.message
    channel = message.channel
    author = message.author
    args = message.clean_content.split()[1:]
    
    if len(args) == 0:
        await channel.send('Which pokemon are you looking for ?')
        return
    
    entered_pokemon = args[0]
    pokemon = await find_pokemon(entered_pokemon, author, channel)
    
    pokeToLoc = guild_dict[ctx.guild.id]['nests'].pokeToLoc    
    if pokeToLoc.get(pokemon, None) and len(pokeToLoc[pokemon]) == 0:
        embed = discord.Embed(colour=ctx.guild.me.colour, description='No nests reported for this pokemon')
        await channel.send(embed=embed)
        return
    for location in pokeToLoc[pokemon]:
        await channel.send(embed=create_nest_embed(pokemon, location))
    
        
@Jessie.command(aliases=['c'])
async def check(ctx):
    """Check details about a nest.
    
    Usage: !check <location>
    """
    guild = ctx.guild
    message = ctx.message
    channel = message.channel
    author = message.author
    args = message.clean_content.split()[1:]
    
    if len(args) == 0:
        await channel.send('Which nest do you want to check ?')
        return
        
    entered_location = ' '.join(args)
    location = await find_nest(entered_location, author, channel)
    if location is None:
        await channel.send('Give me a valid location name!')
        return
    
    locToPoke = guild_dict[ctx.guild.id]['nests'].locToPoke    
    if not locToPoke.get(location['name_eng'], None):
        embed = discord.Embed(colour=ctx.guild.me.colour, description='No nest reported for this location!')
        await channel.send(embed=embed)
        return
        
    await channel.send(embed=create_nest_embed(locToPoke[location['name_eng']], location))

async def list_nests(ctx):    
    guild = ctx.guild
    message = ctx.message
    channel = message.channel
    
    spawn_point_pokemons = []
    nests_of_pokemons = []
    
    pokeToLoc = guild_dict[guild.id]['nests'].pokeToLoc
    print (pokeToLoc)
    for pokemon, poke_locations in pokeToLoc.items():
        point_locations = []
        nests_locations = []
        for location in poke_locations:
            if 'frequent_point' in location:
                point_locations.append(location)
            else:
                nests_locations.append(location)
        if len(point_locations) != 0:
            spawn_point_pokemons.append( (pokemon, point_locations) )
        if len(nests_locations) != 0:
            nests_of_pokemons.append( (pokemon, nests_locations) )
    
    if len(nests_of_pokemons) == 0 and len(spawn_point_pokemons) == 0:
        return 'No nests reported!'
    
    spawn_point_pokemons.sort(key=lambda tup: tup[0])
    nests_of_pokemons.sort(key=lambda tup: tup[0])
    
    nests_msg = ""
    if len(nests_of_pokemons) != 0:
        nests_msg += "__**Nests**__\n"
        for pokemon, locs in nests_of_pokemons:
            if len(nests_msg) < 1800:
                nests_msg += f"{pokemon.title().ljust(12, ' ')}  [{locs[0]['name_eng']}]({locs[0]['map_link']}) | {locs[0]['name_heb']}" + "\n"
            else:
                embed = discord.Embed(description=nests_msg)
                await channel.send(embed=embed)
                nests_msg = f"{pokemon.title().ljust(12, ' ')}  [{locs[0]['name_eng']}]({locs[0]['map_link']}) | {locs[0]['name_heb']}" + "\n"
            for location in locs[1:]:
                if len(nests_msg) < 1800:
                    nests_msg += f"{' '*20}  [{location['name_eng']}]({location['map_link']}) | {location['name_heb']}" + "\n"
                else:
                    embed = discord.Embed(description=nests_msg)
                    await channel.send(embed=embed)
                    nests_msg = f"{' '*20}  [{location['name_eng']}]({location['map_link']}) | {location['name_heb']}" + "\n"
    if len(spawn_point_pokemons) != 0:
        if len(nests_msg) < 1800:
            nests_msg += "\n__**Frequent Spawn Point**__\n"
        else:
            embed = discord.Embed(description=nests_msg)
            await channel.send(embed=embed)
            nests_msg = "\n__**Frequent Spawn Point**__\n"
        for pokemon, locs in spawn_point_pokemons:
            if len(nests_msg) < 1800:
                nests_msg += f"{pokemon.title().ljust(12, ' ')}  [{locs[0]['name_eng']}]({locs[0]['map_link']}) | {locs[0]['name_heb']}" + "\n"
            else:
                embed = discord.Embed(description=nests_msg)
                await channel.send(embed=embed)
                nests_msg = f"{pokemon.title().ljust(12, ' ')}  [{locs[0]['name_eng']}]({locs[0]['map_link']}) | {locs[0]['name_heb']}" + "\n"
            for location in locs[1:]:
                if len(nests_msg) < 1800:
                    nests_msg += f"{' '*20}  [{location['name_eng']}]({location['map_link']}) | {location['name_heb']}" + "\n"
                else:
                    embed = discord.Embed(description=nests_msg)
                    await channel.send(embed=embed)
                    nests_msg = f"{' '*20}  [{location['name_eng']}]({location['map_link']}) | {location['name_heb']}" + "\n"
    nests_msg += "\nכדי לראות את הקנים על מפה היכנסו ל:\nhttps://thesilphroad.com/atlas#11.48/31.785/35.2066"
    embed = discord.Embed(description=nests_msg)
    await channel.send(embed=embed)
    
@Jessie.group(name='list', aliases=['lists', 'l'])
async def _list(ctx):
    """Lists all nests info.
    
    Usage: !list
    """
    if ctx.invoked_subcommand != None:
        return
        
    await list_nests(ctx)

@_list.command(name='locations', aliases=['locs'])
async def _locations(ctx, *, language = "h"):
    """Lists all nests locations.
    
    Usage: !locations
    """
    channel = ctx.message.channel
    
    if "eng" in language or "e" in language or "english" in language:
        language = "name_eng"
    else:
        language = "name_heb"
    
    locations_list = list( locations.values() )
    locations_list.sort(key=lambda x: x[language])
    
    locations_str = ""
    for location in locations_list:
        locations_str += '{}\n'.format(location[language])
    
    if locations_str == "":
        return
        
    embed = discord.Embed(title='Locations', description=locations_str)
    await channel.send(embed=embed)
   
"""
Admin Commands
"""    

@commands.is_owner()
@Jessie.command(hidden=True)
async def set_channel(ctx):
    global guild_dict
    guild = ctx.guild
    channel = ctx.message.channel
    
    guild_dict[guild.id]['channel'] = channel.id

@commands.is_owner()
@Jessie.command(hidden=True)
async def clear(ctx):    
    guild = ctx.guild
    message = ctx.message
    channel = message.channel
    author = message.author
    args = message.clean_content.split()[1:]
    
    if len(args) == 0:
        await ctx.channel.send('Clear all nests...')
        guild_dict[ctx.guild.id]['nests'] = NestMap()
    else:
        entered_location = ' '.join(args)
        location = await find_nest(entered_location, author, channel)
        if location is None:
            await channel.send('Give me a valid location name!')
        else:
            await ctx.channel.send(f'Clear {location["name_eng"]}...')
            guild_dict[ctx.guild.id]['nests'].removeNest(location)
            
    await save()
    
@commands.has_permissions(manage_channels=True)
@Jessie.command(hidden=True)
async def reload(ctx):
    load_data()
    await ctx.message.add_reaction('☑')

@commands.is_owner()
@Jessie.command(hidden=True)
async def restart(ctx):
    """Restart after saving.

    Usage: !restart.
    Calls the save function and restarts Jessie."""
    await save()
        
    await ctx.channel.send('Restarting...')
    Jessie._shutdown_mode = 26
    await Jessie.logout()

@commands.is_owner()
@Jessie.command(hidden=True)
async def exit(ctx):
    """Exit after saving.

    Usage: !exit.
    Calls the save function and quits the script."""
    await save()
    
    await ctx.channel.send('Shutting down...')
    Jessie._shutdown_mode = 0
    await Jessie.logout()
    
    
try:
    event_loop.run_until_complete(Jessie.start(TOKEN))
except discord.LoginFailure:
    # Invalid token
    event_loop.run_until_complete(Jessie.logout())
    Jessie._shutdown_mode = 0
except KeyboardInterrupt:
    # Keyboard interrupt detected. Quitting...
    event_loop.run_until_complete(Jessie.logout())
    Jessie._shutdown_mode = 0
except Exception as e:
    # logger.critical('Fatal exception', exc_info=e)
    event_loop.run_until_complete(Jessie.logout())
finally:
    pass
sys.exit(Jessie._shutdown_mode) 