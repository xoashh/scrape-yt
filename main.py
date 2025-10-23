import asyncio
import os
from apify import Actor
from playwright.async_api import async_playwright

async def main():
    """
    Main function to initialize and run the YouTube comment scraper actor,
    now including Apify Proxy support controlled via input.
    """
    async with Actor:
        Actor.log.info('Starting the YouTube comment scraper...')

        # Get actor input, with default values
        actor_input = await Actor.get_input() or {}
        video_urls = actor_input.get('videoUrls', [])
        max_comments = actor_input.get('maxComments')  # Can be None

        # Get proxy preference from input
        use_proxy = actor_input.get('useProxy', True)
        proxy = None
        if use_proxy:
            proxy_url = os.getenv('APIFY_PROXY_URL')
            if proxy_url:
                proxy = {"server": proxy_url}
                Actor.log.info(f'Using Apify Proxy at {proxy_url}')
            else:
                Actor.log.info('Proxy requested but APIFY_PROXY_URL not set. Running without proxy.')

        if not video_urls:
            Actor.log.warning('No video URLs provided in the input. Exiting.')
            return

        # Launch Playwright browser (with proxy if enabled)
        async with async_playwright() as p:
            browser = await p.chromium.launch(proxy=proxy, headless=True)
            page = await browser.new_page()

            for url in video_urls:
                if not url.strip():
                    continue  # Skip empty URLs

                Actor.log.info(f'Scraping comments for video: {url}')
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                    await page.wait_for_selector('#comments', timeout=15000)
                except Exception as e:
                    Actor.log.error(f"Could not load page or find comments section for {url}. Error: {e}")
                    continue

                # --- Scrolling Logic ---
                Actor.log.info('Scrolling to load all comments...')
                scraped_comment_ids = set()
                while True:
                    comments_on_page = await page.query_selector_all('#comment')
                    initial_count = len(scraped_comment_ids)
                    if max_comments and len(scraped_comment_ids) >= max_comments:
                        Actor.log.info(f'Reached max comment limit of {max_comments}.')
                        break

                    await page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
                    await asyncio.sleep(2)

                    new_comments = await page.query_selector_all('#comment')
                    if len(new_comments) == initial_count:
                        Actor.log.info("No new comments loaded. Assuming end of comments section.")
                        break

                    for comment in new_comments:
                        comment_id = await comment.get_attribute('id')
                        scraped_comment_ids.add(comment_id)

                Actor.log.info('Finished scrolling. Extracting comment data...')

                comment_elements = await page.query_selector_all('#contents > ytd-comment-thread-renderer')
                count = 0
                for comment_element in comment_elements:
                    if max_comments and count >= max_comments:
                        break
                    try:
                        username_element = await comment_element.query_selector('#author-text')
                        timestamp_element = await comment_element.query_selector('yt-formatted-string.published-time-text a')
                        comment_text_element = await comment_element.query_selector('#content-text')
                        if all([username_element, timestamp_element, comment_text_element]):
                            username = (await username_element.inner_text()).strip()
                            timestamp = (await timestamp_element.inner_text()).strip()
                            comment_text = (await comment_text_element.inner_text()).strip()
                            await Actor.push_data({
                                'videoUrl': url,
                                'username': username,
                                'timestamp': timestamp,
                                'comment': comment_text
                            })
                            count += 1
                    except Exception as e:
                        Actor.log.warning(f"Could not extract a comment's data. Skipping. Error: {e}")

                Actor.log.info(f'Successfully scraped {count} comments from {url}.')

            await browser.close()
            Actor.log.info('Scraping finished for all videos.')

if __name__ == "__main__":
    asyncio.run(main())
