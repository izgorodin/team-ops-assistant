# Team Ops Assistant - Runbook

Operational runbook for deploying and managing Team Ops Assistant on Render.

## Deployment to Render

### Prerequisites

1. Render account with billing enabled
2. MongoDB Atlas cluster
3. Platform bot tokens (Telegram, Discord, WhatsApp)

### Initial Setup

1. **Create a new Web Service on Render**
   - Connect your GitHub repository
   - Select Python environment
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `python -m src.app --host 0.0.0.0 --port $PORT`

2. **Configure Environment Variables**

   In Render dashboard, add these environment variables:

   | Variable | Description |
   |----------|-------------|
   | `MONGODB_URI` | MongoDB Atlas connection string |
   | `TELEGRAM_BOT_TOKEN` | From @BotFather |
   | `DISCORD_BOT_TOKEN` | From Discord Developer Portal |
   | `WHATSAPP_ACCESS_TOKEN` | From Meta Business Suite |
   | `WHATSAPP_PHONE_NUMBER_ID` | Your WhatsApp phone number ID |
   | `WHATSAPP_VERIFY_TOKEN` | Custom token for webhook verification |
   | `TOGETHER_API_KEY` | Together AI API key |
   | `APP_SECRET_KEY` | Random secret for sessions |
   | `VERIFY_TOKEN_SECRET` | Random secret for verification tokens |

3. **Deploy**
   - Push to your main branch
   - Render will auto-deploy

### Webhook Configuration

#### Telegram

1. Get your Render URL: `https://your-app.onrender.com`
2. Set webhook with Telegram Bot API:
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-app.onrender.com/hooks/telegram"
   ```

#### Discord

Discord typically uses gateway connections rather than webhooks. Options:

1. Use Discord Interactions (slash commands) with webhook
2. Run a separate process with discord.py gateway connection
3. Use a Discord-to-webhook service

See [Discord documentation](https://discord.com/developers/docs/interactions/overview) for details.

#### WhatsApp

1. In Meta Business Suite, go to WhatsApp > Configuration
2. Set Callback URL: `https://your-app.onrender.com/hooks/whatsapp`
3. Set Verify Token: (same as `WHATSAPP_VERIFY_TOKEN` env var)
4. Subscribe to messages

## Monitoring

### Health Check

```bash
curl https://your-app.onrender.com/health
# Expected: {"status":"ok"}
```

Set up Render health check:
- Path: `/health`
- Interval: 30 seconds

### Logs

View logs in Render dashboard or CLI:
```bash
render logs --service your-service-id
```

### Key Metrics to Monitor

- Response times for `/hooks/*` endpoints
- MongoDB connection status
- Error rate in logs
- Outbound message success rate

## Troubleshooting

### Application Won't Start

1. Check logs for Python errors
2. Verify all environment variables are set
3. Confirm MongoDB URI is accessible from Render IPs

### Webhook Not Receiving Messages

1. Verify webhook URL is correctly configured
2. Check platform-specific webhook status
3. Review application logs for incoming requests

### MongoDB Connection Errors

1. Verify `MONGODB_URI` is correct
2. Check MongoDB Atlas IP allowlist includes Render IPs
3. Confirm database user has correct permissions

### High Latency

1. Check MongoDB Atlas metrics
2. Review Render instance metrics
3. Consider upgrading Render plan or MongoDB tier

## Scaling

### Horizontal Scaling

Render supports scaling instances:
1. Go to Service Settings
2. Adjust instance count

Note: Each instance connects to MongoDB independently.

### Database Scaling

MongoDB Atlas auto-scales, but for heavy load:
1. Upgrade cluster tier
2. Enable auto-scaling
3. Add read replicas if needed

## Backup and Recovery

### MongoDB

1. Enable MongoDB Atlas automated backups
2. Set retention period (minimum 7 days recommended)
3. Test restoration periodically

### Application State

The application is stateless. All persistent state is in MongoDB:
- User timezone preferences
- Chat configurations
- Deduplication records (TTL-managed)

## Security Considerations

### Environment Variables

- Never commit secrets to git
- Rotate tokens periodically
- Use different tokens for dev/staging/prod

### Network Security

- MongoDB Atlas IP allowlist
- HTTPS only (Render provides SSL)
- Webhook signature verification (platform-specific)

### Token Verification

Verification tokens are signed with HMAC-SHA256:
- Short-lived (24 hours default)
- Cannot be forged without `VERIFY_TOKEN_SECRET`
- Rotate `VERIFY_TOKEN_SECRET` if compromised

## Maintenance Tasks

### Regular Tasks

| Task | Frequency | Description |
|------|-----------|-------------|
| Log review | Daily | Check for errors |
| Dependency updates | Weekly | Security patches |
| Token rotation | Monthly | Rotate secrets |
| Backup verification | Monthly | Test DB restore |

### MongoDB Maintenance

- Deduplication records auto-expire via TTL index (7 days)
- No manual cleanup needed for normal operation

## Rollback Procedure

1. In Render dashboard, go to Deploys
2. Find the previous working deploy
3. Click "Rollback to this deploy"
4. Verify health check passes
