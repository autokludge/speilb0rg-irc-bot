from twisted.words.protocols import irc
from twisted.internet import protocol, reactor
import re
import os
import sys
from collections import defaultdict
SEPERATOR = '============================================'


class MomBot(irc.IRCClient):
    def _get_nickname(self):
        return self.factory.nickname
    nickname = property(_get_nickname)

    def signedOn(self):
        self.join(self.factory.channel)
        print "Signed on as %s." % (self.nickname,)

    def privmsg(self, user, channel, msg):
        nick = user.split('!', 1)[0]
        print 'message `%s` from: %s' % (msg, nick)
        if not user:
            return
        if self.nickname in msg:
            msg = re.compile(self.nickname + "[:,]* ?", re.I).sub('', msg)
            prefix = "%s: " % (user.split('!', 1)[0], )
        else:
            prefix = ''
        if prefix or channel == self.factory.nickname:
            # if i have been mentioned (eg nick: ) run possible commands
            print 'mentioned'
            self.mentioned(nick, msg)
        print SEPERATOR

    def irc_JOIN(self, prefix, params):
        user = prefix.split('!')[0]
        if user == self.factory.nickname:
            print "Joined %s." % (params[0],)
            print SEPERATOR
        if user in ['speilberg0', 'marcogmontiero', 'dshoreman', 'pfote', 'code', 'Zogot']:
            self.msg(self.factory.channel, 'Welcome back, %s' % user)
        if re.match(r'.*gateway/web/freenode.*', prefix):
            print "%s is from web gateway" % (user)
            self.msg(self.factory.channel, 'Hi %s, if you have a question just ask and someone will answer soon. Please post relevant code to http://pastebin.com.' % user)

    def mentioned(self, nick, msg):
        #bot operators
        if nick in ['speilberg0']:
            self.botops(nick, msg)

        # now that high priority stuff is out of the way, lets run commands or string subs
        if ' ' not in msg:
            cmd = msg
        else:
            (cmd, rest) = msg.split(' ', 1)
        if cmd in commands:
            response = commands[cmd](rest)
            if response[:3] == '/me':
                self.describe(self.factory.channel, response[4:])
            else:
                self.msg(self.factory.channel, response)
        elif cmd in strings:
            response = strings[msg]
            self.msg(self.factory.channel, response)

    def botops(self, nick, msg):
        print 'message `%s` from botop: %s' % (msg, nick)
        match = re.match('^action (\w*) (lambda.*)$', msg)
        if match:
            commandname = match.group(1)
            command = match.group(2)
            add_to_brain(commandname, 'function', command, write_to_file=True)
            print commandname
            print command


class MomBotFactory(protocol.ClientFactory):
    protocol = MomBot

    def __init__(self, channel, nickname='speilb0rg', max_words=10000):
        self.channel = channel
        self.nickname = nickname
        self.max_words = max_words

    def clientConnectionLost(self, connector, reason):
        print "Lost connection (%s), reconnecting." % (reason,)
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "Could not connect: %s" % (reason,)


strings = defaultdict(list)
commands = defaultdict(list)


def add_to_brain(command, cmdtype, action, write_to_file=False):
    if cmdtype == 'function':
        commands[command] = eval(action)
        print 'added command %s to memory' % (command)
    else:
        strings[command] = action
        print 'added string %s to memory' % (command)
    if write_to_file:
        commandstore = '%s!%s!%s\n' % (command, cmdtype, action)
        with open('stored_commands.pkl', 'a') as f:
            f.write(commandstore)


def lmgtfy(query):
    q = 'http://lmgtfy.com/?q=' + '+'.join(query.split(' '))
    return q

if __name__ == '__main__':
    try:
        chan = sys.argv[1]
    except IndexError:
        print "Please specify a channel name."
        print "Example: "
        print " main.py test7654"
    if os.path.exists('stored_commands.pkl'):
        with open('stored_commands.pkl', 'rb') as f:
            for line in f:
                (command, cmdtype, action) = line.split('!', 2)
                add_to_brain(command, cmdtype, action)
        print 'loaded commands'
        print SEPERATOR

    reactor.connectTCP('irc.freenode.net', 6667, MomBotFactory('#' + chan))
    print 'connecting to freenode'
    reactor.run()
