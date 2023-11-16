# Telegram-Assistant

This is personal AI assistant that communicates with the user using Telegram. You will need telegram and openAI keys to run it, and put them in to environment variables named OPENAI_KEY TELEGRAM_KEY. 

NOTE: you can't probably even run it even if you use your own keys because of preset id for the assistant and I don't know if you can use the one I generated or if you need to generate your own. 

Currently the AI assistant can only create timers / reminders and run python code. 

## TODO 
- add google calendar integration
- implement retrival mode
- novelAI image generation (maybe even text if I'm bored)


## TelegramCommands 
- `toggle_retrival` - doesn't work yet
- `toggle_debug` - Turns debug mode on allowing you to see what functions and tools where used and what their results where. Great to see if the AI actually did what it should have or if it just made stuff up.
- `clear_thread` - Deletes current thread and creates new one, basically deleting current chat history from the AI memory. Important as right now the history grows until it reaches maximum tokens which can be expensive. 

## Function available to the bot 
- `get_current_time` - return current UT datetime
- `calculate_seconds` - calculates seconds, hopefully the AI can use this instead of doing math itself
- `add_reminder` - adds reminder, that will send message to the user when it expires
- `get_reminders` - returns list off all reminders and their indexes
- `remove_reminders` - accepts array of indexes of reminders that are to be removed 

## Examples 
![image](https://github.com/Llyfrs/Telegram-Assistant/assets/59464917/625d79b4-26fa-414f-bb47-70d4aae3e9be)
![image](https://github.com/Llyfrs/Telegram-Assistant/assets/59464917/cdab55c2-5e5c-481b-93d0-1b94db21c0c7)


### Debug mode example and more complicated usage (GPT 4 was used)

![image](https://github.com/Llyfrs/Telegram-Assistant/assets/59464917/2a4929ba-ae76-4785-9c28-b05a3478bf08)
