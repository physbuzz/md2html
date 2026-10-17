"""Small, session-owned JSON line workers for external renderers."""

import json
import subprocess


class Worker:
    def __init__(self, command):
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            self.ready = self.receive()
        except Exception:
            self.close()
            raise

    def receive(self):
        line = self.process.stdout.readline()
        if not line:
            raise OSError("renderer stopped: " + self.process.stderr.read())
        value = json.loads(line)
        if value.get("error"):
            raise ValueError(value["error"])
        return value

    def request(self, **value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()
        return self.receive()

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()
        self.process.stderr.close()
