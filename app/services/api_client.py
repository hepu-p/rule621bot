# app/services/api_client.py
import asyncio
import aiohttp
import random
import logging
from typing import Optional, Dict, Any, List
import xml.etree.ElementTree as ET
import cloudscraper

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def format_post_e621(post: Dict) -> Optional[Dict]:
    """Вспомогательная функция для унификации ответа от e621."""
    try:
        if not post or not post.get('file') or not post['file'].get('url'):
            logger.warning(f"Invalid post format from e621: {post}")
            return None
        return {
            "id": post["id"], "url": post["file"]["url"], "ext": post["file"]["ext"],
            "tags": post["tags"]["general"], "source": f"https://e621.net/posts/{post['id']}"
        }
    except KeyError as e:
        logger.warning(f"Missing key {e} in e621 post: {post}")
        return None

def format_post_rule34(post: Dict) -> Optional[Dict]:
    """Вспомогательная функция для унификации ответа от rule34."""
    try:
        if not post or 'file_url' not in post:
            logger.warning(f"Invalid post format from rule34: {post}")
            return None
        return {
            "id": post["id"], "url": post["file_url"], "ext": post["image"].split('.')[-1],
            "tags": post["tags"].split(), "source": f"https://rule34.xxx/index.php?page=post&s=view&id={post['id']}"
        }
    except KeyError as e:
        logger.warning(f"Missing key {e} in rule34 post: {post}")
        return None

class BaseApiClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get_post(self, tags: str, negative_tags: str, tags_mode: str, post_priority: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

class E621Client(BaseApiClient):
    API_URL = "https://e621.net/posts.json"
    PRIORITY_ORDER_MAP = {
        'random': 'random', 'newest': 'id_desc', 'oldest': 'id_asc',
        'most_popular': 'score_desc', 'least_popular': 'score_asc'
    }

    def _calculate_weights(self, posts: List[Dict], priority: str) -> Optional[List[float]]:
        try:
            weight_calculators = {
                'most_popular': lambda p: max(0, p['score']['total']) + 1,
                'least_popular': lambda p: 1 / (max(0, p['score']['total']) + 1),
                'newest': lambda p: p['id'],
                'oldest': lambda p: 1 / p['id'] if p['id'] > 0 else 1
            }
            if priority in weight_calculators:
                return [weight_calculators[priority](p) for p in posts]
        except (TypeError, KeyError) as e:
            logger.error(f"Could not calculate weights due to unexpected post data: {e}")
            return None
        return None

    async def get_post(self, tags: str, negative_tags: str, tags_mode: str, post_priority: str) -> Optional[Dict[str, Any]]:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        formatted_tags = ' '.join(f"~{tag}" for tag in tag_list) if tags_mode == 'OR' and len(tag_list) > 1 else ' '.join(tag_list)
        if negative_tags:
            formatted_tags += ' ' + ' '.join(f"-{tag.strip()}" for tag in negative_tags.split(','))
        
        order_tag = self.PRIORITY_ORDER_MAP.get(post_priority, 'random')
        limit = 100

        params = {"tags": f"{formatted_tags} order:{order_tag}", "limit": limit}
        logger.info(f"Requesting e621 with params: {params}")
        
        try:
            async with self.session.get(self.API_URL, params=params, headers=HEADERS) as response:
                if response.status != 200:
                    logger.error(f"e621 API returned status {response.status}: {await response.text()}")
                    return None
                data = await response.json()
                
                raw_posts = data.get("posts", [])
                if not raw_posts:
                    logger.warning("No posts found from e621 for the given tags.")
                    return None

                if post_priority == 'random':
                    return format_post_e621(random.choice(raw_posts))
                
                weights = self._calculate_weights(raw_posts, post_priority)
                if weights is None:
                    return format_post_e621(random.choice(raw_posts))

                chosen_post = random.choices(raw_posts, weights=weights, k=1)[0]
                return format_post_e621(chosen_post)

        except (aiohttp.ClientError, IndexError, TypeError, KeyError) as e:
            logger.exception(f"Error in E621Client: {e}")
            return None

class Rule34Client(BaseApiClient):
    API_URL = "https://api.rule34.xxx/index.php"

    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        self.scraper = cloudscraper.create_scraper()

    async def get_post(self, tags: str, negative_tags: str, tags_mode: str, post_priority: str) -> Optional[Dict[str, Any]]:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        formatted_tags = ' '.join(f"~{tag}" for tag in tag_list) if tags_mode == 'OR' and len(tag_list) > 1 else ' '.join(tag_list)
        if negative_tags:
            formatted_tags += ' ' + ' '.join(f"-{tag.strip()}" for tag in negative_tags.split(','))

        logger.info(f"Requesting Rule34 with tags: {formatted_tags}")

        def _get_request(url, params):
            return self.scraper.get(url, params=params, headers=HEADERS)

        try:
            count_params = {"page": "dapi", "s": "post", "q": "index", "tags": formatted_tags, "limit": 0}
            total_posts = 0
            
            response = await asyncio.to_thread(_get_request, self.API_URL, count_params)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            total_posts = int(root.get('count', 0))

            if total_posts == 0:
                logger.warning("No posts found from Rule34 for the given tags.")
                return None
            
            limit_per_page = 100
            max_pid = min(total_posts, 200000)
            pid = 0
            if post_priority != 'newest' and max_pid > 0:
                pid = random.randint(0, (max_pid - 1) // limit_per_page)


            post_params = {"page": "dapi", "s": "post", "q": "index", "json": "1", "tags": formatted_tags, "limit": limit_per_page, "pid": pid}
            
            response = await asyncio.to_thread(_get_request, self.API_URL, post_params)
            response.raise_for_status()
            if 'application/json' not in response.headers.get('Content-Type', ''):
                logger.error(f"Rule34 returned non-JSON response: {response.text}")
                return None
            posts = response.json()
            return format_post_rule34(random.choice(posts)) if posts else None

        except aiohttp.ClientConnectorError as e:
            logger.error(f"Network connection error in Rule34Client: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML from Rule34: {e}. Response text: {response.text}")
            return None
        except (aiohttp.ClientError, IndexError, KeyError, ValueError) as e:
            logger.exception(f"An error occurred in Rule34Client: {e}")
            return None

def get_api_client(api_source: str, session: aiohttp.ClientSession) -> BaseApiClient:
    if api_source == 'e621': return E621Client(session)
    elif api_source == 'rule34': return Rule34Client(session)
    logger.error(f"Unknown API source requested: {api_source}")
    raise ValueError("Unknown API source")