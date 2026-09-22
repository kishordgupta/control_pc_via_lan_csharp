import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def relay(tmp_path):
    if not shutil.which('php'):
        pytest.skip('PHP CLI is required for relay integration tests')
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port = s.getsockname()[1]
    accounts = {f'u{i}': secrets.token_urlsafe(32) for i in range(25)}
    (tmp_path/'users.json').write_text(json.dumps({u:hashlib.sha256(t.encode()).hexdigest() for u,t in accounts.items()}))
    env = dict(os.environ, MINIDESK_DATA=str(tmp_path), MINIDESK_LISTEN=f'127.0.0.1:{port}')
    env.pop('MINIDESK_MAX_CLIENTS', None)
    log = (tmp_path/'relay.log').open('w')
    proc = subprocess.Popen(['php',str(ROOT/'server/relay.php')],env=env,stdout=log,stderr=log)
    try:
        for _ in range(100):
            if proc.poll() is not None:
                pytest.fail((tmp_path/'relay.log').read_text())
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1): break
            except OSError: time.sleep(.02)
        else: pytest.fail('Relay did not start')
        yield {'url':f'ws://127.0.0.1:{port}/ws','accounts':accounts,'env':env,'process':proc,'data':tmp_path,'port':port}
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        log.close()
