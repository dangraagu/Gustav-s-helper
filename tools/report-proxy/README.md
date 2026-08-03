# Step-report forwarder

The plugin's "Report wrong / missing info" button POSTs here; this service forwards the report to a
Discord channel. It exists so the **Discord webhook URL is never published** — the plugin ships in a
public repo, so anything inside it is public.

What it buys over putting the webhook in the plugin:

| | webhook in plugin | this forwarder |
|---|---|---|
| URL extractable from the jar | yes | no |
| Someone can `@everyone` your server | **yes** (they set their own `allowed_mentions`) | no — payload is rebuilt here |
| Someone can `DELETE` the webhook | **yes** (kills reporting until a new hub release) | no |
| GitHub secret-scanning auto-revokes it | **likely** | n/a |
| Block an abuser | needs a new hub release | edit/stop the service |

It accepts only a JSON body with a `content` string, caps it, rate-limits per IP and overall, then sends
a freshly-built payload with mentions disabled. Nothing else the caller sends is forwarded.

## Deploy (VPS, as root)

```bash
# 1. user + code
adduser --system --group --home /opt/gustav-report gustavreport
install -d -o gustavreport -g gustavreport /opt/gustav-report
# copy app.py to /opt/gustav-report/app.py
python3 -m venv /opt/gustav-report/venv
/opt/gustav-report/venv/bin/pip install --upgrade pip fastapi uvicorn httpx
chown -R gustavreport:gustavreport /opt/gustav-report

# 2. the secret — root-owned, not readable by anyone else, NEVER in git
printf 'DISCORD_WEBHOOK_URL=%s\n' 'https://discord.com/api/webhooks/XXXX/YYYY' > /etc/gustav-report.env
chmod 600 /etc/gustav-report.env

# 3. service
# copy gustav-report.service to /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gustav-report
curl -s localhost:8123/healthz      # -> {"ok":true,"webhook_configured":true}
```

## Caddy

Add a site block, then **validate before reloading** — this Caddyfile also serves the revenue sites, so a
bad reload must never be attempted blind:

```caddyfile
gustav.yamaduo.no {
	encode gzip
	handle /report {
		reverse_proxy 127.0.0.1:8123
	}
	handle /healthz {
		reverse_proxy 127.0.0.1:8123
	}
	handle {
		respond "Gustav's Helper report endpoint" 200
	}
}
```

```bash
caddy validate --config /etc/caddy/Caddyfile   # MUST pass first
systemctl reload caddy                         # graceful; existing sites keep serving
```

DNS: `gustav.yamaduo.no` → the VPS IP (A record). Caddy issues the certificate automatically once DNS
resolves.

## Verify end to end

```bash
curl -i -X POST https://gustav.yamaduo.no/report \
  -H 'Content-Type: application/json' \
  -d '{"content":"test report from curl"}'      # -> 204, message appears in Discord
```

## Rotating the webhook

Regenerate it in Discord, update `/etc/gustav-report.env`, `systemctl restart gustav-report`. **No plugin
release needed** — that is the whole point of this indirection.
