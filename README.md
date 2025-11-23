*Disclaimer: all specific terms are capitalized on purpose, I am not stoopid*

# Service Droid

## What is this?

Service Droid is a Discord Bot based on VibeBots structure.
It was created for the Stellaris Youtuber [Ep3o](https://www.youtube.com/@Ep3o) and adds a number of commands for LFG (looking for game) mechanics.

## Available Commands

### General

> `/lfg [Message]` | `!lfg [Message]`

This commands can be executed by every Member that has the permissions to do so.
To actually use the Command the member needs to have a Host Role and the Channel needs to be set up as a LFG Channel.
An additional text can be added to be displayed below the Message.

### Setting Commands

All Settings can only be used by Members having the `Administrator` permissions.

> `/turn_lfg_on_or_off`

Turns of all Features.
This will later be replaced by `/turn_on_or_off` but would be misleading at this point since LFG is the only feature.

> `/current_settings`

Shows the current LFG Settings of the Server.

> `/reset_cooldown [Member]`

Reset all LFG Cooldowns on the Server.
A Member can be added optionally to only reset their Cooldown.

> `/setting_add_lfg {Channel} {Role}`

Create a LFG Channel or add additional Roles to mention to it.
`Channel` is the Channel you want to make a LFG Channel or add additional mentions to.
`Role` is the Role that you want to be mentioned, making it a LFG Role.

> `/setting_remove_lfg {Channel}`

Removes a LFG Channel.
Specific mentions can't be removed, so the entire LFG Channel needs to be removed and the Roles actually wanted re added.

> `/setting_set_host {Role} {timeunit} {amount}`

With this Command Host Roles can be added.
`Role` is the Role that's supposed to be made a Host Role.
`timeunit` and `amount` add details for the Cooldown duration.
If a Role is supposed to remove LFG permissions entirely that can be done by setting the Cooldown to zero seconds.

### Dev Commands

All Dev Commands are only executable as the Bot Developer.
This depends on whom the owner of the Bot is.

> `/shutdown`

Shuts down the Bot.

> `/restart`

Restarts the Bot [currently not working].

> `/load {Cog}`

Loads a Cog.

> `/unload {Cog}`

Unloads a Cog

> `/reload {Cog}`

Reloads a Cog.

> `/update_git`

Pulls the newest version of the Bot from git.