## Problem

Discord connector uses HTTP webhooks, but Discord primarily uses Gateway connection for real-time events.

## Current State

- `/hooks/discord` endpoint exists for HTTP webhooks
- Works for testing and custom proxy setups
- Not suitable for production Discord bots

## Solution

Add optional Discord Gateway connection using discord.py:

```python
# src/connectors/discord/gateway.py
import discord
from discord.ext import commands

class DiscordGateway:
    def __init__(self, orchestrator):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.orchestrator = orchestrator

        @self.bot.event
        async def on_message(message):
            if message.author.bot:
                return
            event = normalize_discord_message(message)
            result = await self.orchestrator.route(event)
            if result.should_respond:
                await message.channel.send(result.messages[0].text)
```

### Run Mode

```bash
# Webhook mode (current)
./run.sh --server

# Gateway mode (new)
./run.sh --discord-gateway
```

## Acceptance Criteria

- [ ] discord.py added to requirements.txt
- [ ] Gateway client implemented
- [ ] --discord-gateway flag added to run.sh
- [ ] Both modes documented
- [ ] Tests for gateway normalization

## Labels
- enhancement
- feature

## Part of
Epic #19
