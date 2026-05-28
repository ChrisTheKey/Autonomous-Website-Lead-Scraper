BOT_NAME = "lead_scraper"
SPIDER_MODULES = ["app.scrapers.spiders"]
NEWSPIDER_MODULE = "app.scrapers.spiders"

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 1.0
COOKIES_ENABLED = False

# Pipelines
ITEM_PIPELINES = {
    "app.scrapers.pipelines.LeadPipeline": 300,
}

# Middlewares
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "app.scrapers.middlewares.RotatingUserAgentMiddleware": 400,
}

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
}

LOG_LEVEL = "WARNING"
