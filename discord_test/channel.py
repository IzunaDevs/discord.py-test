# Stdlib
import asyncio

# External Libraries
import discord


class TextChannel(discord.TextChannel):
    def __init__(self, *, guild, data):
        self.id = int(data['id'])
        self._update(guild, data)

    def __repr__(self):
        return '<TextChannel id={0.id} name={0.name!r} position={0.position}>'.format(
            self)

    @asyncio.coroutine
    def _edit(self):
        raise NotImplementedError

    def _update(self, guild, data):
        self.guild = guild
        self.name = data['name']
        self.category_id = discord.utils._get_as_snowflake(data, 'parent_id')
        self.topic = data.get('topic')
        self.position = data['position']
        self.nsfw = data.get('nsfw', False)
        self._fill_overwrites(data)

    @asyncio.coroutine
    def _get_channel(self):
        return self

    def permissions_for(self, member):
        base = super().permissions_for(member)

        # text channels do not have voice related permissions
        denied = discord.Permissions.voice()
        base.value &= ~denied.value
        return base

    permissions_for.__doc__ = discord.abc.GuildChannel.permissions_for.__doc__

    @property
    def members(self):
        return [
            m for m in self.guild.members
            if self.permissions_for(m).read_messages
        ]

    def is_nsfw(self):
        n = self.name
        return self.nsfw or n == 'nsfw' or n[:5] == 'nsfw-'

    @asyncio.coroutine
    def edit(self, *, reason=None, **options):
        yield from self._edit(options, reason=reason)

    @asyncio.coroutine
    def delete_messages(self, messages):
        raise NotImplementedError

    @asyncio.coroutine
    def purge(self,
              *,
              limit=100,
              check=None,
              before=None,
              after=None,
              around=None,
              reverse=False,
              bulk=True):
        raise NotImplementedError

    @asyncio.coroutine
    def webhooks(self):
        raise NotImplementedError

    @asyncio.coroutine
    def create_webhook(self, *, name=None, avatar=None):
        raise NotImplementedError


class VoiceChannel(discord.VoiceChannel):
    def __init__(self, *, guild, data):
        self.id = int(data['id'])
        self._update(guild, data)

    def __repr__(self):
        return '<VoiceChannel id={0.id} name={0.name!r} position={0.position}>'.format(
            self)

    @asyncio.coroutine
    def _edit(self):
        raise NotImplementedError

    def _get_voice_client_key(self):
        return self.guild.id, 'guild_id'

    def _get_voice_state_pair(self):
        return self.guild.id, self.id

    def _update(self, guild, data):
        self.guild = guild
        self.name = data['name']
        self.category_id = discord.utils._get_as_snowflake(data, 'parent_id')
        self.position = data['position']
        self.bitrate = data.get('bitrate')
        self.user_limit = data.get('user_limit')
        self._fill_overwrites(data)

    @property
    def members(self):
        ret = []
        for user_id, state in self.guild._voice_states.items():
            if state.channel.id == self.id:
                member = self.guild.get_member(user_id)
                if member is not None:
                    ret.append(member)
        return ret

    @asyncio.coroutine
    def edit(self, *, reason=None, **options):
        yield from self._edit(options, reason=reason)


class CategoryChannel(discord.CategoryChannel):
    def __init__(self, *, guild, data):
        self.id = int(data['id'])
        self._update(guild, data)

    def __repr__(self):
        return '<CategoryChannel id={0.id} name={0.name!r} position={0.position}>'.format(
            self)

    def _update(self, guild, data):
        self.guild = guild
        self.name = data['name']
        self.category_id = discord.utils._get_as_snowflake(data, 'parent_id')
        self.nsfw = data.get('nsfw', False)
        self.position = data['position']
        self._fill_overwrites(data)

    def is_nsfw(self):
        n = self.name
        return self.nsfw or n == 'nsfw' or n[:5] == 'nsfw-'

    @asyncio.coroutine
    def edit(self, *, reason=None, **options):
        raise NotImplementedError

    @property
    def channels(self):
        def comparator(channel):
            return (not isinstance(channel, TextChannel), channel.position)

        ret = [c for c in self.guild.channels if c.category_id == self.id]
        ret.sort(key=comparator)
        return ret


class DMChannel(discord.DMChannel):
    def __init__(self, *, me, data):
        # self.recipient = state.store_user(data['recipients'][0])
        self.me = me
        self.id = int(data['id'])

    @asyncio.coroutine
    def _get_channel(self):
        return self

    def __str__(self):
        return 'Direct Message with %s' % self.recipient

    def __repr__(self):
        return '<DMChannel id={0.id} recipient={0.recipient!r}>'.format(self)

    @property
    def created_at(self):
        return discord.utils.snowflake_time(self.id)

    def permissions_for(self, user=None):
        base = discord.Permissions.text()
        base.send_tts_messages = False
        base.manage_messages = False
        return base


class GroupChannel(discord.GroupChannel):
    def __init__(self, *, me, data):
        self.id = int(data['id'])
        self.me = me
        self._update_group(data)

    def _update_group(self, data):
        raise NotImplementedError

    @asyncio.coroutine
    def _get_channel(self):
        return self

    def __str__(self):
        if self.name:
            return self.name

        if len(self.recipients) == 0:
            return 'Unnamed'

        return ', '.join(map(lambda x: x.name, self.recipients))

    def __repr__(self):
        return '<GroupChannel id={0.id} name={0.name!r}>'.format(self)

    @property
    def icon_url(self):
        if self.icon is None:
            return ''

        return 'https://cdn.discordapp.com/channel-icons/{0.id}/{0.icon}.jpg'.format(
            self)

    @property
    def created_at(self):
        return discord.utils.snowflake_time(self.id)

    def permissions_for(self, user):
        base = discord.Permissions.text()
        base.send_tts_messages = False
        base.manage_messages = False
        base.mention_everyone = True

        if user.id == self.owner.id:
            base.kick_members = True

        return base

    @asyncio.coroutine
    def add_recipients(self, *recipients):
        raise NotImplementedError

    @asyncio.coroutine
    def remove_recipients(self, *recipients):
        raise NotImplementedError

    @asyncio.coroutine
    def edit(self, **fields):
        raise NotImplementedError

    @asyncio.coroutine
    def leave(self):
        raise NotImplementedError
