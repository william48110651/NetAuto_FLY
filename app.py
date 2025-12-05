from flask import Flask, render_template, request
from netmiko import ConnectHandler
import yaml
import os

app = Flask(__name__)

def load_devices():
    """Safely load devices.yaml. If missing or malformed, return empty list."""
    try:
        with open("devices.yaml", "r") as f:
            data = yaml.safe_load(f)
            return data.get("devices", [])
    except Exception:
        return []

# Load at startup but keep a function for flexibility (hot reload or future DB)
devices = load_devices()

@app.route("/")
def index():
    return render_template("index.html", devices=devices, logs=None)

@app.route("/deploy", methods=["POST"])
def deploy():
    vlan_id = request.form["vlan_id"]
    vlan_name = request.form["vlan_name"]
    interface = "Ethernet1"
    selected_devices = request.form.getlist("devices")

    logs = []

    for host in selected_devices:
        device = next((d for d in devices if d["host"] == host), None)

        if not device:
            logs.append(f"❌ Device not found: {host}")
            continue

        try:
            logs.append(f"\n🔗 Connecting to {host} ...")

            # Log file path inside container
            session_log_path = "/tmp/netmiko.log"

            net_connect = ConnectHandler(
                **device,
                fast_cli=False,
                global_delay_factor=2,
                conn_timeout=30,
                blocking_timeout=20,
                session_log=session_log_path,
            )

            # Some devices need enable
            try:
                net_connect.enable()
            except Exception:
                pass

            config_commands = [
                f"vlan {vlan_id}",
                f"name {vlan_name}",
                f"interface {interface}",
                "switchport mode access",
                f"switchport access vlan {vlan_id}"
            ]

            output = net_connect.send_config_set(config_commands)
            logs.append(f"✅ Config applied on {host}:\n{output}")

            show_vlan = net_connect.send_command("show vlan brief")
            show_int = net_connect.send_command("show ip interface brief")

            logs.append(f"📌 VLAN Table on {host}:\n{show_vlan}")
            logs.append(f"📌 Interface Status on {host}:\n{show_int}")

            net_connect.disconnect()

        except Exception as e:
            logs.append(f"❌ Error on {host}: {e}")

    return render_template("index.html", devices=devices, logs="\n\n".join(logs))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))   # ← 適用 Docker/Fly.io
    app.run(host="0.0.0.0", port=port)
