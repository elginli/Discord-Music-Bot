import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import urllib.parse, urllib.request, re

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix=".", intents = intents)

    queues = {}
    voice_clients = {}
    loop_state = {}
    is_skipping = {}
    youtube_base_url = "https://www.youtube.com/"
    youtube_results_url = youtube_base_url + 'results?'
    youtube_watch_url = youtube_base_url + 'watch?v='
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    @client.event
    async def on_ready():
        print(f'{client.user} is now playing')

    #plays next song
    async def play_next(ctx):
        if queues[ctx.guild.id]:  
            next_song = queues[ctx.guild.id].pop(0)  
            await play(ctx, next_song) 
            await ctx.send(f"Now playing: {next_song}")
        else:
            await ctx.send("The queue is empty.")

    #plays the song
    @client.command(name="play")
    async def play(ctx, link):

        try:
            voice_client = await ctx.author.voice.channel.connect()
            voice_clients[voice_client.guild.id] = voice_client
        except Exception as e:
            print(e)

        try:

            if youtube_base_url not in link:
                query_string = urllib.parse.urlencode({'search_query': link})

                content = urllib.request.urlopen(youtube_results_url + query_string)

                search_results = re.findall(r'/watch?v=(.{11})', content.read().decode())

                if not search_results:
                    await ctx.send("No videos found based on your search query.")
                    return

                link = youtube_watch_url + search_results[0]

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))

            song = data['url']
            player = discord.FFmpegOpusAudio(song, **ffmpeg_options)

            def after_playing(error):
                if error:
                    print(f'Playback error: {error}')

                if ctx.guild.id in is_skipping:
                    if is_skipping[ctx.guild.id]:
                        del is_skipping[ctx.guild.id]  
                        return  
                    
                if ctx.guild.id in loop_state and loop_state[ctx.guild.id]:
                    asyncio.run_coroutine_threadsafe(play(ctx, link), client.loop)
                else:
                    asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop)

            voice_clients[ctx.guild.id].play(player, after=after_playing)

            #voice_clients[ctx.guild.id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))

        except Exception as e:
            print(e)

    #pauses the song
    @client.command(name = "pause")
    async def pause(ctx):
        try:
            voice_clients[ctx.guild.id].pause()
        except Exception as e:
            print(e)

    #resumes the song
    @client.command(name = "resume")
    async def resume(ctx):
        try:
            voice_clients[ctx.guild.id].resume()
        except Exception as e:
            print(e)

    #makes the bot leave call
    @client.command(name = "leave")
    async def leave(ctx):
        try:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
        except Exception as e:
            print(e)

    #skip to next song in queue
    @client.command(name = "skip")
    async def skip(ctx):
        try:
            if voice_clients[ctx.guild.id] and voice_clients[ctx.guild.id].is_playing():
                is_skipping[ctx.guild.id] = True
                voice_clients[ctx.guild.id].stop()
            await ctx.send("Skipped current track!")  
            await play_next(ctx)
        except Exception as e:
            print(e)
            await ctx.send("Error while trying to skip the track.")

    #skip to a certain song in the queue
    @client.command(name = "skipto")
    async def skipto(ctx, index: int):

        guild_id = ctx.guild.id

        queue = queues.get(guild_id, [])

        if not 1 <= index <= len(queue):
            await ctx.send(f"Please choose a number within the queue, 1 and {len(queue)}.")
            return

        try:
            voice_clients[ctx.guild.id].stop()
        except Exception as e:
            print(e)

        next_song = queue.pop(index-1)
        queues[guild_id] = queue[index - 1:]

        await ctx.send(f"Skipping to song number {index}!")

        try:
            await play(ctx, next_song)
        except Exception as e:
            print(f"Error playing the song at index {index}: {e}")
            await ctx.send("Failed to play the selected song.")

    #loops the current song, to unloop run it again
    @client.command(name = "loop")
    async def loop(ctx):
        
        if loop_state.get(ctx.guild.id, False):
            loop_state[ctx.guild.id] = False
            await ctx.send("Looping is now disabled.")
        else:
            loop_state[ctx.guild.id] = True 
            await ctx.send("Looping is now enabled.")

    #clears the queue
    @client.command(name = "clear")
    async def clear(ctx):
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Queue cleared!")
        else:
            await ctx.send("There is no queue to clear!")

    #queues up the song
    @client.command(name = "queue")
    async def queue(ctx, url):
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []
        queues[ctx.guild.id].append(url)
        await ctx.send("Added to queue!")

    #shows all songs in current queue
    @client.command(name="show")
    async def show(ctx):
        if ctx.guild.id in queues and queues[ctx.guild.id]:
            response = "\n".join(f"{idx + 1}: {url}" for idx, url in enumerate(queues[ctx.guild.id]))
            await ctx.send(f"Current Queue:\n{response}")
        else:
            await ctx.send("The queue is currently empty!")


    client.run(TOKEN)
