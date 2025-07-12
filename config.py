import os
from typing import Dict, Any

def get_device_config() -> Dict[str, Any]:
    """Get network device configuration from environment variables."""
    return {
        'device_type': os.getenv('DEVICE_TYPE', 'cisco_ios'),
        'host': os.getenv('DEVICE_HOST'),
        'username': os.getenv('DEVICE_USERNAME'),
        'password': os.getenv('DEVICE_PASSWORD'),
    }

def get_database_url() -> str:
    """Get database URL from environment variables."""
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    name = os.getenv('DB_NAME', 'network_db')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD')
    
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

def get_monitor_config() -> Dict[str, str]:
    """Get flow monitor configuration from environment variables."""
    return {
        'main_monitor': os.getenv('MAIN_MONITOR', 'FLOW-MONITOR'),
        'flag_monitor': os.getenv('FLAG_MONITOR', 'dat_Gi1_885011376')
    }

def validate_config():
    """Validate that required environment variables are set."""
    required_vars = [
        'DEVICE_USERNAME', 'DEVICE_PASSWORD', 'DEVICE_HOST', 'DB_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
