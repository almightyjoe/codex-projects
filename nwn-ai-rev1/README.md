# NWN AI Rev 1

Preserved baseline copy of the original NWN-AI combat analyzer from `D:\1claudecode\nwn-ai`.

This revision keeps the original architecture intact:

- tails `D:\nwn\logs\nwclientLog*.txt`
- parses attacks, damage, kills, saves, spell events, areas, and status blocks
- stores combat data in SQLite
- imports Higher Grounds bestiary data
- serves the Flask/SocketIO dashboard
- connects natural language questions to local Ollama

Runtime databases, caches, and generated logs are intentionally ignored by git.

