"""
NWN-AI entry point.
Initializes databases, imports bestiary, starts log tailer + DB writer, launches web server.
"""
import os, sys, queue, threading, webbrowser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PLAYER_CHARACTERS, WEB_HOST, WEB_PORT, COMBAT_DB, BESTIARY_DB, CREATURES_JSON

def main():
    print('=' * 60)
    print(' NWN-AI Combat Analyzer')
    print('=' * 60)

    # --- 1. Init databases ---
    print('\n[1/4] Initializing databases...')
    from data.init_db import init_all
    init_all()

    # --- 2. Import bestiary if creatures table is empty ---
    print('\n[2/4] Bestiary...')
    import sqlite3
    conn = sqlite3.connect(BESTIARY_DB)
    count = conn.execute('SELECT COUNT(*) FROM creatures').fetchone()[0]
    conn.close()

    if count == 0:
        print(f'  Importing creatures_data.json...')
        from bestiary.import_creatures import import_creatures
        import_creatures()
    else:
        print(f'  {count} creatures already in bestiary.db')

    # --- 3. Start log parser threads ---
    print('\n[3/4] Starting log parser...')
    from web.app import get_socketio, app
    socketio = get_socketio()

    pc_set    = set(PLAYER_CHARACTERS)
    ev_queue  = queue.Queue(maxsize=10000)

    from parser.db_writer  import DBWriter
    from parser.log_tailer import LogTailer

    writer = DBWriter(ev_queue)
    tailer = LogTailer(ev_queue, pc_set, socketio=socketio)

    writer.start()
    tailer.start()
    print(f'  Log tailer watching D:\\nwn\\logs\\')
    print(f'  DB writer flushing to {COMBAT_DB}')

    # --- 4. Launch web server ---
    print(f'\n[4/4] Starting web server...')
    url = f'http://{WEB_HOST}:{WEB_PORT}'
    print(f'  Open:  {url}')
    print('=' * 60)
    print('  Ctrl+C to stop\n')

    try:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        socketio.run(app, host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print('\nShutting down...')
        tailer.stop()
        writer.stop()
        tailer.join(timeout=3)
        writer.join(timeout=5)
        print('Done.')


if __name__ == '__main__':
    main()
