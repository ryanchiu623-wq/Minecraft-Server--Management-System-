"""Replace a plugin jar that the running server keeps locked.

Windows will not let a jar be moved while java has it open, so a plugin update
needs the server down. This stops it through restart-sequence.py (players get
the same 5-minute warning as any planned stop), swaps the jar once java has
exited, and starts the server again.

    python swap-plugin.py <new.jar> <old jar pattern> [--wait-empty]

    python swap-plugin.py C:/build/PanelKey-1.6.0.jar "PanelKey-*.jar" --wait-empty

The old jar goes to plugins-removed next to plugins, not the bin.
--wait-empty waits until nobody (bots aside) is online first, so the stop
needs no countdown at all.
"""
import argparse
import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEQUENCE = os.path.join(HERE, 'restart-sequence.py')

_spec = importlib.util.spec_from_file_location('restart_sequence', SEQUENCE)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

PLUGINS = os.path.join(rs.SERVER_DIR, 'plugins')
REMOVED = os.path.join(rs.SERVER_DIR, 'plugins-removed')


def wait_for_empty(poll=60):
    while True:
        session = rs.Session()
        online = rs.players_online(session)
        session.close()
        if online == 0:
            return
        time.sleep(poll)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('jar', help='the new plugin jar')
    parser.add_argument('old', help='file pattern of the jar it replaces, inside plugins')
    parser.add_argument('--wait-empty', action='store_true')
    parser.add_argument('--by', default='swap-plugin')
    args = parser.parse_args()

    new_jar = os.path.abspath(args.jar)
    if not os.path.isfile(new_jar):
        print('no such jar: ' + new_jar)
        return 1
    name = os.path.basename(new_jar)
    if not rs.port_open(rs.GAME_PORT):
        print('server is not running - just copy the jar into plugins')
        return 1

    if args.wait_empty:
        rs.log('swap-plugin: waiting for an empty server to install ' + name)
        wait_for_empty()

    rs.log('swap-plugin: stopping the server to install ' + name)
    subprocess.run([sys.executable, SEQUENCE, '--stop', '--by', args.by,
                    '--reason', '更新外掛，約 1 分鐘後回來'], cwd=HERE)
    if rs.port_open(rs.GAME_PORT):
        rs.log('swap-plugin: server still up (countdown cancelled?) - jar not swapped', 'WARN')
        return 1

    # Keep the watchdog off the server while it is down on purpose.
    rs.take_lock()
    try:
        for _ in range(60):
            if not rs.server_process_running():
                break
            time.sleep(3)
        else:
            rs.log('swap-plugin: java never exited - jar not swapped', 'ERROR')
            return 1

        try:
            os.makedirs(REMOVED, exist_ok=True)
            for old in glob.glob(os.path.join(PLUGINS, args.old)):
                if os.path.basename(old) != name:
                    shutil.move(old, os.path.join(REMOVED, os.path.basename(old)))
                    rs.log('swap-plugin: moved out ' + os.path.basename(old))
            shutil.copy2(new_jar, os.path.join(PLUGINS, name))
            rs.log('swap-plugin: installed ' + name)
        except OSError as exc:
            # Bring the server back either way; a failed update beats an outage.
            rs.log('swap-plugin: swap failed ({0}) - starting the server as it was'.format(exc), 'ERROR')

        if not rs.start_server():
            rs.log('swap-plugin: server did not come back within 3 minutes', 'ERROR')
            return 1
        return 0
    finally:
        rs.release_lock()


if __name__ == '__main__':
    sys.exit(main())
