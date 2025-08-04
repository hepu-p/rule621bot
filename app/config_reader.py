import logging
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

logger = logging.getLogger(__name__)

class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    bot_token: SecretStr

class AdminSettings(BaseModel):
    admin_ids: list[int]

def load_admin_config(path: str = "config.yaml") -> AdminSettings:
    try:
        with open(path, 'r') as f:
            config_data = yaml.safe_load(f)
        if not config_data or 'admin_ids' not in config_data:
            logger.warning(f"Configuration file {path} is empty or does not contain 'admin_ids'.")
            return AdminSettings(admin_ids=[])
        
        # Фильтруем None значения, которые могут появиться из-за пустых строк в yaml
        admin_ids = [item for item in config_data.get('admin_ids', []) if item is not None]
        return AdminSettings(admin_ids=admin_ids)
    except FileNotFoundError:
        logger.error(f"Configuration file {path} not found.")
        return AdminSettings(admin_ids=[])
    except (yaml.YAMLError, ValidationError) as e:
        logger.error(f"Error parsing configuration file {path}: {e}")
        return AdminSettings(admin_ids=[])

try:
    config = BotConfig()
except ValidationError as e:
    logger.error(f"Error loading bot configuration from .env: {e}")
    # Provide a default or exit
    config = None # Or handle it as you see fit, maybe exit the application

admin_config = load_admin_config()