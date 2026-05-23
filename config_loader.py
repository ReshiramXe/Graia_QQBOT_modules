# 统一配置加载模块
# 用于加载共享配置和模块特定配置

import yaml
from pathlib import Path
from functools import lru_cache

def get_config_dir():
    """获取配置目录路径"""
    return Path(__file__).parent / 'config'

@lru_cache(maxsize=1)
def load_common_config():
    """加载共享配置（数据库、API密钥等）"""
    config_path = get_config_dir() / 'common_config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_module_config(module_name):
    """加载特定模块的配置"""
    config_path = get_config_dir() / f'{module_name}.yaml'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

def get_db_config():
    """获取数据库配置"""
    common = load_common_config()
    return common.get('database', {})

def get_api_keys():
    """获取API密钥配置"""
    common = load_common_config()
    return common.get('api_keys', {})