from pathlib import Path

env_path = Path(".env")

if not env_path.exists():
    raise SystemExit("Could not find .env file. Create one from .env.example first.")

env = env_path.read_text()

key = "FLUTTERWAVE_MEMBERSHIP_REDIRECT_URL"
local_value = "http://localhost:5173/memberships/payment/processing"

lines = env.splitlines()
updated = False

for index, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[index] = f"{key}={local_value}"
        updated = True
        break

if not updated:
    lines.append(f"{key}={local_value}")

env_path.write_text("\n".join(lines) + "\n")

print(f"{key} set to {local_value}")
