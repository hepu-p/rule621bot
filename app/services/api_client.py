# app/services/api_client.py
import aiohttp
import random
from typing import Optional, Dict, Any, List
import xml.etree.ElementTree as ET

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def format_post_e621(post: Dict) -> Optional[Dict]:
    """Вспомогательная функция для унификации ответа от e621."""
    if not post or not post.get('file') or not post['file'].get('url'):
        return None
    return {
        "id": post["id"], "url": post["file"]["url"], "ext": post["file"]["ext"],
        "tags": post["tags"]["general"], "source": f"https://e621.net/posts/{post['id']}"
    }

def format_post_rule34(post: Dict) -> Optional[Dict]:
    """Вспомогательная функция для унификации ответа от rule34."""
    if not post or 'file_url' not in post:
        return None
    return {
        "id": post["id"], "url": post["file_url"], "ext": post["image"].split('.')[-1],
        "tags": post["tags"].split(), "source": f"https://rule34.xxx/index.php?page=post&s=view&id={post['id']}"
    }

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
        """
        Calculates weights for posts based on priority.
        Corrected to handle the nested score object from the e621 API.
        """
        try:
            if priority == 'most_popular': return [max(0, p['score']['total']) + 1 for p in posts]
            if priority == 'least_popular': return [1 / (max(0, p['score']['total']) + 1) for p in posts]
            if priority == 'newest': return [p['id'] for p in posts]
            if priority == 'oldest': return [1 / p['id'] if p['id'] > 0 else 1 for p in posts]
        except (TypeError, KeyError) as e:
            print(f"Could not calculate weights due to unexpected post data: {e}")
            return None # Fallback to random if weights can't be calculated
        return None # For 'random' priority

    async def get_post(self, tags: str, negative_tags: str, tags_mode: str, post_priority: str) -> Optional[Dict[str, Any]]:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        formatted_tags = ' '.join(f"~{tag}" for tag in tag_list) if tags_mode == 'OR' and len(tag_list) > 1 else ' '.join(tag_list)
        if negative_tags:
            formatted_tags += ' ' + ' '.join(f"-{tag.strip()}" for tag in negative_tags.split(','))
        
        order_tag = self.PRIORITY_ORDER_MAP.get(post_priority, 'random')
        limit = 100

        params = {"tags": f"{formatted_tags} order:{order_tag}", "limit": limit}
        
        try:
            async with self.session.get(self.API_URL, params=params, headers=HEADERS) as response:
                if response.status != 200: return None
                data = await response.json()
                
                raw_posts = data.get("posts", [])
                if not raw_posts: return None

                # For 'random' priority or if weighting fails, choose a random post
                if post_priority == 'random':
                    return format_post_e621(random.choice(raw_posts))
                
                weights = self._calculate_weights(raw_posts, post_priority)
                # If weighting fails or is not applicable, fall back to random
                if weights is None:
                    return format_post_e621(random.choice(raw_posts))

                chosen_post = random.choices(raw_posts, weights=weights, k=1)[0]
                return format_post_e621(chosen_post)

        except (aiohttp.ClientError, IndexError, TypeError, KeyError) as e:
            print(f"Error in E621Client: {e}")
            return None

class Rule34Client(BaseApiClient):
    API_URL = "https://api.rule34.xxx/index.php"

    async def get_post(self, tags: str, negative_tags: str, tags_mode: str, post_priority: str) -> Optional[Dict[str, Any]]:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        formatted_tags = random.choice(tag_list) if tags_mode == 'OR' and tag_list else ' '.join(tag_list)
        if negative_tags:
            formatted_tags += ' ' + ' '.join(f"-{tag.strip()}" for tag in negative_tags.split(','))

        try:
            # First, get the total count of posts for the tags
            count_params = {"page": "dapi", "s": "post", "q": "index", "tags": formatted_tags, "limit": 0}
            total_posts = 0
            async with self.session.get(self.API_URL, params=count_params, headers=HEADERS) as response:
                response.raise_for_status() # Raise an exception for bad status codes
                root = ET.fromstring(await response.text())
                total_posts = int(root.get('count', 0))

            if total_posts == 0: return None
            
            pid = 0 # Default to the first page for 'newest'
            if post_priority != 'newest':
                # Rule34 API is limited to ~2000 pages, so we cap the random index
                effective_total = min(total_posts, 200000)
                if effective_total > 0:
                    pid = random.randint(0, effective_total - 1)

            # Now, fetch one random post using the calculated page index (pid)
            post_params = {"page": "dapi", "s": "post", "q": "index", "json": "1", "tags": formatted_tags, "limit": 1, "pid": pid}
            
            async with self.session.get(self.API_URL, params=post_params, headers=HEADERS) as response:
                response.raise_for_status()
                # Ensure the response is JSON before parsing
                if 'application/json' not in response.headers.get('Content-Type', ''):
                    print(f"Rule34 returned non-JSON response: {await response.text()}")
                    return None
                posts = await response.json()
                return format_post_rule34(posts[0]) if posts else None

        except aiohttp.ClientConnectorError as e:
            print(f"Network connection error in Rule34Client: {e}")
            return None
        except (aiohttp.ClientError, ET.ParseError, IndexError, KeyError, ValueError) as e:
            print(f"An error occurred in Rule34Client: {e}")
            return None

def get_api_client(api_source: str, session: aiohttp.ClientSession) -> BaseApiClient:
    if api_source == 'e621': return E621Client(session)
    elif api_source == 'rule34': return Rule34Client(session)
    raise ValueError("Unknown API source")
