# Deployment guide

The service is a stateless container: `POST` a ticket, get a category/tier/priority back.
Plan for **~2 GB RAM** when using `sentence-transformers` (the model is baked into the image).
With `TC_EMBEDDING_BACKEND=tfidf` it runs in a few hundred MB.

## 0. Test locally
```bash
cp .env.example .env            # set TC_API_KEY
docker compose up --build
curl localhost:8000/healthz
```

## 1. Render (simplest)
1. Push the repo to GitHub.
2. Render dashboard -> New -> **Web Service** -> connect the repo -> Runtime **Docker**.
3. Choose an instance with >= 2 GB RAM. Health check path: `/healthz`.
4. Add environment variables from `.env.example` (at least `TC_API_KEY`).
5. Deploy. Your URL is shown at the top of the service page.

## 2. Google Cloud Run
```bash
gcloud run deploy ticket-categorizer --source . --region <REGION> \
  --memory 2Gi --cpu 2 --allow-unauthenticated \
  --set-env-vars TC_EMBEDDING_BACKEND=sentence-transformers \
  --set-secrets TC_API_KEY=ticket-categorizer-api-key:latest
```
Store `TC_API_KEY` in Secret Manager first. `--allow-unauthenticated` is OK because the app enforces `X-API-Key`;
for private use, drop it and use IAM instead. Set `--min-instances 1` to avoid cold-start model loading.

## 3. Any VPS
```bash
docker run -d --restart unless-stopped -p 8000:8000 --env-file .env ghcr.io/<owner>/ticket-categorizer:latest
```
Put it behind Caddy/nginx for HTTPS.

## Custom taxonomy in a container
Mount your YAML and point the env vars at it:
```bash
docker run ... -v $(pwd)/config:/config -e TC_CATEGORIES_PATH=/config/categories.yaml \
  -e TC_ROUTING_PATH=/config/routing.yaml ...
```

## Wiring it into your helpdesk
- **Real-time:** Zendesk/Freshdesk trigger -> webhook -> `POST /v1/classify` -> write tags/fields back.
- **Batch clustering:** cron/GitHub Action every 15-60 min: fetch open tickets -> `POST /v1/cluster` -> post
  `possible_incident` clusters to Slack.

## Production checklist
- [ ] `TC_API_KEY` set, HTTPS only
- [ ] Secrets in your platform's secret store, never in git
- [ ] Logs do not contain ticket bodies (the service does not log them)
- [ ] Evaluated accuracy on your own labelled tickets
- [ ] Human review for P1 / security / privacy categories
