from typing import Any, Generator

import scrapy
from scrapy.http import Response


class LeadItem(scrapy.Item):
    url = scrapy.Field()
    company_name = scrapy.Field()
    email = scrapy.Field()
    phone = scrapy.Field()
    address = scrapy.Field()
    raw_html = scrapy.Field()


class LeadSpider(scrapy.Spider):
    name = "lead_spider"
    custom_settings = {
        "DEPTH_LIMIT": 2,
    }

    def __init__(self, start_url: str = "", *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url] if start_url else []

    def parse(self, response: Response) -> Generator[LeadItem | scrapy.Request, None, None]:
        item = LeadItem()
        item["url"] = response.url
        item["raw_html"] = response.text
        item["company_name"] = self._extract_company(response)
        item["email"] = self._extract_email(response)
        item["phone"] = self._extract_phone(response)
        item["address"] = self._extract_address(response)
        yield item

        # Follow contact / about pages
        for href in response.css("a[href]::attr(href)").getall():
            if any(kw in href.lower() for kw in ("contact", "about", "imprint", "impressum")):
                yield response.follow(href, self.parse)

    def _extract_company(self, response: Response) -> str:
        return (
            response.css("meta[property='og:site_name']::attr(content)").get()
            or response.css("title::text").get(default="").split("|")[0].strip()
        )

    def _extract_email(self, response: Response) -> str:
        import re
        emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", response.text)
        return emails[0] if emails else ""

    def _extract_phone(self, response: Response) -> str:
        import re
        phones = re.findall(
            r"(\+?[\d\s\-().]{7,20})",
            " ".join(response.css("[href^='tel:']::attr(href)").getall()),
        )
        return phones[0].strip() if phones else ""

    def _extract_address(self, response: Response) -> str:
        return (
            response.css("[itemprop='streetAddress']::text").get()
            or response.css("address::text").get(default="").strip()
        )
