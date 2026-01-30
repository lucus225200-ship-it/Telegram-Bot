Folder Structure:
/storage
├── movies.json    (Shared movie data between bots)
└── stats.db       (SQLite3 database for 21 statistics)

Note:

main.py (User Bot) will read from movies.json to display buttons.

admin_bot.py will write settings and read stats from stats.db.

channel_watcher.py will write new movie entries to movies.json.
