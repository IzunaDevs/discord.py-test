# Stdlib
import asyncio

# External Libraries
import discord


class Context(discord.Context):
    def __init__(self, **attrs):
        self.message = attrs.pop('message', None)
        self.bot = attrs.pop('bot', None)
        self.args = attrs.pop('args', [])
        self.kwargs = attrs.pop('kwargs', {})
        self.prefix = attrs.pop('prefix')
        self.command = attrs.pop('command', None)
        self.view = attrs.pop('view', None)
        self.invoked_with = attrs.pop('invoked_with', None)
        self.invoked_subcommand = attrs.pop('invoked_subcommand', None)
        self.subcommand_passed = attrs.pop('subcommand_passed', None)
        self.command_failed = attrs.pop('command_failed', False)

    @asyncio.coroutine
    def invoke(self, *args, **kwargs):
        try:
            command = args[0]
        except IndexError:
            raise TypeError('Missing command to invoke.') from None

        arguments = []
        if command.instance is not None:
            arguments.append(command.instance)

        arguments.append(self)
        arguments.extend(args[1:])

        ret = yield from command.callback(*arguments, **kwargs)
        return ret

    @asyncio.coroutine
    def reinvoke(self, *, call_hooks=False, restart=True):
        cmd = self.command
        view = self.view
        if cmd is None:
            raise ValueError('This context is not valid.')

        # some state to revert to when we're done
        index, previous = view.index, view.previous
        invoked_with = self.invoked_with
        invoked_subcommand = self.invoked_subcommand
        subcommand_passed = self.subcommand_passed

        if restart:
            to_call = cmd.root_parent or cmd
            view.index = len(self.prefix)
            view.previous = 0
            view.get_word()  # advance to get the root command
        else:
            to_call = cmd

        try:
            yield from to_call.reinvoke(self, call_hooks=call_hooks)
        finally:
            self.command = cmd
            view.index = index
            view.previous = previous
            self.invoked_with = invoked_with
            self.invoked_subcommand = invoked_subcommand
            self.subcommand_passed = subcommand_passed

    @property
    def valid(self):
        return self.prefix is not None and self.command is not None

    @asyncio.coroutine
    def _get_channel(self):
        return self.channel

    @property
    def cog(self):
        if self.command is None:
            return None
        return self.command.instance

    @discord.utils.cached_property
    def guild(self):
        return self.message.guild

    @discord.utils.cached_property
    def channel(self):
        return self.message.channel

    @discord.utils.cached_property
    def author(self):
        return self.message.author

    @discord.utils.cached_property
    def me(self):
        return self.guild.me if self.guild is not None else self.bot.user

    @property
    def voice_client(self):
        g = self.guild
        return g.voice_client if g else None
