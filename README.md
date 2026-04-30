# Telegram-Assistant

This is a personal AI assistant that communicates with the user via Telegram. It’s a personal project that I decided to make public, so I’m forced to keep sensitive information (such as keys) outside of the source code. This project was started long before agents like OpenClaw existed, and it contains a mix of many then–state-of-the-art approaches to building an agent, though it is not always kept up to date. The project also includes many personal tools that help me with day-to-day organization.

## Current Agentic Implementation

The assistant runs in an agentic loop and is decoupled from the Telegram message-handling layer, so it can be invoked from anywhere in the codebase (not only from an incoming chat message). The agent communicates by calling `send_telegram_message`, and it ends the loop by calling `submit_solution` once it is done.

## TelegramCommands 
- **Slash commands registered in Telegram (appear in the `/` command picker)**:
  - `/bounty` - Toggle Torn bounty monitor on/off.
  - `/clear_thread` - Clear the AI conversation history (and memory graph, if enabled).
  - `/company` - Open Torn company settings UI (currently training preferences).
  - `/daily_checkin` - Manually trigger the daily habit check-in.
  - `/email_here` - Set this chat as the destination for email notifications.
  - `/live_message` - Create a message that updates every second (timer demo).
  - `/model` - Switch the OpenRouter model used by the main agent.
  - `/next` - Show your next timetable lesson today.
  - `/now` - Show your current timetable lesson.
  - `/ping` - Reply with `pong`.
  - `/pong` - Reply with `ping`.
  - `/q` - Save an encrypted private note (message is deleted after saving).
  - `/racing` - Show Torn racing skill stats + predictions (with a graph when possible).
  - `/set_torn_api_key <api_key>` - Set Torn API key for this bot instance.
  - `/set_wolframalpha_app_id <app_id>` - Set WolframAlpha App ID (stored in DB).
  - `/settings` - Open notification/settings toggles UI.
  - `/stacking` - Toggle Torn stacking mode on/off.
  - `/stock` - Send a Torn stock report.
  - `/target` - Pick a suitable Torn target (targets list / hospital timing helper).
  - `/time_table` - Add/manage timetable entries (interactive UI).
  - `/train` - Send Torn training status.
  - `/unwatch` - Stop the active `/watch` file watcher in this chat.
  - `/watch [path]` - Live-watch a file under `storage/` and auto-update the message on changes.

- **Utility slash commands (supported but not shown in the picker)**:
  - `/cancel` - Cancel an in-progress interactive flow (used by `/watch`, `/model`, `/settings`, `/company`, `/time_table`).

## Function available to the bot 
- **AI tools (functions the main agent can call)**:
  - `seconds_until` - Seconds remaining until a given datetime (`%Y-%m-%d %H:%M:%S`).
  - `convert_to_seconds` - Convert days/hours/minutes/seconds into total seconds.
  - `create_reminder` - Create a reminder that will message you later.
  - `cancel_reminder` - Cancel reminders by ID.
  - `get_reminders` - List active reminders.
  - `create_event` - Create a Google Calendar event.
  - `send_telegram_message` - Send a message to the primary Telegram chat (agent’s main output).
  - `read_file` - Read a file from `storage/` with line numbers.
  - `write_file` - Create/overwrite a file under `storage/`.
  - `str_replace` - Replace a specific string in an existing file under `storage/`.
  - `list_directory` - List directory contents under `storage/`.
  - `create_directory` - Create a directory under `storage/`.
  - `delete` - Delete a file/folder under `storage/` (recursive for directories).
  - `move` - Move/rename a file/folder under `storage/`.
  - `search_files` - Search filenames and contents under `storage/`.
  - `create_time_capsule` - Schedule a “message to future self” delivery.
  - `create_habit` - Create a new daily habit to track.
  - `list_habits` - List active habits.
  - `remove_habit` - Deactivate a habit.
  - `get_habit_stats` - Get habit stats (streaks / averages / trends).
  - `generate_heatmap` - Generate & send a habit heatmap image.
  - `submit_solution` - Internal “done” signal for the agent loop.

- **Non-slash handlers (always on)**:
  - **Assistant chat**: any non-command text/photo/voice message is routed to the main AI agent.
  - **File upload to memory**: uploading a text-like file (txt/md/json/xml/js/yaml) adds its contents into memory.

## Thoughts and discoveries

### Function output 

> This is all from time when function calling was like two weeks old, it has come long way since then and AI models are way smarter. 

Looks like function output should be formatted in the style of json or at least provide context as a see better results when I do. 
I can only guess this is because the AI doesn't remember what functions it called so when it calls for example `get_current_time` and gets only time like 10:20:34 
it just remembers some numbers as result and doesn't know the context of them but if you return {"current_time":"10:16:19"} it will now know that what it got is current time. 
Example of this: The AI really struggles to use `get_current_time`with set reminder function to create reminders for specific times not in specific time.

![image](https://i.imgur.com/jJj0pVN.png)

After some more testing the problem could have been with the fact that I was returning time that had seconds as float making the AI not recognize it necessarily  as time.

### Error handling
The AI has the ability to recognize errors and try again, but it seems this is very strict as it will only recognize outputs that specifically say that the function call failed. 
When your function returns result that is clearly incorrect it doesn't seem to recognize it as an error and will pretend the funtion did what it should have. 

![img.png](https://i.imgur.com/ihSAPrS.png)

### Multiple assistants
They provide nice speciality to them allowing them to perform specific tasks better than general assistant can. 
But the question is if they are needed or cheaper that just using GP-4, as this model seems to just be able to handle most task. 
Unfortunately because of the cost I can't test with the more advanced model.


## Examples 
![image](https://github.com/Llyfrs/Telegram-Assistant/assets/59464917/625d79b4-26fa-414f-bb47-70d4aae3e9be)
![image](https://github.com/Llyfrs/Telegram-Assistant/assets/59464917/cdab55c2-5e5c-481b-93d0-1b94db21c0c7)


### Debug mode example and more complicated usage (GPT 4 was used)

![image](https://github.com/Llyfrs/Telegram-Assistant/assets/59464917/2a4929ba-ae76-4785-9c28-b05a3478bf08)
