from twisted.words.protocols import irc
from twisted.internet import protocol, reactor
from twisted.python import log
import os
import time
import sys
import re
from collections import defaultdict
SEPERATOR = '============================================'
REGULARS = ['speilberg0', 'marcogmontiero', 'dshoreman', 'pfote', 'code', 'Zogot']
commands = defaultdict(list)


class MessageLogger:
    """
    An independant logger class
    """
    def __init__(self, file):
        self.file = file

    def log(self, message):
        """Write message to file."""
        timestamp = time.strftime("[%H:%M:%S]", time.localtime(time.time()))
        self.file.write('%s %s\n' % (timestamp, message))
        self.file.flush()

    def close(self):
        self.file.close()


class MomBot(irc.IRCClient):
    def _get_nickname(self):
        return self.factory.nickname
    nickname = property(_get_nickname)

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.logger = MessageLogger(open(self.factory.filename, 'a'))
        self.log_n_print("[connected at %s]" %
                    time.asctime(time.localtime(time.time())))

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        self.log_n_print("[disconnected at %s]" %
                    time.asctime(time.localtime(time.time())))
        self.logger.close()

    # Event Callbacks
    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        self.log_n_print("[Signed on as %s]" % self.nickname)
        self.join(self.factory.channel)

    def joined(self, channel):
        """This will get called when the bot joins the channel."""
        self.log_n_print("[I have joined %s]" % channel)

    def action(self, user, channel, data):
        nick = user.split('!', 1)[0]
        self.log_n_print("%s%s %s" % (" " * (20 - len(nick)), '*' + nick, data))

    def privmsg(self, user, channel, msg):
        nick = user.split('!', 1)[0]
        self.log_n_print("%s<%s> %s" % (" " * (19 - len(nick)), nick, msg))
        if not user:
            return
        if self.nickname in msg:
            msg = re.compile(self.nickname + "[:,]* ?", re.I).sub('', msg)
            prefix = "%s: " % (user.split('!', 1)[0], )
        elif channel == self.nickname and msg[0] == '!':
            msg = msg[1:]
            prefix = '!'
        else:
            prefix = ''
        if prefix:
            # if i have been mentioned (eg nick: ) run possible commands
            print SEPERATOR
            self.log_n_print('mentioned by %s in channel %s' % (nick, channel))
            self.command(user, msg)
            print SEPERATOR

    def command(self, user, msg):
        nick = user.split('!', 1)[0]

        if msg == 'commands':
            response = 'commands, ' + ', '.join(commands.keys()) + " [quit, action verb function, changeNick new_nick]"
            self.msg(nick, response)
            return

        #bot operators
        if nick in ['speilberg0']:
            self.botops(user, msg)

        # now that high priority stuff is out of the way, lets run commands or string subs
        if ' ' not in msg:
            cmd = msg
            rest = ''
        else:
            (cmd, rest) = msg.split(' ', 1)
        if cmd in commands:
            if rest:
                response = commands[cmd](rest)
            else:
                response = commands[cmd]()
            if response[:3] == '/me':
                self.describe(self.factory.channel, response[4:])
                self.log_n_print("[Ran command %s with response %s]" % (cmd, response))
            else:
                self.msg(self.factory.channel, response)
                self.log_n_print("[Ran command %s with response %s]" % (cmd, response))

    # irc callbacks
    def irc_NICK(self, prefix, params):
        """Called when an IRC user changes their nick"""
        old_nick = prefix.split('!')[0]
        new_nick = params[0]
        self.log_n_print("[%s is now known as %s]" % (old_nick, new_nick))

    def botops(self, user, msg):
        nick = user.split('!', 1)[0]
        self.log_n_print('message `%s` from botop: %s' % (msg, nick))
        if msg == 'quit':
            self.describe(self.factory.channel, "Shutting down...")
            reactor.stop()
        new_nick = re.match('^changeNick (\w+)', msg)
        new_channel = re.match('^changeChan (#\w+)', msg)
        action = re.match('^action (\w*) (lambda.*)$', msg)
        if action:
            commandname = action.group(1)
            command = action.group(2)
            add_to_brain(commandname, 'function', command, write_to_file=True)
            self.log_n_print("[New command `%s` added: %s]" % (commandname, command))
        elif new_nick:
            self.setNick(new_nick.group(1))
        elif new_channel:
            new_channel = new_channel.group(1)
            old_channel = self.factory.channel
            self.log_n_print("[Changed channel from %s to %s]" % (old_channel, new_channel))
            self.join(new_channel)
            self.leave(old_channel)

    def log_n_print(self, message):
        print message
        self.logger.log(message)


def add_to_brain(command, cmdtype, action, write_to_file=False):
    if cmdtype == 'function':
        commands[command] = eval(action)
        print 'added command %s to memory' % (command)
    if write_to_file:
        commandstore = '%s!%s!%s\n' % (command, cmdtype, action)
        with open('stored_commands.txt', 'a') as f:
            f.write(commandstore)


class MomBotFactory(protocol.ClientFactory):
    """
    Pretty standard clientfactory
    Instantiates MomBot and reconnects if disconnected
    """

    def __init__(self, channel, nickname='speilb0rg', filename='speilb0rg-log.txt'):
        self.channel = channel
        self.nickname = nickname
        self.filename = filename

    def buildProtocol(self, addr):
        p = MomBot()
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        print "Lost connection (%s), reconnecting." % (reason,)
        connector.connect()

    def clientConnectionFailed(self, reason):
        print "Could not connect: %s" % (reason,)
        reactor.stop()


if __name__ == '__main__':
    chan = "#codeigniter"
    intl = 'irc.freenode.net'
    brisbane = 'roddenberry.freenode.net'
    if len(sys.argv) > 1:
        chan = sys.argv[1]

    log.startLogging(sys.stdout)

    if os.path.exists('stored_commands.txt'):
        with open('stored_commands.txt', 'rb') as f:
            for line in f:
                (command, cmdtype, action) = line.split('!', 2)
                add_to_brain(command, cmdtype, action)
        print 'loaded commands'
        print SEPERATOR

    f = MomBotFactory(chan)

    reactor.connectTCP(intl, 6667, f)
    print 'connecting to freenode'
    reactor.run()
