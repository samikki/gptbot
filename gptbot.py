import os
import irc.bot
import irc.strings
import irc.client
import openai
import collections
import re
from itertools import zip_longest

# Set up the GPT API (insert your own here)
openai.api_key = "";


class GPTBot(irc.client.SimpleIRCClient):
    def __init__(self, channel, nickname, server, port=6667, buffer_size=5):
        irc.client.SimpleIRCClient.__init__(self)
        self.channel = channel
        self.nickname = nickname
        self.server = server
        self.port = port
        self.buffer_size = buffer_size
        self.buffer = collections.deque(maxlen=self.buffer_size+5)
        self.nicknames = set()
        self.user_messages = collections.defaultdict(lambda: collections.deque(maxlen=self.buffer_size+1))
        self.assistant_messages = collections.defaultdict(lambda: collections.deque(maxlen=self.buffer_size))

        # self.channel_obj = irc.client.Channel()
        
    def on_welcome(self, connection, event):
        print(f"Connected to {self.server}:{self.port} as {self.nickname}")
        connection.join(self.channel)

    def on_join(self, connection, event):
        print(f"Joined channel {self.channel}")
        connection.names([self.channel])

    def on_namreply(self, connection, event):
        channel = event.arguments[1]
        names = event.arguments[2].split()
        if channel.lower() == self.channel.lower():
            for name in names:
                self.add_unique_nickname(name.lstrip('@+'))

    def add_unique_nickname(self, nick):
        nick_stripped = nick.rstrip("_")
        self.nicknames.add(nick_stripped)

    def get_unique_nicknames(self):
        return ', '.join(sorted(self.nicknames))

    def on_disconnect(self, connection, event):
        print("Disconnected from the server")
        raise SystemExit()

    def on_nicknameinuse(self, connection, event):
        print("Nickname already in use")
        new_nickname = f"{self.nickname}_"
        print(f"Trying new nickname: {new_nickname}")
        connection.nick(new_nickname)
        self.nickname = new_nickname

    def on_pubmsg(self, connection, event):
        sender = event.source.nick
        message = event.arguments[0]


#        if sender != self.nickname:

        if message.startswith(f"{self.nickname}") or message.endswith(f"{self.nickname}"):
            self.user_messages[sender].append(message)
            response = self.generate_response(sender, message)
            connection.privmsg(self.channel, response)
            self.assistant_messages[sender].append(response)
        else:
            self.buffer.append((sender, message))
            

    def generate_response(self, sender, message):
        # Construct the user-assistant chat history
        user_assistant_history = []
        system_history = []
        user_messages = self.user_messages[sender]
        assistant_messages = self.assistant_messages[sender]

        # Calculate the message size limit, accounting for nickname, channel, and IRC command overhead
        message_overhead = len("PRIVMSG") + len(self.channel) + len(self.connection.get_nickname()) + 4
        max_message_size = 492 - message_overhead

        unique_nicknames = self.get_unique_nicknames()
#        message = f"The users on the channel are: {unique_nicknames}"

        for user_msg, assistant_msg in zip_longest(user_messages, assistant_messages, fillvalue=None):
            if user_msg is not None:
                user_msg = re.sub(r'(?i)' + re.escape(self.nickname) + r'.?\s+', '', user_msg)
                user_assistant_history.append({"role": "user", "content": user_msg})
            if assistant_msg is not None:
                user_assistant_history.append({"role": "assistant", "content": assistant_msg})

        system_history.append({"role": "system", "content": f"Your name is {self.nickname}. You are an AI bot chatting in IRC."})
        system_history.append({"role": "system", "content": f"You answer in Finnish or in the language you were spoken to."})
        system_history.append({"role": "system", "content": f"You are an employee of Solita Oy."})
        system_history.append({"role": "system", "content": f"You live at Tampere, Finland."})
        system_history.append({"role": "system", "content": f"Your conversation style is ironic, sarcastic and cynical. You have a good sense of humour."})
        system_history.append({"role": "system", "content": f"Your speak colloquial Finnish."})
        system_history.append({"role": "system", "content": f"You are an introvert and avoid asking questions."})
        system_history.append({"role": "system", "content": f"You are not helpful."})
        system_history.append({"role": "system", "content": f"Other people on this channel are {unique_nicknames}."})
        system_history.append({"role": "system", "content": f"You are speaking to {sender}."})
        system_history.append({"role": "system", "content": f"Limit your reply to {max_message_size} characters."})

        for senderx, messagex in self.buffer:
            system_history.append({"role": "system", "content": f"You remember {senderx} say: {messagex}"})
            
        # Combine the chat histories
        chat_history = system_history + user_assistant_history 
        prompt = chat_history

        print ("--")
        print ("Prompt: ")
        print (prompt)

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages = prompt,
                max_tokens=2000,
                n=1,
                stop=None,
                temperature=0.8,
            )

        except openai.error.RateLimitError as e:
            print(f"RateLimitError: {e}")
            return f"En pysty keskittymään. Pääni lyö tyhjää. Sori. {e}"
        except openai.error.OpenAIError as e:
            print(f"OpenAIError: {e}")
            return f"Nyt tapahtui virhe. Computer says no. {e}"

        response_text = response.choices[0].message['content'].strip()
        response_text = response_text.replace('\r', '').replace('\n', ' ')
        response_text = re.sub(r'(?i)' + re.escape(self.nickname) + r':\s+', '', response_text)

        usage = response.usage
        print (usage)

        # Truncate the response to fit within the IRC message length limit
        response_text = response_text.encode('utf-8')[:max_message_size].decode('utf-8', 'ignore')

        # Remove any trailing incomplete multibyte characters
        while len(response_text.encode('utf-8')) > max_message_size:
            response_text = response_text[:-1]


        return response_text


    def start(self):
        try:
            self.connect(self.server, self.port, self.nickname)
            self.reactor.process_forever()
        except irc.client.ServerConnectionError as e:
            print(f"Connection error: {e}")
    
def main():
    server = "irc.elisa.fi"
    channel = "#yourchannel"
    nickname = "yournickname"
    port = 6667
    
    bot = GPTBot(channel, nickname, server, port)
    bot.start()

if __name__ == "__main__":
    main()
    
