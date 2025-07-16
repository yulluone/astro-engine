from fastapi import FastAPI
from . import config # This will run the checks in config.py on startup
from .api.endpoints import businesses, tags, products, webhooks

# Import the new setup function
from .logging_config import setup_logging

# Call the setup function right at the start
setup_logging()

# Create the FastAPI app instance
app = FastAPI(
    title="Astro Engagement Engine",
    description="The core API for the Astro multi-channel customer engagement platform.",
    version="0.1.0"
)

# A simple root endpoint to confirm the server is running
@app.get("/")
def read_root():
    """
    Root endpoint to check API status.
    """
    return {"status": "ok", "message": "Astro Engine is online."}

# We will add our API routers here later
# from .api.endpoints import businesses, products
app.include_router(businesses.router)
app.include_router(tags.router)
app.include_router(products.router)
app.include_router(webhooks.router) 