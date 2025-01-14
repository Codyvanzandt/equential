# equential

### Local Development

```bash
uvicorn app.main:app --reload
```

### CLI Commands

```bash
python -m cli.manage create-user "user@example.com" "John Doe"
```

```bash
python -m cli.manage delete-user "user@example.com"
```

## Deployment to DigitalOcean App Platform

### MongoDB Atlas Setup
1. Configure Network Access in Atlas
   - Go to Network Access in Atlas
   - Add IP Address
   - For App Platform, you'll need to allow access from all IPs (0.0.0.0/0) as DO App Platform uses dynamic IPs

### App Platform Configuration
1. Create a new app from your GitHub repo
2. Environment Type: Python
3. Set Environment Variables:
   ```
   MONGODB_URL=your-mongodb-atlas-url
   BASE_URL=${APP_URL}  # App Platform automatically provides this
   ```
4. Build Command: `pip install -r requirements.txt`
5. Run Command: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT}`

### Important Notes
- App Platform will automatically:
  - Provide HTTPS/SSL
  - Handle process management
  - Provide a domain (or you can configure your own)
  - Auto-deploy on git push
- The CLI tool is for local admin use only and won't be available on App Platform
- Consider setting up CI/CD tests before deployment
