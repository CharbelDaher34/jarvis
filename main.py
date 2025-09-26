import scrapy
from scrapy.crawler import CrawlerProcess


class DynamicSpider(scrapy.Spider):
    name = "dynamic_test"
    start_urls = ["https://quotes.toscrape.com/js/"]  # JS-rendered test site

    async def parse(self, response):
        # Get all visible text
        text_parts = response.xpath("//body//text()").getall()
        cleaned_text = " ".join([t.strip() for t in text_parts if t.strip()])

        # Extract all links
        links = response.css("a::attr(href)").getall()
        with open("scraped_output.txt", "w", encoding="utf-8") as f:
            f.write(cleaned_text)
        yield {
            "url": response.url,
            "text": cleaned_text,
            "links": links,
        }


def crawl_page(url: str):
    """
    Run scrapy-playwright once on a dynamic page.
    Returns scraped results.
    """
    process = CrawlerProcess(settings={
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "LOG_LEVEL": "DEBUG",  # keep logs clean
    })

    # Dynamically override the start URL
    DynamicSpider.start_urls = [url]

    process.crawl(DynamicSpider)
    process.start()


# 🔹 Test it
if __name__ == "__main__":
    print(crawl_page("https://quotes.toscrape.com/js/"))
