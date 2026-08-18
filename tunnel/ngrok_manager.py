"""
Ngrok tunnel manager.

Manages ngrok tunnels to expose the local webhook server to the internet.
Uses subprocess to call the system-installed ngrok directly (via homebrew).
"""

import json
import logging
import subprocess
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Path priorities for finding ngrok binary
NGROK_PATHS = [
    '/opt/homebrew/bin/ngrok',     # macOS ARM (homebrew)
    '/usr/local/bin/ngrok',        # macOS Intel (homebrew)
]


def _find_ngrok() -> Optional[str]:
    """Find the ngrok binary on the system."""
    import shutil

    # First try PATH (skip venv wrappers)
    for path in NGROK_PATHS:
        try:
            result = subprocess.run(
                [path, 'version'],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info('Found ngrok at: %s (%s)', path, result.stdout.strip())
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Fallback: search PATH but exclude venv
    which_result = shutil.which('ngrok')
    if which_result and 'venv' not in which_result:
        return which_result

    return None


class NgrokManager:
    """Manages ngrok tunnel lifecycle using subprocess."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._public_url: Optional[str] = None
        self._ngrok_bin: Optional[str] = None

    def start(self, port: int, authtoken: str) -> Optional[str]:
        """
        Start an ngrok tunnel on the specified port.

        Args:
            port: Local port to tunnel (e.g., 5001).
            authtoken: Ngrok authentication token.

        Returns:
            Public HTTPS URL, or None if failed.
        """
        try:
            # Find ngrok binary
            self._ngrok_bin = _find_ngrok()
            if not self._ngrok_bin:
                logger.error('ngrok binary not found. Install via: brew install ngrok')
                return None

            # Kill any existing ngrok processes
            self._kill_existing()

            # Start ngrok process
            self._process = subprocess.Popen(
                [self._ngrok_bin, 'http', str(port), '--log', 'stdout', '--log-format', 'json'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={
                    **__import__('os').environ,
                    'NGROK_AUTHTOKEN': authtoken,
                },
            )

            # Wait for tunnel to be established (read log lines)
            self._public_url = self._wait_for_url(timeout=15)

            if self._public_url:
                logger.info('Ngrok tunnel started: %s -> localhost:%d', self._public_url, port)
                return self._public_url
            else:
                logger.error('Ngrok tunnel failed to provide a public URL.')
                self.stop()
                return None

        except Exception as e:
            logger.error('Failed to start ngrok tunnel: %s', str(e))
            self.stop()
            return None

    def _wait_for_url(self, timeout: int = 15) -> Optional[str]:
        """
        Wait for ngrok to output the public URL in its JSON logs.
        Falls back to the ngrok local API.
        """
        start_time = time.time()

        # Method 1: Read stdout JSON logs for the URL
        while time.time() - start_time < timeout:
            if self._process is None or self._process.poll() is not None:
                # Process exited unexpectedly
                if self._process:
                    stderr = self._process.stderr.read().decode() if self._process.stderr else ''
                    logger.error('ngrok exited: %s', stderr[:500])
                return None

            # Try the ngrok API (http://127.0.0.1:4040/api/tunnels)
            try:
                resp = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    tunnels = data.get('tunnels', [])
                    for tunnel in tunnels:
                        url = tunnel.get('public_url', '')
                        if url.startswith('https://'):
                            return url
                        elif url.startswith('http://'):
                            return url.replace('http://', 'https://')
            except (requests.RequestException, ValueError):
                pass

            time.sleep(1)

        return None

    def _kill_existing(self):
        """Kill any existing ngrok processes to avoid conflicts."""
        try:
            subprocess.run(
                ['pkill', '-f', 'ngrok'],
                capture_output=True, timeout=5,
            )
            time.sleep(0.5)
        except Exception:
            pass

    def stop(self):
        """Stop the ngrok tunnel and cleanup."""
        try:
            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                logger.info('Ngrok process terminated.')

            # Also kill any orphaned ngrok processes
            self._kill_existing()

        except Exception as e:
            logger.warning('Error stopping ngrok: %s', str(e))
        finally:
            self._process = None
            self._public_url = None

    def get_url(self) -> Optional[str]:
        """Get the current public URL."""
        return self._public_url

    @property
    def is_running(self) -> bool:
        """Check if tunnel is currently active."""
        return self._process is not None and self._process.poll() is None
