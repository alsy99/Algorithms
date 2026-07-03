# Static dashboard for GitHub Pages

This folder is published automatically to **GitHub Pages** when pushed to the default branch.

## Live demo URL

After deployment: `https://<username>.github.io/<repo>/`

For this repository: **https://alsy99.github.io/Algorithms/**

The hosted dashboard runs in **demo mode** with simulated NSE quotes and sentiment (GitHub Pages cannot run the Python bot).

## Connect to a running bot

If you run the bot locally or on a server with a public URL:

```
https://alsy99.github.io/Algorithms/?api=https://your-server:8080
```

The dashboard will poll `/api/status` every 2 seconds.

## Local bot dashboard

When running `sentiment-trader`, open:

- http://localhost:8080/ — live dashboard
- http://localhost:8080/api/status — JSON API
- http://localhost:8080/health — health check
