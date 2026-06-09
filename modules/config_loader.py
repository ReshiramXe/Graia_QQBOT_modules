# 统一配置加载模块
# 用于加载共享配置和模块特定配置
# 敏感信息（API密钥、数据库密码）以YAML配置文件为主要来源
# 环境变量可作为可选覆盖（通过 _env 函数），但默认直接从YAML读取

import os
import yaml
import pymysql
from pathlib import Path
from functools import lru_cache
from dbutils.pooled_db import PooledDB

# 数据库连接池（全局单例，复用连接减少 MySQL 内存开销）
_pool = None


def _init_pool():
    """初始化数据库连接池（首次调用时创建）"""
    global _pool
    if _pool is None:
        cfg = get_db_config()
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=8,      # 最多8个连接
            mincached=1,           # 最少保持1个空闲连接
            maxcached=4,           # 最多缓存4个
            maxshared=0,           # 不共享连接
            blocking=True,         # 连接耗尽时等待
            maxusage=100,          # 单个连接最多复用100次
            setsession=[],
            ping=0,                # 0=不ping, 1=默认, 2=每次用前ping, 4=每次用完ping, 7=总是ping
            host=cfg['host'],
            user=cfg['user'],
            password=cfg['passwd'],
            port=cfg['port'],
            database=cfg['db'],
            charset=cfg['charset'],
        )
    return _pool


def get_db_connection():
    """获取数据库连接（从连接池借用，用完 close() 即归还）"""
    return _init_pool().connection()


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


def _env(key, yaml_value):
    """获取配置值 - YAML为主，环境变量可覆盖

    Args:
        key: 环境变量名
        yaml_value: YAML中的默认值

    Returns:
        环境变量值（如果设置），否则返回YAML值
    """
    return os.environ.get(key, yaml_value)


def get_db_config():
    """获取数据库配置 - 从YAML读取，环境变量可覆盖"""
    yaml_config = load_common_config().get('database', {})
    return {
        'host': _env('DB_HOST', yaml_config.get('host', '127.0.0.1')),
        'user': _env('DB_USER', yaml_config.get('user', 'root')),
        'passwd': _env('DB_PASSWORD', yaml_config.get('passwd', '')),
        'port': int(_env('DB_PORT', str(yaml_config.get('port', 3306)))),
        'db': _env('DB_NAME', yaml_config.get('db', 'qqbot')),
        'charset': _env('DB_CHARSET', yaml_config.get('charset', 'utf8mb4')),
    }


def get_api_keys():
    """获取API密钥配置 - 从YAML读取，环境变量可覆盖"""
    yaml_keys = load_common_config().get('api_keys', {})
    return {
        'siliconflow': _env('SILICONFLOW_API_KEY', yaml_keys.get('siliconflow', '')),
        'deepseek': _env('DEEPSEEK_API_KEY', yaml_keys.get('deepseek', '')),
        'xiaoai': _env('XIAOAI_API_KEY', yaml_keys.get('xiaoai', '')),
        'xi-ai': _env('XI_AI_API_KEY', yaml_keys.get('xi-ai', '')),
        'xai': _env('XAI_API_KEY', yaml_keys.get('xai', '')),
        'Kimi': _env('KIMI_API_KEY', yaml_keys.get('Kimi', '')),
        'kinoko': _env('KINOKO_API_KEY', yaml_keys.get('kinoko', '')),
        'psutil': _env('PSUTIL_API_KEY', yaml_keys.get('psutil', '')),
    }
