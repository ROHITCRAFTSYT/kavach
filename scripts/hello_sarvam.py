import os
import sys
from pathlib import Path

from sarvamai import SarvamAI

# Load .env into the environment (stdlib only, no python-dotenv).
env_file = Path(__file__).resolve().parents[1] / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    raise SystemExit("SARVAM_API_KEY is not set. Add it to .env.")

client = SarvamAI(api_subscription_key=api_key)

response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Say hello in Hindi and English."}],
)

sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252
print(response.choices[0].message.content)
