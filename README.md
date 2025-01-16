# Equential

A web application for running A/B tests and collecting user feedback on policy language.

## Deployment to DigitalOcean App Platform

### Prerequisites

1. A DigitalOcean account
2. Your code pushed to a GitHub repository
3. MongoDB database (can be set up on MongoDB Atlas with a free tier)

### Step-by-Step Deployment Instructions

1. **Prepare Your Repository**
   - Ensure your repository contains:
     - `requirements.txt` with all Python dependencies
     - `Procfile` with the command to run your FastAPI app: `web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`
     - Environment variables defined in your app

2. **Set Up MongoDB**
   - Create a MongoDB Atlas account if you don't have one
   - Create a new cluster (free tier is sufficient)
   - Create a database user and get your connection string
   - Whitelist all IP addresses (0.0.0.0/0) for App Platform

3. **Deploy to DigitalOcean**
   1. Log in to your DigitalOcean account
   2. Go to the App Platform section
   3. Click "Create App"
   4. Choose GitHub as your repository source
   5. Select your repository
   6. Select the branch you want to deploy
   7. Select Python as the environment
   8. Configure your app:
      - Choose "Web Service" as the component type
      - Set the run command: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`
      - Add environment variables:
        ```
        MONGODB_URL=your_mongodb_connection_string
        USERS_COLLECTION=users
        ```
   9. Click "Next"
   10. Choose your plan (Basic plan is usually sufficient)
   11. Click "Launch App"

4. **Post-Deployment**
   - Your app will be assigned a `.ondigitalocean.app` domain
   - You can add a custom domain in the app settings if needed
   - Set up automatic deployments from your repository

### Environment Variables

Make sure to set these environment variables in your DigitalOcean App:

- `MONGODB_URL`: Your MongoDB connection string
- `USERS_COLLECTION`: Name of your users collection (default: "users")

### Monitoring and Maintenance

- Monitor your app's performance in the DigitalOcean dashboard
- View logs in the "Components" -> "Console" section
- Set up alerts for any issues
- Scale your app resources as needed in the settings

### Troubleshooting

Common issues and solutions:

1. **App fails to start**
   - Check the logs in the Console section
   - Verify all environment variables are set correctly
   - Ensure MongoDB connection string is correct and IP is whitelisted

2. **Database connection issues**
   - Check if MongoDB Atlas IP whitelist includes 0.0.0.0/0
   - Verify connection string includes correct username/password
   - Ensure database user has correct permissions

3. **Static files not loading**
   - Verify static files are included in your repository
   - Check file permissions
   - Ensure paths in your code are correct

### Local Development

To run the app locally:

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables in a `.env` file:
   ```
   MONGODB_URL=your_mongodb_connection_string
   USERS_COLLECTION=users
   ```
5. Run the app:
   ```bash
   uvicorn app.main:app --reload
   ```

## Support

For issues with deployment:
1. Check DigitalOcean's status page
2. Review app logs in the Console section
3. Contact DigitalOcean support if needed
