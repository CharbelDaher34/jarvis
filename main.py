import asyncio
import json
from typing import List, Dict, Any, Optional
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter, URLPatternFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

class AdvancedDeepCrawler:
    """
    A class to perform deep crawling and extract text, images, and PDFs from websites.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the crawler.
        
        Args:
            headless (bool): Whether to run browser in headless mode. 
                           Set to False for debugging.
        """
        self.crawler = None
        self.headless = headless
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.crawler = AsyncWebCrawler()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.crawler:
            await self.crawler.close()
    
    async def deep_crawl(
        self,
        start_url: str,
        max_depth: int = 2,
        max_pages: int = 50,
        keywords: Optional[List[str]] = None,
        allowed_domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform deep crawling and extract content.
        
        Args:
            start_url: The URL to start crawling from
            max_depth: Maximum depth to crawl from start URL
            max_pages: Maximum number of pages to crawl
            keywords: List of keywords for relevance scoring
            allowed_domains: List of domains to stay within
            
        Returns:
            List of dictionaries containing page content, images, and PDFs
        """
        
        # Create filter chain
        filter_chain = FilterChain([
            DomainFilter(
                allowed_domains=allowed_domains or [start_url.split('/')[2]],
                blocked_domains=[]
            ),
            URLPatternFilter(patterns=["*"])  # Match all URLs within domain
        ])
        
        # Create scorer for intelligent crawling prioritization
        scorer = KeywordRelevanceScorer(
            keywords=keywords or [],
            weight=0.7
        ) if keywords else None
        
        # Configure deep crawling strategy
        deep_crawl_strategy = BestFirstCrawlingStrategy(
            max_depth=max_depth,
            include_external=False,
            max_pages=max_pages,
            filter_chain=filter_chain,
            url_scorer=scorer
        )
        
        # Configure crawl execution
        config = CrawlerRunConfig(
            deep_crawl_strategy=deep_crawl_strategy,
            cache_mode=CacheMode.BYPASS,  # Get fresh content
            screenshot=True,              # Capture screenshots
            pdf=True,                     # Generate PDFs
            capture_mhtml=True,           # Capture complete page snapshots
            word_count_threshold=10,      # Minimum content threshold
            process_iframes=True,         # Process iframe content
            remove_overlay_elements=True, # Remove popups/modals
            verbose=True                  # Enable logging
        )
        
        results = []
        try:
            # Execute the deep crawl
            async for result in await self.crawler.adeep_crawl(
                start_url=start_url, 
                config=config
            ):
                if result.success:
                    page_data = self._extract_page_data(result)
                    results.append(page_data)
                    
                    # Print progress
                    depth = result.metadata.get('depth', 0)
                    print(f"✅ Depth {depth}: Crawled {result.url}")
                    print(f"   - Text characters: {len(page_data['text_content'])}")
                    print(f"   - Images found: {len(page_data['images'])}")
                    print(f"   - PDF generated: {page_data['has_pdf']}")
                    
        except Exception as e:
            print(f"Error during crawling: {str(e)}")
            
        return results
    
    def _extract_page_data(self, result) -> Dict[str, Any]:
        """
        Extract structured data from a crawl result.
        
        Args:
            result: The CrawlResult object from Crawl4AI
            
        Returns:
            Dictionary containing extracted page data
        """
        # Extract text content from markdown
        text_content = ""
        if hasattr(result, 'markdown') and result.markdown:
            text_content = result.markdown.fit_markdown or result.markdown.raw_markdown or ""
        
        # Extract images
        images = []
        if hasattr(result, 'media') and result.media:
            images = result.media.get('images', [])
        
        # Check if PDF was generated
        has_pdf = result.pdf is not None
        
        return {
            'url': result.url,
            'title': getattr(result, 'title', ''),
            'depth': result.metadata.get('depth', 0),
            'text_content': text_content,
            'text_length': len(text_content),
            'word_count': getattr(result.markdown, 'word_count', 0) if hasattr(result, 'markdown') else 0,
            'images': images,
            'image_count': len(images),
            'has_pdf': has_pdf,
            'pdf_size': len(result.pdf) if has_pdf else 0,
            'links': result.links if hasattr(result, 'links') else {},
            'status_code': getattr(result, 'status_code', 000),
            'crawl_timestamp': getattr(result, 'crawl_timestamp', '')
        }

# Usage Example
async def main():
    """
    Example demonstrating how to use the AdvancedDeepCrawler class.
    """
    async with AdvancedDeepCrawler(headless=True) as crawler:
        results = await crawler.deep_crawl(
            start_url="https://docs.crawl4ai.com",
            max_depth=2,
            max_pages=20,
            keywords=["crawling", "extraction", "markdown", "configuration"],
            allowed_domains=["docs.crawl4ai.com"]
        )
        
        # Print summary
        print(f"\n--- Crawl Summary ---")
        print(f"Total pages crawled: {len(results)}")
        
        total_text = sum(len(r['text_content']) for r in results)
        total_images = sum(r['image_count'] for r in results)
        total_pdfs = sum(1 for r in results if r['has_pdf'])
        
        print(f"Total text characters: {total_text}")
        print(f"Total images found: {total_images}")
        print(f"Pages with PDFs: {total_pdfs}")
        
        # Save results to JSON file
        with open('crawl_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print("Results saved to crawl_results.json")

if __name__ == "__main__":
    asyncio.run(main())